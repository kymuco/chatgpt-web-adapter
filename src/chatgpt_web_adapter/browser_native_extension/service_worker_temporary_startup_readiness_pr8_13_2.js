// PR8.13.2: fresh Temporary startup-readiness stabilization and abort diagnostics.
//
// This layer is deliberately non-authoritative. It may delay a fresh Temporary
// submit while the newly-created product page stabilizes, but it never grants
// Temporary write authority. The PR8.13 Fetch-paused proof of the page-generated
// request (`history_and_training_disabled === true`) remains the only prewrite
// authority gate.

const PR8132_FRESH_READINESS_TIMEOUT_MS = 5_000;
const PR8132_FRESH_READINESS_STABLE_MS = 750;
const PR8132_FRESH_READINESS_POLL_MS = 125;
const PR8132_FRESH_READINESS_REQUIRED_SAMPLES = 3;

const _pr8132PriorSubmitOfficialPageTurn = submitOfficialPageTurn;
const _pr8132PriorResolveProof = _pr813ResolveProof;
const _pr8132PriorRejectProof = _pr813RejectProof;
const _pr8132PriorExecuteNativeTurn = executeNativeTurn;

const _pr8132TurnDiagnostics = new Map();

function _pr8132ContextToken(context) {
  return _pr813TemporaryToken(context?.token);
}

function _pr8132UpdateDiagnostic(context, patch) {
  const token = _pr8132ContextToken(context);
  if (!token) return;
  const current = _pr8132TurnDiagnostics.get(token) || {};
  _pr8132TurnDiagnostics.set(token, {
    ...current,
    ...patch,
    pausedConversationWriteCount: Number.isInteger(context?.pausedConversationWriteCount)
      ? context.pausedConversationWriteCount
      : (current.pausedConversationWriteCount ?? 0),
    modeViolation: typeof context?.modeViolation === "string"
      ? context.modeViolation
      : (current.modeViolation ?? null),
  });
}

function _pr8132TemporaryUrlHint(url) {
  try {
    const parsed = new URL(url);
    return parsed.origin === CHATGPT_ORIGIN &&
      parsed.searchParams.get("temporary-chat") === "true";
  } catch {
    return false;
  }
}

async function _pr8132TemporaryControlHint(debuggee) {
  if (typeof _pr87TemporaryControlSnapshot !== "function") {
    return {
      available: false,
      controlFound: false,
      ambiguous: false,
      selected: null,
    };
  }
  try {
    const snapshot = await _pr87TemporaryControlSnapshot(debuggee);
    return {
      available: true,
      controlFound: snapshot?.controlFound === true,
      ambiguous: snapshot?.ambiguous === true,
      selected: typeof snapshot?.selected === "boolean" ? snapshot.selected : null,
    };
  } catch {
    return {
      available: false,
      controlFound: false,
      ambiguous: false,
      selected: null,
    };
  }
}

async function _pr8132FreshReadinessSample(debuggee) {
  let tab;
  try {
    tab = await chrome.tabs.get(debuggee.tabId);
  } catch {
    return {
      readyHint: false,
      reason: "temporary_tab_unavailable",
      urlTemporaryQueryTrue: false,
      composerReady: false,
      controlAvailable: false,
      controlFound: false,
      controlAmbiguous: false,
      controlSelected: null,
    };
  }

  let composer = { ready: false, reason: "composer_probe_failed" };
  try {
    composer = await queryComposerReadiness(debuggee);
  } catch {
    // Keep the readiness hint fail-closed. The authoritative Fetch proof has not
    // run yet and no product write is submitted from this probe.
  }

  const control = await _pr8132TemporaryControlHint(debuggee);
  const urlTemporaryQueryTrue = _pr8132TemporaryUrlHint(tab?.url || "");
  const explicitControlFalse = Boolean(
    control.available &&
    control.controlFound &&
    !control.ambiguous &&
    control.selected === false
  );
  const readyHint = Boolean(
    urlTemporaryQueryTrue &&
    composer?.ready === true &&
    !explicitControlFalse
  );

  let reason = "ready_hint";
  if (!urlTemporaryQueryTrue) reason = "temporary_url_hint_missing";
  else if (composer?.ready !== true) reason = `composer_${composer?.reason || "not_ready"}`;
  else if (explicitControlFalse) reason = "temporary_control_explicitly_false";

  return {
    readyHint,
    reason,
    urlTemporaryQueryTrue,
    composerReady: composer?.ready === true,
    controlAvailable: control.available,
    controlFound: control.controlFound,
    controlAmbiguous: control.ambiguous,
    controlSelected: control.selected,
  };
}

async function _pr8132WaitForFreshTemporaryReadiness(debuggee, timeoutMs) {
  const startedAt = performance.now();
  const budgetMs = Math.min(
    PR8132_FRESH_READINESS_TIMEOUT_MS,
    Math.max(1_000, Number.isFinite(timeoutMs) ? timeoutMs : PR8132_FRESH_READINESS_TIMEOUT_MS)
  );
  let stableStartedAt = null;
  let consecutiveReady = 0;
  let last = {
    readyHint: false,
    reason: "not_sampled",
    urlTemporaryQueryTrue: false,
    composerReady: false,
    controlAvailable: false,
    controlFound: false,
    controlAmbiguous: false,
    controlSelected: null,
  };

  while (performance.now() - startedAt < budgetMs) {
    last = await _pr8132FreshReadinessSample(debuggee);
    if (!last.readyHint) {
      stableStartedAt = null;
      consecutiveReady = 0;
    } else {
      if (stableStartedAt === null) stableStartedAt = performance.now();
      consecutiveReady += 1;
      const stableMs = Math.round(performance.now() - stableStartedAt);
      const explicitSelected = Boolean(
        last.controlAvailable &&
        last.controlFound &&
        !last.controlAmbiguous &&
        last.controlSelected === true
      );

      if (explicitSelected && consecutiveReady >= 2) {
        return {
          kind: "TEMPORARY_CONTROL_SELECTED_STABLE",
          waitMs: Math.round(performance.now() - startedAt),
          stableMs,
          consecutiveReady,
          ...last,
        };
      }

      if (
        consecutiveReady >= PR8132_FRESH_READINESS_REQUIRED_SAMPLES &&
        stableMs >= PR8132_FRESH_READINESS_STABLE_MS
      ) {
        return {
          kind: "TEMPORARY_URL_COMPOSER_STABLE_HINT",
          waitMs: Math.round(performance.now() - startedAt),
          stableMs,
          consecutiveReady,
          ...last,
        };
      }
    }
    await sleep(PR8132_FRESH_READINESS_POLL_MS);
  }

  throw new Error(
    `PR8_13_2_TEMPORARY_FRESH_READINESS_TIMEOUT:${last.reason || "unknown"}`
  );
}

_pr813ResolveProof = function _pr8132ResolveProofWithDiagnostics(context, evidence) {
  _pr8132UpdateDiagnostic(context, {
    prewriteProofKind: typeof evidence?.proofKind === "string" ? evidence.proofKind : null,
    prewriteProofResolved: true,
  });
  return _pr8132PriorResolveProof(context, evidence);
};

_pr813RejectProof = function _pr8132RejectProofWithDiagnostics(context, error) {
  _pr8132UpdateDiagnostic(context, {
    prewriteProofRejected: true,
    proofError: error instanceof Error ? error.message : String(error),
  });
  return _pr8132PriorRejectProof(context, error);
};

submitOfficialPageTurn = async function _pr8132SubmitOfficialPageTurn(debuggee, timeoutMs) {
  const context = _pr813TemporaryTurnContext;
  if (context === null || debuggee?.tabId !== context.tabId) {
    return _pr8132PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
  }

  if (context.expectedConversationId === null) {
    const readiness = await _pr8132WaitForFreshTemporaryReadiness(debuggee, timeoutMs);
    context.pr8132FreshReadiness = readiness;
    _pr8132UpdateDiagnostic(context, {
      freshReadinessApplied: true,
      freshReadinessKind: readiness.kind,
      freshReadinessWaitMs: readiness.waitMs,
      freshReadinessStableMs: readiness.stableMs,
      freshReadinessControlSelected: readiness.controlSelected,
      freshReadinessUrlQueryTrue: readiness.urlTemporaryQueryTrue,
    });
  } else {
    _pr8132UpdateDiagnostic(context, {
      freshReadinessApplied: false,
    });
  }

  return _pr8132PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
};

function _pr8132AbortError(error, diagnostic) {
  const message = error instanceof Error ? error.message : String(error);
  if (!message.includes("CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED")) {
    return null;
  }

  if (typeof diagnostic?.modeViolation === "string" && diagnostic.modeViolation) {
    return new Error(
      `PR8_13_2_TEMPORARY_PREWRITE_ABORT:${diagnostic.modeViolation}:${message}`
    );
  }
  if (typeof diagnostic?.prewriteProofKind === "string" && diagnostic.prewriteProofKind) {
    return new Error(
      `PR8_13_2_TEMPORARY_ABORT_AFTER_PREWRITE_PROOF:${diagnostic.prewriteProofKind}:${message}`
    );
  }
  if ((diagnostic?.pausedConversationWriteCount ?? 0) > 0) {
    return new Error(
      `PR8_13_2_TEMPORARY_ABORT_WITHOUT_RETAINED_PROOF:paused=${diagnostic.pausedConversationWriteCount}:${message}`
    );
  }
  return new Error(
    `PR8_13_2_TEMPORARY_ABORT_BEFORE_FETCH_OBSERVATION:${message}`
  );
}

executeNativeTurn = async function _pr8132ExecuteNativeTurnWithStartupDiagnostics(message) {
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  if (mode !== "temporary") {
    return _pr8132PriorExecuteNativeTurn(message);
  }

  const token = _pr813TemporaryToken(message?.temporaryLifecycleToken);
  if (token) _pr8132TurnDiagnostics.set(token, {});

  try {
    const result = await _pr8132PriorExecuteNativeTurn(message);
    if (!result || typeof result !== "object") return result;
    const diagnostic = token ? (_pr8132TurnDiagnostics.get(token) || {}) : {};
    return {
      ...result,
      temporaryFreshReadinessApplied: diagnostic.freshReadinessApplied === true,
      temporaryFreshReadinessKind: typeof diagnostic.freshReadinessKind === "string"
        ? diagnostic.freshReadinessKind
        : null,
      temporaryFreshReadinessWaitMs: Number.isInteger(diagnostic.freshReadinessWaitMs)
        ? diagnostic.freshReadinessWaitMs
        : null,
      temporaryFreshReadinessStableMs: Number.isInteger(diagnostic.freshReadinessStableMs)
        ? diagnostic.freshReadinessStableMs
        : null,
      temporaryFreshReadinessControlSelected: typeof diagnostic.freshReadinessControlSelected === "boolean"
        ? diagnostic.freshReadinessControlSelected
        : null,
      temporaryFreshReadinessUrlQueryTrue: diagnostic.freshReadinessUrlQueryTrue === true,
    };
  } catch (error) {
    const diagnostic = token ? (_pr8132TurnDiagnostics.get(token) || {}) : {};
    const enriched = _pr8132AbortError(error, diagnostic);
    if (enriched) throw enriched;
    throw error;
  } finally {
    if (token) _pr8132TurnDiagnostics.delete(token);
  }
};
