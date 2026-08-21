// PR8.11.1 production repair: wire proven visible-assistant terminal evidence
// into the fail-closed page-turn completion hook installed below PR8.8/PR8.9.
//
// The live characterization proved that current-answer finish_reason, end_turn
// and is_complete arrive with the final visible text, while a generic
// finished_successfully status can appear before the first assistant text.
// Therefore the early boundary requires visible assistant text plus a
// finish_reason and at least one independent terminal bit (end_turn or
// is_complete). Canonical HTTP readback remains authoritative afterwards.

const _pr8111RepairPriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr8111RepairPriorRecordAssistant = _pr89BrowserStreamRecordAssistant;
const _pr8111RepairPriorFirstTerminal = _pr8111FirstTerminal;
const _pr8111RepairPriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr8111RepairPriorExecuteNativeTurn = executeNativeTurn;

let _pr8111RepairContext = null;

function _pr8111RepairFinishReason(value) {
  const normalized = typeof value === "string" ? value.trim() : "";
  return normalized || null;
}

function _pr8111RepairResolveTerminal(finishReason, completionEvidence) {
  const active = _pr8111RepairContext;
  if (active === null || active.terminalResolved === true) return;
  if (!Number.isFinite(active.firstVisibleAssistantTextAt)) return;
  if (_pr8111RepairFinishReason(finishReason) === null) return;
  if (completionEvidence !== "end_turn" && completionEvidence !== "is_complete" && completionEvidence !== "end_turn+is_complete") {
    return;
  }

  active.terminalResolved = true;
  active.terminalKind = "assistant_terminal_conjunction";
  active.terminalFinishReason = finishReason;
  active.terminalCompletionEvidence = completionEvidence;
  active.terminalResolvedAt = performance.now();
  active.resolveTerminal({
    kind: active.terminalKind,
    finishReason,
    completionEvidence
  });
}

_pr89BrowserStreamRecordAssistant = async function _pr8111RepairRecordAssistant(
  context,
  candidate
) {
  const active = _pr8111RepairContext;
  const text = candidate?.text;
  const key = candidate?.messageKey;
  const previous = (
    context?.lastTextByKey instanceof Map && typeof key === "string"
  ) ? context.lastTextByKey.get(key) : undefined;

  await _pr8111RepairPriorRecordAssistant(context, candidate);

  if (
    active === null ||
    typeof text !== "string" ||
    typeof key !== "string" ||
    !key ||
    previous === text
  ) {
    return;
  }

  const now = performance.now();
  if (!Number.isFinite(active.firstVisibleAssistantTextAt)) {
    active.firstVisibleAssistantTextAt = now;
  }
  active.lastVisibleAssistantTextAt = now;
  active.lastVisibleAssistantMessageKey = key;
};

// Resolve only after the complete SSE block has passed through the established
// PR8.9 patch/full-message parser and the PR8.11.1 characterization layer. This
// lets us require two independent current-answer terminal signals without
// changing raw SSE parsing or exporting any additional content.
_pr89BrowserStreamProcessSseEvent = async function _pr8111RepairProcessSseEvent(
  streamContext,
  block
) {
  const result = await _pr8111RepairPriorProcessSseEvent(streamContext, block);
  const active = _pr8111RepairContext;
  const characterized = _pr8111Context;
  if (active === null || characterized === null || active.terminalResolved === true) {
    return result;
  }

  const firstText = active.firstVisibleAssistantTextAt;
  if (!Number.isFinite(firstText)) return result;

  const finishReason = _pr8111RepairFinishReason(characterized.assistantFinishReason);
  const finishAt = characterized.assistantFinishReasonAt;
  const endTurnAt = characterized.assistantEndTurnAt;
  const isCompleteAt = characterized.assistantIsCompleteAt;
  const finishCurrent = Number.isFinite(finishAt) && finishAt >= firstText;
  const endTurnCurrent = Number.isFinite(endTurnAt) && endTurnAt >= firstText;
  const isCompleteCurrent = Number.isFinite(isCompleteAt) && isCompleteAt >= firstText;

  if (finishReason !== null && finishCurrent && (endTurnCurrent || isCompleteCurrent)) {
    const completionEvidence = endTurnCurrent && isCompleteCurrent
      ? "end_turn+is_complete"
      : endTurnCurrent
      ? "end_turn"
      : "is_complete";
    _pr8111RepairResolveTerminal(finishReason, completionEvidence);
  }
  return result;
};

// Generic status / marker observations remain useful diagnostics, but a signal
// timestamp that predates the first visible assistant text cannot characterize
// completion of the current visible answer.
_pr8111FirstTerminal = function _pr8111RepairFirstTerminal(context) {
  const firstText = context?.firstAssistantTextObservedAt;
  if (!Number.isFinite(firstText)) return { kind: null, at: null };

  const signals = [
    ["assistant_finish_reason", context.assistantFinishReasonAt],
    ["assistant_end_turn", context.assistantEndTurnAt],
    ["assistant_is_complete", context.assistantIsCompleteAt],
    ["assistant_completed_status", context.assistantCompletedStatusAt],
    ["done_sentinel", context.doneSentinelAt]
  ].filter(([, at]) => Number.isFinite(at) && at >= firstText);

  if (!signals.length) return { kind: null, at: null };
  signals.sort((left, right) => left[1] - right[1]);
  return { kind: signals[0][0], at: signals[0][1] };
};

executeOfficialPageTurn = async function _pr8111RepairExecuteOfficialPageTurn(args) {
  const active = _pr8111RepairContext;
  if (active === null) return _pr8111RepairPriorExecuteOfficialPageTurn(args);

  const restore = _cwaInstallOfficialPageEarlyCompletionSignal(active.terminalPromise);
  try {
    return await _pr8111RepairPriorExecuteOfficialPageTurn(args);
  } finally {
    restore();
  }
};

function _pr8111RepairLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

executeNativeTurn = async function _pr8111RepairExecuteNativeTurn(message) {
  const leaseId = _pr8111RepairLeaseId(message?.browserAuthorityLeaseId);
  const ordinaryWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  if (!ordinaryWrite) return _pr8111RepairPriorExecuteNativeTurn(message);
  if (_pr8111RepairContext !== null) {
    throw new Error("PR8_11_1_EARLY_COMPLETION_REPAIR_CONTEXT_ALREADY_ACTIVE");
  }

  let resolveTerminal;
  const terminalPromise = new Promise((resolve) => {
    resolveTerminal = resolve;
  });
  const context = {
    leaseId,
    terminalPromise,
    resolveTerminal,
    terminalResolved: false,
    terminalKind: null,
    terminalFinishReason: null,
    terminalCompletionEvidence: null,
    terminalResolvedAt: null,
    firstVisibleAssistantTextAt: null,
    lastVisibleAssistantTextAt: null,
    lastVisibleAssistantMessageKey: null
  };
  _pr8111RepairContext = context;

  try {
    return await _pr8111RepairPriorExecuteNativeTurn(message);
  } finally {
    _pr8111RepairContext = null;
  }
};