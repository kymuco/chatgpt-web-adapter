importScripts("service_worker_temporary_chat_manual_ground_truth.js");

// PR8.7 T7b characterization:
// Open the exact /c/<ephemeral-backend-id> product route only after the original
// true Temporary source tab has been explicitly confirmed closed. Sample route
// settling and bounded visible-turn evidence over time. This probe never types,
// submits, continues, canonically reads, or exports message text / raw DOM.
//
// A single transient /c/<id> URL is not stable reopenability. Recovery evidence
// requires visible conversation turns while the exact target route is observed.

const _pr87RouteReopenPriorExecuteNativeTurn = executeNativeTurn;
const PR87_ROUTE_REOPEN_DEFAULT_TIMEOUT_MS = 30_000;
const PR87_ROUTE_REOPEN_MAX_OBSERVATION_MS = 15_000;
const PR87_ROUTE_REOPEN_SAMPLE_MS = 250;
const PR87_ROUTE_REOPEN_STABLE_SAMPLE_COUNT = 8;

function _pr87RouteReopenValidateId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (
    !conversationId ||
    conversationId.includes("/") ||
    conversationId.includes("?") ||
    conversationId.includes("#")
  ) {
    throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_BACKEND_ID_REQUIRED");
  }
  return conversationId;
}

function _pr87RouteReopenClassifyUrl(url, targetId) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return "other_origin";
    const match = parsed.pathname.match(/^\/c\/([^/]+)$/);
    if (match) {
      let id = match[1];
      try { id = decodeURIComponent(id); } catch {}
      return id === targetId ? "exact_target" : "other_conversation";
    }
    if (parsed.pathname === "/" || parsed.pathname === "") return "root";
    return "other_chatgpt";
  } catch {
    return "invalid";
  }
}

function _pr87RouteReopenSurfaceExpression() {
  return `(() => {
    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const main = document.querySelector('main');
    if (!main) {
      return { surfaceReady: false, visibleTurnCount: 0, selectorKind: 'none' };
    }
    let selectorKind = 'conversation-testid';
    let turns = Array.from(main.querySelectorAll('[data-testid^="conversation-turn-"]'));
    if (turns.length === 0) {
      selectorKind = 'article-fallback';
      turns = Array.from(main.querySelectorAll('article'));
    }
    turns = Array.from(new Set(turns)).filter((element) => {
      if (!isVisible(element)) return false;
      if (element.closest('form')) return false;
      return true;
    });
    return {
      surfaceReady: true,
      visibleTurnCount: turns.length,
      selectorKind
    };
  })()`;
}

async function _pr87RouteReopenSurfaceSnapshot(debuggee) {
  try {
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr87RouteReopenSurfaceExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (value && typeof value === "object") return value;
  } catch {
    // Navigation can invalidate an execution context between samples.
  }
  return { surfaceReady: false, visibleTurnCount: 0, selectorKind: "unavailable" };
}

async function _pr87ProbeTemporaryRouteReopen(message) {
  const conversationId = _pr87RouteReopenValidateId(message?.conversationId);
  if (message?.sourceTemporaryTabConfirmedClosed !== true) {
    throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_SOURCE_CLOSED_CONFIRMATION_REQUIRED");
  }
  if (
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.characterizeManualTemporaryGroundTruth === true ||
    message?.text != null
  ) {
    throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_FLAG_CONFLICT");
  }

  const timeoutMs = Math.max(
    10_000,
    Math.min(60_000, Number(message?.timeoutMs) || PR87_ROUTE_REOPEN_DEFAULT_TIMEOUT_MS)
  );
  const observationWindowMs = Math.min(timeoutMs, PR87_ROUTE_REOPEN_MAX_OBSERVATION_MS);
  const targetUrl = `${CHATGPT_ORIGIN}/c/${encodeURIComponent(conversationId)}`;
  const startedAt = performance.now();

  let tabId = null;
  let debuggee = null;
  let attached = false;
  let debuggerAttachedAfter = null;
  let activationListener = null;
  let networkListener = null;
  let tabWasActive = false;
  let tabActiveAfter = null;
  let tabActivatedDuringProbe = false;
  let probeTabClosed = false;
  let conversationWriteCount = 0;

  let targetRouteObserved = false;
  let targetRouteFirstSeenMs = null;
  let targetRouteLastSeenMs = null;
  let targetRouteSampleCount = 0;
  let rootRouteObserved = false;
  let rootRouteSampleCount = 0;
  let otherRouteSampleCount = 0;
  let redirectAwayFromTargetObserved = false;
  let targetPreviouslySeen = false;

  let visibleTurnSurfaceObserved = false;
  let maxVisibleTurnCount = 0;
  let finalVisibleTurnCount = 0;
  let turnSurfaceSelectorKind = "unavailable";
  let recoveredSampleCount = 0;
  let firstRecoveredMs = null;
  let lastRecoveredMs = null;
  const finalRecoveredSamples = [];
  let outcome = null;

  const activatedTabIds = new Set();
  activationListener = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(activationListener);

  try {
    const tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab?.id)) {
      throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_TAB_CREATE_FAILED");
    }
    tabId = tab.id;
    tabWasActive = Boolean(tab.active);
    debuggee = { tabId };

    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "Network.enable");

    networkListener = (source, method, params) => {
      if (source?.tabId !== tabId || method !== "Network.requestWillBeSent") return;
      const request = params?.request;
      if (isConversationWrite(request?.url || "", request?.method || "")) {
        conversationWriteCount += 1;
      }
    };
    chrome.debugger.onEvent.addListener(networkListener);

    while (elapsedMs(startedAt) < observationWindowMs) {
      let currentTab = null;
      try {
        currentTab = await chrome.tabs.get(tabId);
      } catch {
        break;
      }
      const routeKind = _pr87RouteReopenClassifyUrl(currentTab?.url || "", conversationId);
      const nowMs = elapsedMs(startedAt);
      const exactTarget = routeKind === "exact_target";

      if (exactTarget) {
        targetRouteObserved = true;
        targetRouteSampleCount += 1;
        if (targetRouteFirstSeenMs == null) targetRouteFirstSeenMs = nowMs;
        targetRouteLastSeenMs = nowMs;
        targetPreviouslySeen = true;
      } else {
        if (routeKind === "root") {
          rootRouteObserved = true;
          rootRouteSampleCount += 1;
        } else {
          otherRouteSampleCount += 1;
        }
        if (targetPreviouslySeen) redirectAwayFromTargetObserved = true;
      }

      const surface = await _pr87RouteReopenSurfaceSnapshot(debuggee);
      const visibleTurnCount = Number.isInteger(surface?.visibleTurnCount)
        ? surface.visibleTurnCount
        : 0;
      finalVisibleTurnCount = visibleTurnCount;
      maxVisibleTurnCount = Math.max(maxVisibleTurnCount, visibleTurnCount);
      if (visibleTurnCount > 0) visibleTurnSurfaceObserved = true;
      if (typeof surface?.selectorKind === "string") {
        turnSurfaceSelectorKind = surface.selectorKind;
      }

      const recoveredNow = exactTarget && visibleTurnCount >= 2;
      if (recoveredNow) {
        recoveredSampleCount += 1;
        if (firstRecoveredMs == null) firstRecoveredMs = nowMs;
        lastRecoveredMs = nowMs;
      }
      finalRecoveredSamples.push(recoveredNow);
      if (finalRecoveredSamples.length > PR87_ROUTE_REOPEN_STABLE_SAMPLE_COUNT) {
        finalRecoveredSamples.shift();
      }

      await sleep(PR87_ROUTE_REOPEN_SAMPLE_MS);
    }

    if (conversationWriteCount !== 0) {
      throw new Error(
        `TEMPORARY_CHAT_ROUTE_REOPEN_UNEXPECTED_CONVERSATION_WRITE:${conversationWriteCount}`
      );
    }

    try {
      const finalTab = await chrome.tabs.get(tabId);
      tabActiveAfter = Boolean(finalTab?.active);
      const finalRouteKind = _pr87RouteReopenClassifyUrl(
        finalTab?.url || "",
        conversationId
      );
      const stableRecovered = Boolean(
        finalRecoveredSamples.length >= PR87_ROUTE_REOPEN_STABLE_SAMPLE_COUNT &&
        finalRecoveredSamples.every((value) => value === true)
      );
      const transientRecovered = recoveredSampleCount > 0 && !stableRecovered;

      let recoveryEvidenceStatus = "INCONCLUSIVE";
      if (stableRecovered) {
        recoveryEvidenceStatus = "STABLE_RECOVERED";
      } else if (transientRecovered) {
        recoveryEvidenceStatus = "TRANSIENT_RECOVERED";
      } else if (targetRouteObserved && redirectAwayFromTargetObserved) {
        recoveryEvidenceStatus = "TRANSIENT_ROUTE_NO_RECOVERY";
      } else if (finalRouteKind === "root") {
        recoveryEvidenceStatus = "REDIRECTED_TO_ROOT";
      } else if (targetRouteObserved) {
        recoveryEvidenceStatus = "TARGET_ROUTE_NO_VISIBLE_TURNS";
      }

      tabActivatedDuringProbe = activatedTabIds.has(tabId);

      outcome = {
        probeContext: "temporary_product_route_reopen_after_source_close",
        conversationId,
        sourceTemporaryTabConfirmedClosed: true,
        productRouteOpenAttempted: true,
        canonicalHttpReadPerformed: false,
        conversationAttachPerformed: false,
        writePerformed: false,
        conversationWriteCount,
        observationWindowMs: elapsedMs(startedAt),
        targetRouteObserved,
        targetRouteFirstSeenMs,
        targetRouteLastSeenMs,
        targetRouteSampleCount,
        rootRouteObserved,
        rootRouteSampleCount,
        otherRouteSampleCount,
        redirectAwayFromTargetObserved,
        finalUrlKind: finalRouteKind,
        finalUrlConversationIdMatchesTarget: finalRouteKind === "exact_target",
        visibleTurnSurfaceObserved,
        maxVisibleTurnCount,
        finalVisibleTurnCount,
        turnSurfaceSelectorKind,
        recoveredSampleCount,
        firstRecoveredMs,
        lastRecoveredMs,
        stableRecovered,
        transientRecovered,
        recoveryEvidenceStatus,
        tabWasActive,
        tabActiveAfter,
        tabActivatedDuringProbe,
        foregroundActivationObserved: Boolean(
          tabWasActive || tabActiveAfter === true || tabActivatedDuringProbe
        )
      };
    } catch {
      throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_FINAL_TAB_UNAVAILABLE");
    }
  } finally {
    if (networkListener) chrome.debugger.onEvent.removeListener(networkListener);
    if (attached && debuggee) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    if (debuggee) {
      try {
        const targets = await chrome.debugger.getTargets();
        debuggerAttachedAfter = Boolean(
          targets.find((target) => target.tabId === tabId)?.attached
        );
      } catch {
        debuggerAttachedAfter = null;
      }
    }
    if (activationListener) chrome.tabs.onActivated.removeListener(activationListener);
    if (Number.isInteger(tabId)) {
      try {
        await chrome.tabs.remove(tabId);
        probeTabClosed = true;
      } catch {
        probeTabClosed = false;
      }
    }
  }

  if (!outcome) {
    throw new Error("TEMPORARY_CHAT_ROUTE_REOPEN_NO_OUTCOME");
  }
  return {
    ...outcome,
    debuggerAttachedAfter,
    probeTabClosed
  };
}

executeNativeTurn = async function _executeNativeTurnWithTemporaryRouteReopenProbe(message) {
  if (message?.probeTemporaryRouteReopen !== true) {
    return _pr87RouteReopenPriorExecuteNativeTurn(message);
  }
  return _pr87ProbeTemporaryRouteReopen(message);
};
