const _cwaUiLivenessPriorOnNativeMessage = onNativeMessage;
let _cwaUiLivenessProbeActive = false;
let _cwaUiLivenessProbePromise = null;

function _cwaUiLivenessBase(state, reasonCode, extra = {}) {
  return {
    state,
    reasonCode,
    observedAtMs: Date.now(),
    bridgeAvailable: true,
    extensionConnected: true,
    runtimeTabPresent: null,
    composerVisible: null,
    generationControlVisible: null,
    composerBusy: null,
    rawDomExported: false,
    navigationPerformed: false,
    runtimeTabCreated: false,
    writePerformed: false,
    canonicalReadPerformed: false,
    canonicalFinalityProven: false,
    grantsWriteAuthority: false,
    grantsRetryAuthority: false,
    debuggerAttachedAfter: null,
    ...extra
  };
}

function _cwaUiLivenessRejectWriteBearingFields(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  );
}

async function _cwaUiLivenessExistingRuntimeTab() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) return null;
  try {
    const tab = await chrome.tabs.get(runtimeTabId);
    if (!isChatGPTUrl(tab?.url || "")) return null;
    return tab;
  } catch {
    return null;
  }
}

function _cwaUiLivenessFromComposerReadiness(readiness) {
  const reason = typeof readiness?.reason === "string"
    ? readiness.reason
    : "unknown";
  if (readiness?.ready === true && reason === "ready") {
    return _cwaUiLivenessBase("READY_FOR_INPUT", "COMPOSER_READY", {
      runtimeTabPresent: true,
      composerVisible: true,
      generationControlVisible: false,
      composerBusy: false
    });
  }
  if (reason === "generation_control_visible") {
    return _cwaUiLivenessBase("GENERATING", "GENERATION_CONTROL_VISIBLE", {
      runtimeTabPresent: true,
      composerVisible: true,
      generationControlVisible: true,
      composerBusy: false
    });
  }
  if (reason === "composer_busy") {
    return _cwaUiLivenessBase("UNKNOWN", "COMPOSER_BUSY", {
      runtimeTabPresent: true,
      composerVisible: true,
      generationControlVisible: false,
      composerBusy: true
    });
  }
  if (reason === "composer_missing") {
    return _cwaUiLivenessBase("UNKNOWN", "COMPOSER_MISSING", {
      runtimeTabPresent: true,
      composerVisible: false,
      generationControlVisible: false,
      composerBusy: null
    });
  }
  return _cwaUiLivenessBase("UNKNOWN", "READINESS_EVIDENCE_UNKNOWN", {
    runtimeTabPresent: true
  });
}

async function _cwaObserveUiLiveness() {
  const tab = await _cwaUiLivenessExistingRuntimeTab();
  if (!tab) {
    return _cwaUiLivenessBase("UNAVAILABLE", "RUNTIME_TAB_ABSENT", {
      runtimeTabPresent: false
    });
  }
  if (activeRequestId !== null) {
    return _cwaUiLivenessBase("UNKNOWN", "ACTIVE_REQUEST_IN_PROGRESS", {
      runtimeTabPresent: true
    });
  }
  if (_cwaUiLivenessProbeActive) {
    return _cwaUiLivenessBase("UNKNOWN", "OBSERVATION_ALREADY_RUNNING", {
      runtimeTabPresent: true
    });
  }
  if (tab.status !== "complete") {
    return _cwaUiLivenessBase("UNKNOWN", "RUNTIME_TAB_LOADING", {
      runtimeTabPresent: true
    });
  }

  const debuggee = { tabId: tab.id };
  let attached = false;
  let detachFailed = false;
  let observation = null;
  _cwaUiLivenessProbeActive = true;
  try {
    try {
      await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
      attached = true;
    } catch {
      return _cwaUiLivenessBase("UNKNOWN", "DEBUGGER_UNAVAILABLE", {
        runtimeTabPresent: true
      });
    }
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    try {
      const readiness = await queryComposerReadiness(debuggee);
      observation = _cwaUiLivenessFromComposerReadiness(readiness);
    } catch {
      observation = _cwaUiLivenessBase("UNKNOWN", "READINESS_PROBE_FAILED", {
        runtimeTabPresent: true
      });
    }
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        detachFailed = true;
      }
    }
    _cwaUiLivenessProbeActive = false;
    if (observation && detachFailed) {
      observation = _cwaUiLivenessBase("UNKNOWN", "DEBUGGER_DETACH_FAILED", {
        runtimeTabPresent: true,
        debuggerAttachedAfter: true
      });
    } else if (observation) {
      try {
        const targets = await chrome.debugger.getTargets();
        const stillAttached = Boolean(
          targets.find((target) => target.tabId === tab.id)?.attached
        );
        observation.debuggerAttachedAfter = stillAttached;
        if (stillAttached) {
          observation = _cwaUiLivenessBase("UNKNOWN", "DEBUGGER_STILL_ATTACHED", {
            runtimeTabPresent: true,
            debuggerAttachedAfter: true
          });
        }
      } catch {
        observation.debuggerAttachedAfter = null;
      }
    }
  }
  return observation || _cwaUiLivenessBase("UNKNOWN", "READINESS_PROBE_FAILED", {
    runtimeTabPresent: true
  });
}

onNativeMessage = async function _cwaOnNativeMessageWithUiLiveness(message, port) {
  if (
    message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
    message?.type !== "ui_liveness"
  ) {
    const activeProbe = _cwaUiLivenessProbePromise;
    if (activeProbe) {
      try { await activeProbe; } catch {}
    }
    return _cwaUiLivenessPriorOnNativeMessage(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (_cwaUiLivenessRejectWriteBearingFields(message)) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "ui_liveness_result",
      request_id: requestId,
      ok: false,
      error: "UI_LIVENESS_WRITE_BEARING_FIELDS_FORBIDDEN"
    });
    return;
  }

  let observation;
  const probe = _cwaObserveUiLiveness();
  _cwaUiLivenessProbePromise = probe;
  try {
    observation = await probe;
  } catch {
    observation = _cwaUiLivenessBase("UNKNOWN", "OBSERVATION_PROBE_FAILED", {
      runtimeTabPresent: null
    });
  } finally {
    if (_cwaUiLivenessProbePromise === probe) {
      _cwaUiLivenessProbePromise = null;
    }
  }
  safePortPost(port, {
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "ui_liveness_result",
    request_id: requestId,
    ok: true,
    ...observation
  });
};
