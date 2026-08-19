importScripts("service_worker_hotfix.js");

const STALE_UI_COMPLETION_EVIDENCE_MAX_AGE_MS = 5_000;
const STALE_UI_RELOAD_TIMEOUT_MS = 45_000;
const _pr811OriginalExecuteNativeTurn = executeNativeTurn;

function _pr811FreshCanonicalCompletionEvidence(message) {
  if (message?.canonicalCompleted !== true) return false;
  if (!Number.isFinite(message?.canonicalCompletedAtMs)) return false;
  const ageMs = Date.now() - Number(message.canonicalCompletedAtMs);
  return ageMs >= 0 && ageMs <= STALE_UI_COMPLETION_EVIDENCE_MAX_AGE_MS;
}

async function _pr811ReloadRuntimeTabAndWait(tabId, expectedConversationId) {
  const startedAt = performance.now();
  await new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error = null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      if (error) reject(error);
      else resolve();
    };
    const timer = setTimeout(
      () => finish(new Error("CHATGPT_STALE_UI_RELOAD_TIMEOUT")),
      STALE_UI_RELOAD_TIMEOUT_MS
    );
    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") finish();
    }
    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.reload(tabId).catch((error) => finish(error));
  });

  const reloadedTab = await chrome.tabs.get(tabId);
  const conversationId = conversationIdFromUrl(reloadedTab.url || "");
  if (conversationId !== expectedConversationId) {
    throw new Error("CHATGPT_STALE_UI_RELOAD_CONVERSATION_MISMATCH");
  }
  return Math.round(performance.now() - startedAt);
}

async function _pr811MaybeRecoverStaleRuntimeUi(message) {
  const conversationId = typeof message?.conversationId === "string"
    ? message.conversationId.trim()
    : "";
  if (!conversationId || !_pr811FreshCanonicalCompletionEvidence(message)) {
    return { runtimeReloaded: false, runtimeReloadMs: null };
  }

  const tab = await ensureRuntimeTab(conversationId);
  if (!Number.isInteger(tab?.id)) {
    throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");
  }

  const debuggee = { tabId: tab.id };
  let attached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await sendCommand(debuggee, "Runtime.enable");
    const readiness = await queryComposerReadiness(debuggee);
    if (readiness?.reason !== "generation_control_visible") {
      return { runtimeReloaded: false, runtimeReloadMs: null };
    }
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // The dedicated runtime tab may have closed while probing.
      }
    }
  }

  const runtimeReloadMs = await _pr811ReloadRuntimeTabAndWait(tab.id, conversationId);
  return { runtimeReloaded: true, runtimeReloadMs };
}

executeNativeTurn = async function _executeNativeTurnWithStaleUiRecovery(message) {
  const recovery = await _pr811MaybeRecoverStaleRuntimeUi(message);
  const result = await _pr811OriginalExecuteNativeTurn(message);
  return {
    ...result,
    runtimeReloaded: recovery.runtimeReloaded,
    runtimeReloadMs: recovery.runtimeReloadMs
  };
};
