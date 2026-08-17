importScripts("service_worker_recovery.js");

// PR8.8 phase-level Browser Authority cost attribution.
//
// This layer adds observability only. It is loaded immediately below the
// existing provisioning-observability/lease/Temporary wrappers, so those
// established semantics remain authoritative.
//
// Only bounded numeric timing metadata is retained. No prompt text, cookies,
// raw response bodies, SSE, DOM, or authentication material is stored/exported.

const PR88_PHASE_TIMING_SCHEMA_VERSION = 1;
const PR88_PHASE_TIMING_STORAGE_KEY = "browserAuthorityLastPhaseTimingV1";

const _pr88PhasePriorEnsureRuntimeTab = ensureRuntimeTab;
const _pr88PhasePriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr88PhasePriorExecuteNativeTurn = executeNativeTurn;

let _pr88PhaseTimingContext = null;

function _pr88PhaseLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88PhaseDurationMs(startedAt, endedAt = performance.now()) {
  return Math.max(0, Math.round(endedAt - startedAt));
}

function _pr88PhaseSafeInt(value) {
  return Number.isFinite(value) ? Math.max(0, Math.round(Number(value))) : null;
}

function _pr88PhaseTimingQueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.canonicalCompleted === true ||
    message?.browserAuthorityLeaseId != null ||
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.characterizeManualTemporaryGroundTruth === true ||
    message?.probeTemporaryRouteReopen === true
  );
}

ensureRuntimeTab = async function _ensureRuntimeTabWithPhaseTiming(conversationId) {
  const context = _pr88PhaseTimingContext;
  if (context === null) {
    return _pr88PhasePriorEnsureRuntimeTab(conversationId);
  }

  const startedAt = performance.now();
  try {
    return await _pr88PhasePriorEnsureRuntimeTab(conversationId);
  } finally {
    const durationMs = _pr88PhaseDurationMs(startedAt);
    context.runtimeTabResolveCallCount += 1;
    context.runtimeTabResolveTotalMs += durationMs;
    context.runtimeTabResolveMaxMs = Math.max(
      context.runtimeTabResolveMaxMs,
      durationMs
    );
    if (context.runtimeTabFirstResolveMs === null) {
      context.runtimeTabFirstResolveMs = durationMs;
    }
  }
};

executeOfficialPageTurn = async function _executeOfficialPageTurnWithPhaseTiming(args) {
  const context = _pr88PhaseTimingContext;
  if (context === null) {
    return _pr88PhasePriorExecuteOfficialPageTurn(args);
  }

  const pageStartedAt = performance.now();
  let conversationRequestId = null;
  let delegatedAt = null;
  let networkCompleteAt = null;

  const observer = (source, method, params) => {
    try {
      if (source?.tabId !== args?.tabId) return;
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (
          conversationRequestId === null &&
          isConversationWrite(request?.url || "", request?.method || "")
        ) {
          conversationRequestId = params.requestId;
          delegatedAt = performance.now();
        }
        return;
      }
      if (
        conversationRequestId !== null &&
        params?.requestId === conversationRequestId &&
        method === "Network.loadingFinished"
      ) {
        networkCompleteAt = performance.now();
      }
    } catch {
      // Timing observation must never perturb the proven product write path.
    }
  };

  let listenerInstalled = false;
  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  try {
    return await _pr88PhasePriorExecuteOfficialPageTurn(args);
  } finally {
    const nativeCompleteAt = performance.now();
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Observability cleanup only.
      }
    }

    context.pageTurnElapsedMs = _pr88PhaseDurationMs(
      pageStartedAt,
      nativeCompleteAt
    );
    context.tabReadyToWriteDelegatedMs = delegatedAt === null
      ? null
      : _pr88PhaseDurationMs(pageStartedAt, delegatedAt);
    context.writeDelegatedToNetworkCompleteMs = (
      delegatedAt === null || networkCompleteAt === null
    )
      ? null
      : _pr88PhaseDurationMs(delegatedAt, networkCompleteAt);
    context.networkCompleteToNativeCompleteMs = networkCompleteAt === null
      ? null
      : _pr88PhaseDurationMs(networkCompleteAt, nativeCompleteAt);
    context.writeDelegatedToNativeCompleteMs = delegatedAt === null
      ? null
      : _pr88PhaseDurationMs(delegatedAt, nativeCompleteAt);
  }
};

async function _pr88PhaseTimingRecord() {
  try {
    const stored = await chrome.storage.local.get(PR88_PHASE_TIMING_STORAGE_KEY);
    const value = stored?.[PR88_PHASE_TIMING_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

async function _pr88CharacterizePhaseTiming(message) {
  if (_pr88PhaseTimingQueryConflict(message)) {
    throw new Error("PR8_8_PHASE_TIMING_QUERY_FLAG_CONFLICT");
  }
  const expectedLeaseId = _pr88PhaseLeaseId(
    message?.expectedBrowserAuthorityLeaseId
  );
  if (expectedLeaseId === null) {
    throw new Error("PR8_8_PHASE_TIMING_EXPECTED_LEASE_REQUIRED");
  }

  const record = await _pr88PhaseTimingRecord();
  if (record === null) {
    throw new Error("PR8_8_PHASE_TIMING_RECORD_NOT_AVAILABLE");
  }
  if (_pr88PhaseLeaseId(record.phaseTimingLeaseId) !== expectedLeaseId) {
    throw new Error("PR8_8_PHASE_TIMING_RECORD_LEASE_MISMATCH");
  }

  return {
    probeContext: "browser_authority_phase_timing",
    readOnly: true,
    phaseTimingSupported: true,
    ...record
  };
}

executeNativeTurn = async function _executeNativeTurnWithPhaseTiming(message) {
  if (message?.characterizeBrowserAuthorityPhaseTimingSupport === true) {
    if (_pr88PhaseTimingQueryConflict(message)) {
      throw new Error("PR8_8_PHASE_TIMING_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "browser_authority_phase_timing_support",
      readOnly: true,
      phaseTimingSupported: true,
      phaseTimingSchemaVersion: PR88_PHASE_TIMING_SCHEMA_VERSION
    };
  }

  if (message?.characterizeBrowserAuthorityPhaseTiming === true) {
    return _pr88CharacterizePhaseTiming(message);
  }

  const leaseId = _pr88PhaseLeaseId(message?.browserAuthorityLeaseId);
  const ordinaryProductWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  if (!ordinaryProductWrite) {
    return _pr88PhasePriorExecuteNativeTurn(message);
  }

  const nativeStartedAt = performance.now();
  const context = {
    runtimeTabResolveCallCount: 0,
    runtimeTabFirstResolveMs: null,
    runtimeTabResolveTotalMs: 0,
    runtimeTabResolveMaxMs: 0,
    pageTurnElapsedMs: null,
    tabReadyToWriteDelegatedMs: null,
    writeDelegatedToNetworkCompleteMs: null,
    networkCompleteToNativeCompleteMs: null,
    writeDelegatedToNativeCompleteMs: null
  };
  _pr88PhaseTimingContext = context;

  try {
    const result = await _pr88PhasePriorExecuteNativeTurn(message);
    const nativeTurnElapsedMs = _pr88PhaseDurationMs(nativeStartedAt);
    const runtimeReloaded = result?.runtimeReloaded === true;
    const runtimeReloadMs = runtimeReloaded
      ? _pr88PhaseSafeInt(result?.runtimeReloadMs)
      : null;

    const required = [
      context.runtimeTabFirstResolveMs,
      context.pageTurnElapsedMs,
      context.tabReadyToWriteDelegatedMs,
      context.writeDelegatedToNetworkCompleteMs,
      context.networkCompleteToNativeCompleteMs,
      context.writeDelegatedToNativeCompleteMs
    ];
    const complete = (
      context.runtimeTabResolveCallCount >= 1 &&
      required.every((value) => Number.isInteger(value))
    );

    if (complete) {
      const accountedMs = (
        context.runtimeTabResolveTotalMs +
        context.pageTurnElapsedMs +
        (runtimeReloadMs || 0)
      );
      const record = {
        phaseTimingLeaseId: leaseId,
        phaseTimingSchemaVersion: PR88_PHASE_TIMING_SCHEMA_VERSION,
        runtimeTabResolveCallCount: context.runtimeTabResolveCallCount,
        runtimeTabFirstResolveMs: context.runtimeTabFirstResolveMs,
        runtimeTabResolveTotalMs: context.runtimeTabResolveTotalMs,
        runtimeTabResolveMaxMs: context.runtimeTabResolveMaxMs,
        pageTurnElapsedMs: context.pageTurnElapsedMs,
        tabReadyToWriteDelegatedMs: context.tabReadyToWriteDelegatedMs,
        writeDelegatedToNetworkCompleteMs:
          context.writeDelegatedToNetworkCompleteMs,
        networkCompleteToNativeCompleteMs:
          context.networkCompleteToNativeCompleteMs,
        writeDelegatedToNativeCompleteMs:
          context.writeDelegatedToNativeCompleteMs,
        nativeTurnElapsedMs,
        runtimeReloaded,
        runtimeReloadMs,
        otherNativeOverheadMs: nativeTurnElapsedMs - accountedMs
      };

      // Failure to persist optional observability must not change a successful
      // product write outcome. The live gate will fail later, read-only, if the
      // timing record is unavailable.
      try {
        await chrome.storage.local.set({
          [PR88_PHASE_TIMING_STORAGE_KEY]: record
        });
      } catch {
        // Deliberately ignored: observability must not become write semantics.
      }
    }

    return result;
  } finally {
    _pr88PhaseTimingContext = null;
  }
};
