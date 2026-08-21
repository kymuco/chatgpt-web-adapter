// PR8.11: bounded post-answer tail latency attribution.
//
// Observability only. This layer records numeric timing boundaries for one
// leased ordinary product turn and never changes prompt insertion, submit,
// model selection, Browser Authority, canonical finality, or retry behavior.
// Raw assistant text, raw SSE, request bodies, cookies and auth material are
// never persisted or returned by this surface.

const PR811_TAIL_TIMING_SCHEMA_VERSION = 1;
const PR811_TAIL_TIMING_STORAGE_KEY = "browserAuthorityLastPostAnswerTailTimingV1";

const _pr811TailPriorRecordAssistant = _pr89BrowserStreamRecordAssistant;
const _pr811TailPriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr811TailPriorExecuteNativeTurn = executeNativeTurn;

let _pr811TailContext = null;

function _pr811TailLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr811TailDurationMs(startedAt, endedAt) {
  if (!Number.isFinite(startedAt) || !Number.isFinite(endedAt) || endedAt < startedAt) {
    return null;
  }
  return Math.max(0, Math.round(endedAt - startedAt));
}

function _pr811TailQueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true
  );
}

_pr89BrowserStreamRecordAssistant = async function _pr811RecordAssistantTailTiming(
  context,
  candidate
) {
  const text = candidate?.text;
  const key = candidate?.messageKey;
  const previous = (
    context?.lastTextByKey instanceof Map && typeof key === "string"
  ) ? context.lastTextByKey.get(key) : undefined;

  await _pr811TailPriorRecordAssistant(context, candidate);

  const active = _pr811TailContext;
  if (
    active === null ||
    typeof text !== "string" ||
    typeof key !== "string" ||
    !key ||
    previous === text
  ) {
    return;
  }
  active.lastAssistantTextObservedAt = performance.now();
  active.assistantTextObservationCount += 1;
};

executeOfficialPageTurn = async function _executeOfficialPageTurnWithPostAnswerTailTiming(args) {
  const context = _pr811TailContext;
  if (context === null) {
    return _pr811TailPriorExecuteOfficialPageTurn(args);
  }

  const tabId = args?.tabId;
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
          context.writeDelegatedAt = performance.now();
        }
        return;
      }
      if (
        conversationRequestId !== null &&
        params?.requestId === conversationRequestId &&
        method === "Network.loadingFinished"
      ) {
        context.networkCompleteAt = performance.now();
      }
    } catch {
      // Timing observability must never perturb the product write.
    }
  };

  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  try {
    return await _pr811TailPriorExecuteOfficialPageTurn(args);
  } finally {
    context.nativeCompleteAt = performance.now();
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Observability cleanup only.
      }
    }
  }
};

async function _pr811StoredTailTimingRecord() {
  try {
    const stored = await chrome.storage.local.get(PR811_TAIL_TIMING_STORAGE_KEY);
    const value = stored?.[PR811_TAIL_TIMING_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

executeNativeTurn = async function _executeNativeTurnWithPostAnswerTailTiming(message) {
  if (message?.characterizePostAnswerTailTimingSupport === true) {
    if (_pr811TailQueryConflict(message)) {
      throw new Error("PR8_11_TAIL_TIMING_SUPPORT_FLAG_CONFLICT");
    }
    return {
      postAnswerTailTimingSupported: true,
      postAnswerTailTimingSchemaVersion: PR811_TAIL_TIMING_SCHEMA_VERSION,
      numericOnly: true,
      changesWriteSemantics: false
    };
  }

  if (message?.characterizePostAnswerTailTiming === true) {
    if (_pr811TailQueryConflict(message)) {
      throw new Error("PR8_11_TAIL_TIMING_QUERY_FLAG_CONFLICT");
    }
    const expectedLeaseId = _pr811TailLeaseId(
      message?.expectedBrowserAuthorityLeaseId
    );
    if (expectedLeaseId === null) {
      throw new Error("PR8_11_TAIL_TIMING_EXPECTED_LEASE_REQUIRED");
    }
    const record = await _pr811StoredTailTimingRecord();
    if (record === null) {
      throw new Error("PR8_11_TAIL_TIMING_RECORD_NOT_AVAILABLE");
    }
    if (_pr811TailLeaseId(record.browserAuthorityLeaseId) !== expectedLeaseId) {
      throw new Error("PR8_11_TAIL_TIMING_RECORD_LEASE_MISMATCH");
    }
    return {
      postAnswerTailTimingSupported: true,
      postAnswerTailTiming: record
    };
  }

  const leaseId = _pr811TailLeaseId(message?.browserAuthorityLeaseId);
  const ordinaryWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  if (!ordinaryWrite) {
    return _pr811TailPriorExecuteNativeTurn(message);
  }
  if (_pr811TailContext !== null) {
    throw new Error("PR8_11_TAIL_TIMING_CONTEXT_ALREADY_ACTIVE");
  }

  const context = {
    leaseId,
    startedAt: performance.now(),
    writeDelegatedAt: null,
    lastAssistantTextObservedAt: null,
    networkCompleteAt: null,
    nativeCompleteAt: null,
    assistantTextObservationCount: 0
  };
  _pr811TailContext = context;

  try {
    const result = await _pr811TailPriorExecuteNativeTurn(message);
    const record = {
      schemaVersion: PR811_TAIL_TIMING_SCHEMA_VERSION,
      browserAuthorityLeaseId: leaseId,
      assistantTextObservationCount: context.assistantTextObservationCount,
      writeDelegatedMs: _pr811TailDurationMs(context.startedAt, context.writeDelegatedAt),
      lastAssistantTextObservedMs: _pr811TailDurationMs(
        context.startedAt,
        context.lastAssistantTextObservedAt
      ),
      networkCompleteMs: _pr811TailDurationMs(context.startedAt, context.networkCompleteAt),
      nativeCompleteMs: _pr811TailDurationMs(context.startedAt, context.nativeCompleteAt),
      lastTextToNetworkCompleteMs: _pr811TailDurationMs(
        context.lastAssistantTextObservedAt,
        context.networkCompleteAt
      ),
      networkCompleteToNativeCompleteMs: _pr811TailDurationMs(
        context.networkCompleteAt,
        context.nativeCompleteAt
      ),
      lastTextToNativeCompleteMs: _pr811TailDurationMs(
        context.lastAssistantTextObservedAt,
        context.nativeCompleteAt
      )
    };
    try {
      await chrome.storage.local.set({
        [PR811_TAIL_TIMING_STORAGE_KEY]: record
      });
    } catch {
      // Optional observability must not change a successful turn.
    }
    return result;
  } finally {
    _pr811TailContext = null;
  }
};
