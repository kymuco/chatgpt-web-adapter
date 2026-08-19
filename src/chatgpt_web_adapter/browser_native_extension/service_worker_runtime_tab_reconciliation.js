importScripts("service_worker_observability.js");

const _pr824a3RawStoredRuntimeTabId = storedRuntimeTabId;
let _pr824a3ValidationInFlight = null;

async function _pr824a3ClearStoredRuntimeTabIdIfMatches(expectedTabId) {
  const current = await _pr824a3RawStoredRuntimeTabId();
  if (current !== expectedTabId) return false;
  await chrome.storage.local.remove(RUNTIME_TAB_KEY);
  postNative({
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "runtime_state",
    runtimeTabId: null
  });
  return true;
}

async function _pr824a3ValidateStoredRuntimeTab() {
  if (_pr824a3ValidationInFlight !== null) return _pr824a3ValidationInFlight;

  _pr824a3ValidationInFlight = (async () => {
    const storedId = await _pr824a3RawStoredRuntimeTabId();
    if (!Number.isInteger(storedId)) {
      return { tabId: null, valid: false, stale: false };
    }

    try {
      const tab = await chrome.tabs.get(storedId);
      if (isChatGPTUrl(tab?.url || "")) {
        return { tabId: storedId, valid: true, stale: false };
      }
    } catch {
      // Missing Chrome tab is stale persistent state.
    }

    const cleared = await _pr824a3ClearStoredRuntimeTabIdIfMatches(storedId);
    if (!cleared) {
      const replacementId = await _pr824a3RawStoredRuntimeTabId();
      if (Number.isInteger(replacementId)) {
        try {
          const replacement = await chrome.tabs.get(replacementId);
          if (isChatGPTUrl(replacement?.url || "")) {
            return { tabId: replacementId, valid: true, stale: false };
          }
        } catch {
          // A concurrent replacement also went stale; the next read repairs it.
        }
      }
    }
    return { tabId: null, valid: false, stale: true };
  })();

  try {
    return await _pr824a3ValidationInFlight;
  } finally {
    _pr824a3ValidationInFlight = null;
  }
}

storedRuntimeTabId = async function _storedRuntimeTabIdWithLiveValidation() {
  const state = await _pr824a3ValidateStoredRuntimeTab();
  return state.tabId;
};

async function _pr824a3PublishValidatedRuntimeState() {
  const state = await _pr824a3ValidateStoredRuntimeTab();
  if (!state.stale) {
    postNative({
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "runtime_state",
      runtimeTabId: state.tabId
    });
  }
  return state;
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (typeof changeInfo?.url !== "string") return;
  _pr824a3RawStoredRuntimeTabId().then(async (storedId) => {
    if (storedId !== tabId) return;
    const nextUrl = changeInfo.url || tab?.url || "";
    if (isChatGPTUrl(nextUrl)) return;
    await _pr824a3ClearStoredRuntimeTabIdIfMatches(tabId);
  }).catch(() => {});
});

chrome.tabs.onReplaced.addListener((addedTabId, removedTabId) => {
  _pr824a3RawStoredRuntimeTabId().then(async (storedId) => {
    if (storedId !== removedTabId) return;
    try {
      const replacement = await chrome.tabs.get(addedTabId);
      if (isChatGPTUrl(replacement?.url || "")) {
        await storeRuntimeTabId(addedTabId);
        return;
      }
    } catch {
      // Fall through to clearing the stale removed id.
    }
    await _pr824a3ClearStoredRuntimeTabIdIfMatches(removedTabId);
  }).catch(() => {});
});

_pr824a3PublishValidatedRuntimeState().catch(() => {});

// PR8.8 Browser Authority Lease fencing, CLOSE, and read-only live characterization.
const PR88_BROWSER_AUTHORITY_LEASE_KEY = "browserNativeRuntimeTabAuthorityLeaseId";
const PR88_RESOURCE_SAMPLE_MIN_MS = 1000;
const PR88_RESOURCE_SAMPLE_MAX_MS = 15000;
const _pr88PriorExecuteNativeTurn = executeNativeTurn;
const _pr88PriorOnNativeMessage = onNativeMessage;

function _pr88LeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

async function _pr88StoredLeaseId() {
  const value = await chrome.storage.local.get(PR88_BROWSER_AUTHORITY_LEASE_KEY);
  return _pr88LeaseId(value?.[PR88_BROWSER_AUTHORITY_LEASE_KEY]);
}

async function _pr88StoreLeaseId(leaseId) {
  await chrome.storage.local.set({
    [PR88_BROWSER_AUTHORITY_LEASE_KEY]: leaseId
  });
}

async function _pr88ClearLeaseIdIfMatches(expectedLeaseId) {
  const current = await _pr88StoredLeaseId();
  if (current !== expectedLeaseId) return false;
  await chrome.storage.local.remove(PR88_BROWSER_AUTHORITY_LEASE_KEY);
  return true;
}

function _pr88FiniteMetric(value) {
  return Number.isFinite(value) ? Number(value) : null;
}

function _pr88MetricValue(metrics, name) {
  const entry = Array.isArray(metrics)
    ? metrics.find((metric) => metric?.name === name)
    : null;
  return _pr88FiniteMetric(entry?.value);
}

async function _pr88PerformanceSnapshot(debuggee) {
  const performanceMetrics = await chrome.debugger.sendCommand(
    debuggee,
    "Performance.getMetrics"
  );
  let dom = null;
  try {
    dom = await chrome.debugger.sendCommand(debuggee, "Memory.getDOMCounters");
  } catch {
    dom = null;
  }
  const metrics = Array.isArray(performanceMetrics?.metrics)
    ? performanceMetrics.metrics
    : [];
  return {
    taskDurationS: _pr88MetricValue(metrics, "TaskDuration"),
    jsHeapUsedBytes: _pr88MetricValue(metrics, "JSHeapUsedSize"),
    jsHeapTotalBytes: _pr88MetricValue(metrics, "JSHeapTotalSize"),
    documents: Number.isInteger(dom?.documents)
      ? dom.documents
      : _pr88MetricValue(metrics, "Documents"),
    nodes: Number.isInteger(dom?.nodes)
      ? dom.nodes
      : _pr88MetricValue(metrics, "Nodes"),
    jsEventListeners: Number.isInteger(dom?.jsEventListeners)
      ? dom.jsEventListeners
      : _pr88MetricValue(metrics, "JSEventListeners")
  };
}

async function _pr88CharacterizationStatus(message) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error("PR8_8_CHARACTERIZATION_STATUS_FLAG_CONFLICT");
  }
  const runtimeTabId = await storedRuntimeTabId();
  return {
    probeContext: "browser_authority_characterization_support",
    characterizationSupported: true,
    resourceSamplingSupported: true,
    runtimeTabReleaseSupported: true,
    runtimeTabId,
    leaseIdPresent: (await _pr88StoredLeaseId()) !== null,
    readOnly: true
  };
}

async function _pr88SampleRuntimeTabResources(message) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error("PR8_8_RESOURCE_SAMPLE_FLAG_CONFLICT");
  }

  const requested = Number(message?.sampleMs);
  const sampleMs = Number.isFinite(requested)
    ? Math.max(
        PR88_RESOURCE_SAMPLE_MIN_MS,
        Math.min(PR88_RESOURCE_SAMPLE_MAX_MS, Math.round(requested))
      )
    : 5000;
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    throw new Error("PR8_8_RESOURCE_SAMPLE_RUNTIME_TAB_REQUIRED");
  }

  const tabBefore = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tabBefore?.url || "")) {
    throw new Error("PR8_8_RESOURCE_SAMPLE_RUNTIME_TAB_NOT_CHATGPT");
  }

  const debuggee = { tabId: runtimeTabId };
  const activatedTabIds = new Set();
  const onActivated = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) {
      activatedTabIds.add(activeInfo.tabId);
    }
  };

  let attached = false;
  const startedAt = performance.now();
  chrome.tabs.onActivated.addListener(onActivated);

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Performance.enable");
    const start = await _pr88PerformanceSnapshot(debuggee);
    await sleep(sampleMs);
    const end = await _pr88PerformanceSnapshot(debuggee);
    const tabAfter = await chrome.tabs.get(runtimeTabId);
    const tabActiveAfter = Boolean(tabAfter?.active);
    const observedSampleMs = elapsedMs(startedAt);
    const taskDelta = (
      start.taskDurationS !== null &&
      end.taskDurationS !== null &&
      end.taskDurationS >= start.taskDurationS
    )
      ? end.taskDurationS - start.taskDurationS
      : null;
    const taskFraction = taskDelta !== null && observedSampleMs > 0
      ? Math.max(0, taskDelta / (observedSampleMs / 1000))
      : null;

    return {
      probeContext: "browser_authority_runtime_tab_idle_resources",
      readOnly: true,
      runtimeTabId,
      requestedSampleMs: sampleMs,
      observedSampleMs,
      taskDurationStartS: start.taskDurationS,
      taskDurationEndS: end.taskDurationS,
      taskDurationDeltaS: taskDelta,
      taskTimeFraction: taskFraction,
      jsHeapUsedStartBytes: start.jsHeapUsedBytes,
      jsHeapUsedEndBytes: end.jsHeapUsedBytes,
      jsHeapUsedMaxBytes: (
        start.jsHeapUsedBytes !== null && end.jsHeapUsedBytes !== null
      )
        ? Math.max(start.jsHeapUsedBytes, end.jsHeapUsedBytes)
        : (start.jsHeapUsedBytes ?? end.jsHeapUsedBytes),
      jsHeapTotalStartBytes: start.jsHeapTotalBytes,
      jsHeapTotalEndBytes: end.jsHeapTotalBytes,
      documentsStart: Number.isInteger(start.documents) ? start.documents : null,
      documentsEnd: Number.isInteger(end.documents) ? end.documents : null,
      nodesStart: Number.isInteger(start.nodes) ? start.nodes : null,
      nodesEnd: Number.isInteger(end.nodes) ? end.nodes : null,
      jsEventListenersStart: Number.isInteger(start.jsEventListeners)
        ? start.jsEventListeners
        : null,
      jsEventListenersEnd: Number.isInteger(end.jsEventListeners)
        ? end.jsEventListeners
        : null,
      tabWasActive: Boolean(tabBefore?.active),
      tabActiveAfter,
      tabActivatedDuringSample: activatedTabIds.has(runtimeTabId),
      foregroundActivationObserved: Boolean(
        tabBefore?.active ||
        tabActiveAfter === true ||
        activatedTabIds.has(runtimeTabId)
      )
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Runtime tab may have disappeared during diagnostics.
      }
    }
    chrome.tabs.onActivated.removeListener(onActivated);
  }
}

executeNativeTurn = async function _executeNativeTurnWithBrowserAuthorityLease(message) {
  if (message?.characterizeBrowserAuthorityStatus === true) {
    return _pr88CharacterizationStatus(message);
  }
  if (message?.characterizeBrowserAuthorityResources === true) {
    const result = await _pr88SampleRuntimeTabResources(message);
    let debuggerAttachedAfter = null;
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === result.runtimeTabId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
    return {
      ...result,
      debuggerAttachedAfter
    };
  }

  const leaseId = _pr88LeaseId(message?.browserAuthorityLeaseId);
  if (leaseId !== null) {
    await _pr88StoreLeaseId(leaseId);
  }

  const result = await _pr88PriorExecuteNativeTurn(message);
  return {
    ...result,
    browserAuthorityLeaseId: leaseId
  };
};

async function _pr88ReleaseRuntimeTab(message) {
  const requestLeaseId = _pr88LeaseId(message?.browserAuthorityLeaseId);
  if (requestLeaseId === null) {
    throw new Error("BROWSER_NATIVE_AUTHORITY_LEASE_REQUIRED");
  }

  const storedLeaseId = await _pr88StoredLeaseId();
  if (storedLeaseId !== requestLeaseId) {
    throw new Error("BROWSER_NATIVE_AUTHORITY_LEASE_CHANGED");
  }

  const expectedTabId = Number.isInteger(message?.expectedRuntimeTabId)
    ? message.expectedRuntimeTabId
    : null;
  const storedTabId = await storedRuntimeTabId();

  if (storedTabId == null) {
    await _pr88ClearLeaseIdIfMatches(requestLeaseId);
    return {
      released: false,
      alreadyAbsent: true,
      runtimeTabId: null,
      browserAuthorityLeaseId: requestLeaseId
    };
  }

  if (expectedTabId !== null && storedTabId !== expectedTabId) {
    throw new Error("BROWSER_NATIVE_RUNTIME_TAB_CHANGED");
  }

  let tab;
  try {
    tab = await chrome.tabs.get(storedTabId);
  } catch {
    await _pr824a3ClearStoredRuntimeTabIdIfMatches(storedTabId);
    await _pr88ClearLeaseIdIfMatches(requestLeaseId);
    return {
      released: false,
      alreadyAbsent: true,
      runtimeTabId: null,
      browserAuthorityLeaseId: requestLeaseId
    };
  }

  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("BROWSER_NATIVE_RUNTIME_TAB_NOT_CHATGPT");
  }

  const finalLeaseId = await _pr88StoredLeaseId();
  const finalTabId = await storedRuntimeTabId();
  if (finalLeaseId !== requestLeaseId) {
    throw new Error("BROWSER_NATIVE_AUTHORITY_LEASE_CHANGED");
  }
  if (finalTabId !== storedTabId) {
    throw new Error("BROWSER_NATIVE_RUNTIME_TAB_CHANGED");
  }

  await chrome.tabs.remove(storedTabId);
  await _pr824a3ClearStoredRuntimeTabIdIfMatches(storedTabId);
  await _pr88ClearLeaseIdIfMatches(requestLeaseId);

  return {
    released: true,
    alreadyAbsent: false,
    runtimeTabId: storedTabId,
    browserAuthorityLeaseId: requestLeaseId
  };
}

onNativeMessage = async function _onNativeMessageWithBrowserAuthorityLease(message, port) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION) return;
  if (message?.type !== "release_runtime_tab") {
    return _pr88PriorOnNativeMessage(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (activeRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "release_runtime_tab_result",
      request_id: requestId,
      ok: false,
      error: "BROWSER_NATIVE_EXTENSION_BUSY"
    });
    return;
  }

  activeRequestId = requestId;
  try {
    const result = await _pr88ReleaseRuntimeTab(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "release_runtime_tab_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "release_runtime_tab_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  } finally {
    activeRequestId = null;
  }
};
