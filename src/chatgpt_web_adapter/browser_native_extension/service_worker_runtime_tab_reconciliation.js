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

// The base worker may already have connected and published a stored integer
// before this wrapper was loaded. Correct broker state immediately from a live
// Chrome validation. Future reconnect hello messages call the wrapped
// storedRuntimeTabId() and therefore cannot republish an unvalidated stale id.
_pr824a3PublishValidatedRuntimeState().catch(() => {});


// PR8.8 Browser Authority Lease fencing and production CLOSE primitive.
//
// This layer is deliberately below the PR8.7 Temporary-specific wrappers.
// Browser Authority Lease identity is generic page/runtime authority metadata;
// it never proves product mode, conversation identity, or Temporary lifecycle.
const PR88_BROWSER_AUTHORITY_LEASE_KEY = "browserNativeRuntimeTabAuthorityLeaseId";
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

executeNativeTurn = async function _executeNativeTurnWithBrowserAuthorityLease(message) {
  const leaseId = _pr88LeaseId(message?.browserAuthorityLeaseId);
  if (leaseId !== null) {
    // Fence stale timers before any page-owned mutation or runtime-tab reuse.
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

  // Recheck both fences immediately before CLOSE.
  const finalLeaseId = await _pr88StoredLeaseId();
  const finalTabId = await storedRuntimeTabId();
  if (finalLeaseId !== requestLeaseId) {
    throw new Error("BROWSER_NATIVE_AUTHORITY_LEASE_CHANGED");
  }
  if (finalTabId !== storedTabId) {
    throw new Error("BROWSER_NATIVE_RUNTIME_TAB_CHANGED");
  }

  await chrome.tabs.remove(storedTabId);

  // The base onRemoved listener normally clears runtime state. Make release
  // result independent of listener scheduling while never clearing a newer tab.
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
