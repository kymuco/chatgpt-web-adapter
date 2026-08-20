importScripts("service_worker_hotfix.js");

const STALE_UI_COMPLETION_EVIDENCE_MAX_AGE_MS = 5_000;
const STALE_UI_RELOAD_TIMEOUT_MS = 45_000;
const _pr811OriginalExecuteNativeTurn = executeNativeTurn;

// PR8.11.1 installs a per-turn promise here from the later response-stream
// overlay. The core page turn snapshots the promise after submit observation.
// If no later layer installs one, behavior is exactly the prior network-complete
// path. The hook never authorizes a write or a retry.
let _cwaOfficialPageEarlyCompletionSignalPromise = null;

function _cwaInstallOfficialPageEarlyCompletionSignal(promise) {
  const previous = _cwaOfficialPageEarlyCompletionSignalPromise;
  _cwaOfficialPageEarlyCompletionSignalPromise = (
    promise && typeof promise.then === "function"
  ) ? promise : null;
  let restored = false;
  return () => {
    if (restored) return;
    restored = true;
    _cwaOfficialPageEarlyCompletionSignalPromise = previous;
  };
}

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

// PR8.11.1 production repair. This is the current core page-turn implementation
// with one additional fail-closed completion race. A visible assistant terminal
// signal may stop blocking on Network.loadingFinished only when the response is
// already HTTP 200 and the page already exposes a concrete /c/<id> route.
// Otherwise it falls through to the prior network-complete path. Canonical HTTP
// readback remains mandatory in browser_native_client.py after this returns.
executeOfficialPageTurn = async function _executeOfficialPageTurnWithEarlyTerminalBoundary({
  tabId,
  text,
  timeoutMs
}) {
  if (!Number.isInteger(tabId)) throw new Error("TAB_ID_REQUIRED");
  if (typeof text !== "string" || !text.trim()) throw new Error("TEXT_REQUIRED");
  if (text.length > 200_000) throw new Error("TEXT_TOO_LARGE_FOR_BROWSER_NATIVE_TURN");

  const startedAt = performance.now();
  const tab = await chrome.tabs.get(tabId);
  if (!isChatGPTUrl(tab.url || "")) throw new Error("RUNTIME_TAB_IS_NOT_CHATGPT");
  const debuggee = { tabId };
  const diagnostics = {
    tabId,
    tabWasActive: Boolean(tab.active),
    composerStrategy: null,
    submitStrategy: null,
    submitButtonSelector: null,
    submitAckMs: null,
    responseStatus: null,
    responseMimeType: null,
    conversationRequestSeen: false,
    conversationResponseSeen: false,
    loadingFinished: false,
    completionReadyWaitMs: null,
    completionBoundary: null,
    earlyCompletionCandidateSeen: false,
    earlyCompletionAccepted: false,
    earlyCompletionKind: null,
    earlyCompletionRejectedReason: null,
    debuggerAttachedAfter: null,
    elapsedMs: null
  };

  let attached = false;
  let eventListener = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await sendCommand(debuggee, "Network.enable");
    await sendCommand(debuggee, "Runtime.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );

    let conversationRequestId = null;
    let resolveRequestSeen;
    let resolveCompleted;
    let rejectCompleted;
    const requestSeen = new Promise((resolve) => {
      resolveRequestSeen = resolve;
    });
    const completed = new Promise((resolve, reject) => {
      resolveCompleted = resolve;
      rejectCompleted = reject;
    });

    eventListener = (source, method, params) => {
      if (source.tabId !== tabId) return;
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (!conversationRequestId && isConversationWrite(request?.url || "", request?.method || "")) {
          conversationRequestId = params.requestId;
          diagnostics.conversationRequestSeen = true;
          resolveRequestSeen(params.requestId);
        }
        return;
      }
      if (!conversationRequestId || params?.requestId !== conversationRequestId) return;
      if (method === "Network.responseReceived") {
        diagnostics.conversationResponseSeen = true;
        diagnostics.responseStatus = params?.response?.status ?? null;
        diagnostics.responseMimeType = params?.response?.mimeType ?? null;
        return;
      }
      if (method === "Network.loadingFailed") {
        rejectCompleted(new Error(`CHATGPT_CONVERSATION_REQUEST_FAILED:${params?.errorText || "unknown"}`));
        return;
      }
      if (method === "Network.loadingFinished") {
        diagnostics.loadingFinished = true;
        resolveCompleted(conversationRequestId);
      }
    };
    chrome.debugger.onEvent.addListener(eventListener);

    diagnostics.composerStrategy = await locateAndFocusComposer(debuggee);
    await clearComposer(debuggee);
    await sendCommand(debuggee, "Input.insertText", { text });

    const submitStartedAt = performance.now();
    const submit = await submitOfficialPageTurn(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_READY_TIMEOUT_MS)
    );
    diagnostics.submitStrategy = submit.strategy;
    diagnostics.submitButtonSelector = submit.selector;

    await Promise.race([
      requestSeen,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error(`CHATGPT_SUBMIT_NOT_OBSERVED:${submit.strategy}`)),
        Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_ACK_TIMEOUT_MS)
      ))
    ]);
    diagnostics.submitAckMs = elapsedMs(submitStartedAt);

    const earlySignalPromise = _cwaOfficialPageEarlyCompletionSignalPromise;
    const timeoutResult = new Promise((_, reject) => setTimeout(
      () => reject(new Error("CHATGPT_TURN_TIMEOUT")),
      remainingMs(startedAt, timeoutMs)
    ));
    const networkResult = completed.then((requestId) => ({
      kind: "network_complete",
      requestId
    }));
    const firstBoundary = earlySignalPromise
      ? await Promise.race([
          networkResult,
          Promise.resolve(earlySignalPromise).then((signal) => ({
            kind: "assistant_terminal_candidate",
            signal
          })),
          timeoutResult
        ])
      : await Promise.race([networkResult, timeoutResult]);

    let requestId = conversationRequestId;
    let safeMetadata = { conversationId: null, turnExchangeId: null };
    let finalTab = null;
    let urlConversationId = null;

    if (firstBoundary?.kind === "assistant_terminal_candidate") {
      diagnostics.earlyCompletionCandidateSeen = true;
      diagnostics.earlyCompletionKind = (
        typeof firstBoundary?.signal?.kind === "string"
          ? firstBoundary.signal.kind
          : null
      );
      finalTab = await chrome.tabs.get(tabId);
      urlConversationId = conversationIdFromUrl(finalTab.url || "");

      if (diagnostics.conversationResponseSeen !== true || diagnostics.responseStatus !== 200) {
        diagnostics.earlyCompletionRejectedReason = "response_not_proven_200";
      } else if (!urlConversationId) {
        diagnostics.earlyCompletionRejectedReason = "conversation_route_not_resolved";
      } else {
        diagnostics.earlyCompletionAccepted = true;
        diagnostics.completionBoundary = "assistant_terminal";
      }
    }

    if (diagnostics.earlyCompletionAccepted !== true) {
      if (firstBoundary?.kind === "network_complete") {
        requestId = firstBoundary.requestId;
      } else {
        requestId = await Promise.race([completed, timeoutResult]);
      }
      diagnostics.completionBoundary = "network_loading_finished";

      try {
        const response = await sendCommand(debuggee, "Network.getResponseBody", { requestId });
        safeMetadata = extractSafeStreamMetadata(response?.body, Boolean(response?.base64Encoded));
      } catch {
        // Optional safe metadata only.
      }

      diagnostics.completionReadyWaitMs = await waitForComposerReady(
        debuggee,
        Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
      );
      finalTab = await chrome.tabs.get(tabId);
      urlConversationId = conversationIdFromUrl(finalTab.url || "");
    }

    diagnostics.elapsedMs = elapsedMs(startedAt);
    return {
      diagnostics,
      finalUrl: finalTab?.url || "",
      conversationId: safeMetadata.conversationId || urlConversationId,
      turnExchangeId: safeMetadata.turnExchangeId
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Tab may have closed.
      }
    }
    try {
      const targets = await chrome.debugger.getTargets();
      diagnostics.debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === tabId)?.attached
      );
    } catch {
      diagnostics.debuggerAttachedAfter = null;
    }
  }
};

executeNativeTurn = async function _executeNativeTurnWithStaleUiRecovery(message) {
  const recovery = await _pr811MaybeRecoverStaleRuntimeUi(message);
  const result = await _pr811OriginalExecuteNativeTurn(message);
  return {
    ...result,
    runtimeReloaded: recovery.runtimeReloaded,
    runtimeReloadMs: recovery.runtimeReloadMs
  };
};