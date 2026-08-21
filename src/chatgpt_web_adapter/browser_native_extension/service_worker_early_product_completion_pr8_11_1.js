// PR8.11.1: early product-completion signal characterization.
//
// Read-only characterization layered over the proven PR8.9 response stream and
// PR8.11 timing surface. It records only bounded timestamps, counts and small
// terminal enums. Prompt/assistant text, raw SSE, response bodies, headers,
// cookies, credentials and DOM/HTML are never persisted or returned.

const PR8111_EARLY_COMPLETION_SCHEMA_VERSION = 1;
const PR8111_EARLY_COMPLETION_STORAGE_KEY = "browserAuthorityLastEarlyProductCompletionV1";
const PR8111_COMPOSER_POLL_INTERVAL_MS = 100;
const PR8111_COMPOSER_POLL_TIMEOUT_MS = 120000;

const _pr8111PriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr8111PriorRecordAssistant = _pr89BrowserStreamRecordAssistant;
const _pr8111PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr8111PriorExecuteNativeTurn = executeNativeTurn;

let _pr8111Context = null;

function _pr8111LeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr8111ElapsedMs(context, at = performance.now()) {
  if (!context || !Number.isFinite(context.startedAt) || !Number.isFinite(at)) return null;
  return Math.max(0, Math.round(at - context.startedAt));
}

function _pr8111DurationMs(startedAt, endedAt) {
  if (!Number.isFinite(startedAt) || !Number.isFinite(endedAt) || endedAt < startedAt) {
    return null;
  }
  return Math.max(0, Math.round(endedAt - startedAt));
}

function _pr8111RecordFirst(context, field, at = performance.now()) {
  if (!context || Number.isFinite(context[field])) return;
  context[field] = at;
}

function _pr8111NormalizedStatus(value) {
  return typeof value === "string" && value.trim() ? value.trim().toLowerCase() : null;
}

function _pr8111RecordFinishReason(context, value, at = performance.now()) {
  const finishReason = typeof value === "string" ? value.trim() : "";
  if (!finishReason) return;
  _pr8111RecordFirst(context, "assistantFinishReasonAt", at);
  if (context.assistantFinishReason === null) context.assistantFinishReason = finishReason;
}

function _pr8111InspectMetadata(context, metadata, at = performance.now()) {
  if (!metadata || typeof metadata !== "object") return;
  const details = metadata.finish_details;
  if (details && typeof details === "object") {
    _pr8111RecordFinishReason(context, details.type, at);
  }
  _pr8111RecordFinishReason(context, metadata.finish_reason, at);
  if (metadata.is_complete === true) {
    _pr8111RecordFirst(context, "assistantIsCompleteAt", at);
  }
}

function _pr8111RecordCompletedStatus(context, value, at = performance.now()) {
  const status = _pr8111NormalizedStatus(value);
  if (!["completed", "complete", "finished", "finished_successfully", "done"].includes(status)) {
    return;
  }
  _pr8111RecordFirst(context, "assistantCompletedStatusAt", at);
  if (context.assistantCompletedStatus === null) context.assistantCompletedStatus = status;
}

function _pr8111VisibleAssistant(message) {
  if (!message || typeof message !== "object") return false;
  if (message?.author?.role !== "assistant") return false;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return false;
  const recipient = typeof message.recipient === "string" ? message.recipient.trim() : "";
  return !recipient || recipient === "all";
}

function _pr8111InspectAssistantTerminal(context, message) {
  if (!_pr8111VisibleAssistant(message)) return;
  const now = performance.now();
  _pr8111RecordFinishReason(context, _pr89BrowserStreamFinishReason(message), now);
  if (message.end_turn === true) {
    _pr8111RecordFirst(context, "assistantEndTurnAt", now);
  }
  _pr8111InspectMetadata(context, message.metadata, now);
  _pr8111RecordCompletedStatus(context, message.status, now);
}

function _pr8111InspectValue(context, value, depth = 0) {
  if (depth > 7 || value == null) return;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 128)) _pr8111InspectValue(context, item, depth + 1);
    return;
  }
  if (typeof value !== "object") return;

  const type = typeof value.type === "string" ? value.type.trim() : "";
  if (type === "stream_handoff") _pr8111RecordFirst(context, "streamHandoffAt");
  if (type === "message_marker") _pr8111RecordFirst(context, "messageMarkerAt");

  if (value?.author?.role === "assistant") {
    _pr8111InspectAssistantTerminal(context, value);
  }

  for (const key of ["message", "messages", "data", "result", "payload", "turn", "v", "value"]) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      _pr8111InspectValue(context, value[key], depth + 1);
    }
  }
}

function _pr8111InspectPatchItem(active, streamContext, item) {
  if (!item || typeof item !== "object") return;
  const assistantActive = streamContext?.patchAssistantActive === true;
  const path = typeof item.p === "string" ? item.p : null;
  const value = item.v;

  if (value && typeof value === "object" && !Array.isArray(value)) {
    const message = value.message;
    if (message && typeof message === "object") {
      _pr8111InspectAssistantTerminal(active, message);
    }
  }
  if (!assistantActive || path === null) return;

  const now = performance.now();
  if (path === "/message/metadata") {
    _pr8111InspectMetadata(active, value, now);
  } else if (path === "/message/end_turn" && value === true) {
    _pr8111RecordFirst(active, "assistantEndTurnAt", now);
  } else if (path === "/message/status") {
    _pr8111RecordCompletedStatus(active, value, now);
  }
}

function _pr8111InspectPatchEnvelope(active, streamContext, payload) {
  if (!payload || typeof payload !== "object") return;
  _pr8111InspectPatchItem(active, streamContext, payload);
  if (Array.isArray(payload.v)) {
    for (const item of payload.v.slice(0, 128)) {
      _pr8111InspectPatchItem(active, streamContext, item);
    }
  }
}

_pr89BrowserStreamProcessSseEvent = async function _pr8111ProcessSseEvent(context, block) {
  const active = _pr8111Context;
  let data = "";
  let payload = null;
  if (active !== null) {
    try {
      const lines = String(block || "").split(/\r?\n/);
      const dataLines = [];
      for (const line of lines) {
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      data = dataLines.join("\n").trim();
      if (data && data !== "[DONE]") {
        try {
          payload = JSON.parse(data);
        } catch {
          payload = null;
        }
      }
    } catch {
      active.characterizationErrorCount += 1;
    }
  }

  const result = await _pr8111PriorProcessSseEvent(context, block);

  if (active !== null) {
    try {
      if (data === "[DONE]") {
        _pr8111RecordFirst(active, "doneSentinelAt");
      } else if (payload !== null) {
        _pr8111InspectValue(active, payload);
        _pr8111InspectPatchEnvelope(active, context, payload);
      }
    } catch {
      active.characterizationErrorCount += 1;
    }
  }
  return result;
};

_pr89BrowserStreamRecordAssistant = async function _pr8111RecordAssistant(context, candidate) {
  const active = _pr8111Context;
  const text = candidate?.text;
  const key = candidate?.messageKey;
  const previous = (
    context?.lastTextByKey instanceof Map && typeof key === "string"
  ) ? context.lastTextByKey.get(key) : undefined;

  await _pr8111PriorRecordAssistant(context, candidate);

  if (active === null) return;
  _pr8111RecordFinishReason(active, candidate?.finishReason);
  if (
    typeof text === "string" &&
    typeof key === "string" &&
    key &&
    previous !== text
  ) {
    const now = performance.now();
    _pr8111RecordFirst(active, "firstAssistantTextObservedAt", now);
    active.lastAssistantTextObservedAt = now;
    active.assistantTextObservationCount += 1;
  }
};

async function _pr8111PollComposerReadiness(debuggee, context) {
  const pollStartedAt = performance.now();
  let consecutiveReady = 0;
  while (
    context.stopComposerPoll !== true &&
    performance.now() - pollStartedAt < PR8111_COMPOSER_POLL_TIMEOUT_MS
  ) {
    if (Number.isFinite(context.lastAssistantTextObservedAt)) {
      try {
        const state = await queryComposerReadiness(debuggee);
        context.composerProbeCount += 1;
        if (state?.ready === true) {
          const now = performance.now();
          _pr8111RecordFirst(context, "firstComposerReadyAfterTextAt", now);
          consecutiveReady += 1;
          if (consecutiveReady >= 2) {
            _pr8111RecordFirst(context, "consecutiveComposerReadyAfterTextAt", now);
          }
        } else {
          consecutiveReady = 0;
        }
      } catch {
        consecutiveReady = 0;
        context.composerProbeErrorCount += 1;
      }
    }
    await sleep(PR8111_COMPOSER_POLL_INTERVAL_MS);
  }
}

executeOfficialPageTurn = async function _pr8111ExecuteOfficialPageTurn(args) {
  const context = _pr8111Context;
  if (context === null) return _pr8111PriorExecuteOfficialPageTurn(args);

  const tabId = args?.tabId;
  const debuggee = { tabId };
  let conversationRequestId = null;
  let listenerInstalled = false;

  const observer = (source, method, params) => {
    try {
      if (source?.tabId !== tabId) return;
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (
          conversationRequestId === null &&
          isConversationWrite(request?.url || "", request?.method || "")
        ) {
          conversationRequestId = params.requestId;
          _pr8111RecordFirst(context, "writeDelegatedAt");
        }
        return;
      }
      if (
        conversationRequestId !== null &&
        params?.requestId === conversationRequestId &&
        method === "Network.loadingFinished"
      ) {
        _pr8111RecordFirst(context, "networkCompleteAt");
      }
    } catch {
      context.characterizationErrorCount += 1;
    }
  };

  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  const composerPoll = _pr8111PollComposerReadiness(debuggee, context).catch(() => {
    context.composerProbeErrorCount += 1;
  });

  try {
    return await _pr8111PriorExecuteOfficialPageTurn(args);
  } finally {
    _pr8111RecordFirst(context, "officialPageTurnCompleteAt");
    context.stopComposerPoll = true;
    try {
      await composerPoll;
    } catch {
      // Observational poll cleanup only.
    }
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Observational listener cleanup only.
      }
    }
  }
};

function _pr8111QueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true
  );
}

async function _pr8111StoredRecord() {
  try {
    const stored = await chrome.storage.local.get(PR8111_EARLY_COMPLETION_STORAGE_KEY);
    const value = stored?.[PR8111_EARLY_COMPLETION_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

function _pr8111FirstTerminal(context) {
  const signals = [
    ["assistant_finish_reason", context.assistantFinishReasonAt],
    ["assistant_end_turn", context.assistantEndTurnAt],
    ["assistant_is_complete", context.assistantIsCompleteAt],
    ["assistant_completed_status", context.assistantCompletedStatusAt],
    ["done_sentinel", context.doneSentinelAt]
  ].filter(([, at]) => Number.isFinite(at));
  if (!signals.length) return { kind: null, at: null };
  signals.sort((left, right) => left[1] - right[1]);
  return { kind: signals[0][0], at: signals[0][1] };
}

function _pr8111Record(context) {
  const terminal = _pr8111FirstTerminal(context);
  const lastText = context.lastAssistantTextObservedAt;
  const networkDone = context.networkCompleteAt;
  return {
    schemaVersion: PR8111_EARLY_COMPLETION_SCHEMA_VERSION,
    browserAuthorityLeaseId: context.leaseId,
    assistantTextObservationCount: context.assistantTextObservationCount,
    composerProbeCount: context.composerProbeCount,
    composerProbeErrorCount: context.composerProbeErrorCount,
    characterizationErrorCount: context.characterizationErrorCount,
    writeDelegatedMs: _pr8111ElapsedMs(context, context.writeDelegatedAt),
    firstAssistantTextObservedMs: _pr8111ElapsedMs(context, context.firstAssistantTextObservedAt),
    lastAssistantTextObservedMs: _pr8111ElapsedMs(context, lastText),
    assistantFinishReasonObservedMs: _pr8111ElapsedMs(context, context.assistantFinishReasonAt),
    assistantFinishReason: context.assistantFinishReason,
    assistantEndTurnObservedMs: _pr8111ElapsedMs(context, context.assistantEndTurnAt),
    assistantIsCompleteObservedMs: _pr8111ElapsedMs(context, context.assistantIsCompleteAt),
    assistantCompletedStatusObservedMs: _pr8111ElapsedMs(context, context.assistantCompletedStatusAt),
    assistantCompletedStatus: context.assistantCompletedStatus,
    messageMarkerObservedMs: _pr8111ElapsedMs(context, context.messageMarkerAt),
    streamHandoffObservedMs: _pr8111ElapsedMs(context, context.streamHandoffAt),
    doneSentinelObservedMs: _pr8111ElapsedMs(context, context.doneSentinelAt),
    firstComposerReadyAfterTextMs: _pr8111ElapsedMs(context, context.firstComposerReadyAfterTextAt),
    consecutiveComposerReadyAfterTextMs: _pr8111ElapsedMs(
      context,
      context.consecutiveComposerReadyAfterTextAt
    ),
    networkCompleteMs: _pr8111ElapsedMs(context, networkDone),
    officialPageTurnCompleteMs: _pr8111ElapsedMs(context, context.officialPageTurnCompleteAt),
    earliestTerminalSignalKind: terminal.kind,
    earliestTerminalSignalMs: _pr8111ElapsedMs(context, terminal.at),
    lastTextToEarliestTerminalSignalMs: _pr8111DurationMs(lastText, terminal.at),
    lastTextToComposerReadyMs: _pr8111DurationMs(
      lastText,
      context.consecutiveComposerReadyAfterTextAt
    ),
    earliestTerminalSignalToNetworkCompleteMs: _pr8111DurationMs(terminal.at, networkDone),
    composerReadyToNetworkCompleteMs: _pr8111DurationMs(
      context.consecutiveComposerReadyAfterTextAt,
      networkDone
    ),
    lastTextToNetworkCompleteMs: _pr8111DurationMs(lastText, networkDone)
  };
}

executeNativeTurn = async function _pr8111ExecuteNativeTurn(message) {
  if (message?.characterizeEarlyProductCompletionSupport === true) {
    if (_pr8111QueryConflict(message)) {
      throw new Error("PR8_11_1_EARLY_COMPLETION_SUPPORT_FLAG_CONFLICT");
    }
    return {
      earlyProductCompletionSupported: true,
      earlyProductCompletionSchemaVersion: PR8111_EARLY_COMPLETION_SCHEMA_VERSION,
      readOnlyCharacterization: true,
      composerPollIntervalMs: PR8111_COMPOSER_POLL_INTERVAL_MS,
      changesWriteSemantics: false,
      changesCanonicalFinality: false
    };
  }

  if (message?.characterizeEarlyProductCompletion === true) {
    if (_pr8111QueryConflict(message)) {
      throw new Error("PR8_11_1_EARLY_COMPLETION_QUERY_FLAG_CONFLICT");
    }
    const expectedLeaseId = _pr8111LeaseId(message?.expectedBrowserAuthorityLeaseId);
    if (expectedLeaseId === null) {
      throw new Error("PR8_11_1_EARLY_COMPLETION_EXPECTED_LEASE_REQUIRED");
    }
    const record = await _pr8111StoredRecord();
    if (record === null) {
      throw new Error("PR8_11_1_EARLY_COMPLETION_RECORD_NOT_AVAILABLE");
    }
    if (_pr8111LeaseId(record.browserAuthorityLeaseId) !== expectedLeaseId) {
      throw new Error("PR8_11_1_EARLY_COMPLETION_RECORD_LEASE_MISMATCH");
    }
    return {
      earlyProductCompletionSupported: true,
      earlyProductCompletion: record
    };
  }

  const leaseId = _pr8111LeaseId(message?.browserAuthorityLeaseId);
  const ordinaryWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  if (!ordinaryWrite) return _pr8111PriorExecuteNativeTurn(message);
  if (_pr8111Context !== null) {
    throw new Error("PR8_11_1_EARLY_COMPLETION_CONTEXT_ALREADY_ACTIVE");
  }

  const context = {
    leaseId,
    startedAt: performance.now(),
    writeDelegatedAt: null,
    firstAssistantTextObservedAt: null,
    lastAssistantTextObservedAt: null,
    assistantTextObservationCount: 0,
    assistantFinishReasonAt: null,
    assistantFinishReason: null,
    assistantEndTurnAt: null,
    assistantIsCompleteAt: null,
    assistantCompletedStatusAt: null,
    assistantCompletedStatus: null,
    messageMarkerAt: null,
    streamHandoffAt: null,
    doneSentinelAt: null,
    firstComposerReadyAfterTextAt: null,
    consecutiveComposerReadyAfterTextAt: null,
    composerProbeCount: 0,
    composerProbeErrorCount: 0,
    networkCompleteAt: null,
    officialPageTurnCompleteAt: null,
    stopComposerPoll: false,
    characterizationErrorCount: 0
  };
  _pr8111Context = context;

  try {
    const result = await _pr8111PriorExecuteNativeTurn(message);
    const record = _pr8111Record(context);
    try {
      await chrome.storage.local.set({
        [PR8111_EARLY_COMPLETION_STORAGE_KEY]: record
      });
    } catch {
      // Characterization persistence must never change a successful turn.
    }
    return result;
  } finally {
    _pr8111Context = null;
  }
};
