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
