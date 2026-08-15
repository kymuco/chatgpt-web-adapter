importScripts("service_worker_temporary_chat_turn_probe.js");

// PR8.7 live characterization #5:
// A Temporary-candidate conversation can be briefly represented by an exact
// /c/<conversation_id> anchor while a fresh ChatGPT root page hydrates. A single
// early anchor observation is therefore NOT equivalent to durable user-history
// persistence. Observe the exact link across a bounded settling window and
// report transient vs stable presence without exporting titles, link text, raw
// DOM, or page payloads.

const _pr87HistoryProbePriorExecuteNativeTurn = executeNativeTurn;
const PR87_HISTORY_DEFAULT_TIMEOUT_MS = 30_000;
const PR87_HISTORY_MIN_SETTLE_MS = 8_000;
const PR87_HISTORY_MAX_SETTLE_MS = 15_000;
const PR87_HISTORY_SAMPLE_MS = 500;
const PR87_HISTORY_STABLE_SAMPLE_COUNT = 4;

function _pr87HistoryProbeExpression(conversationId) {
  const encodedId = JSON.stringify(conversationId);
  return `(() => {
    const targetId = ${encodedId};
    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };

    let conversationLinkCount = 0;
    let exactLinkPresent = false;
    let exactVisibleLinkPresent = false;
    for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
      let parsed;
      try {
        parsed = new URL(anchor.href, location.href);
      } catch {
        continue;
      }
      if (parsed.origin !== location.origin) continue;
      const match = parsed.pathname.match(/^\\/c\\/([^/]+)$/);
      if (!match) continue;
      conversationLinkCount += 1;
      let id = match[1];
      try { id = decodeURIComponent(id); } catch {}
      if (id !== targetId) continue;
      exactLinkPresent = true;
      if (isVisible(anchor)) exactVisibleLinkPresent = true;
    }

    const mainPresent = Boolean(document.querySelector('main'));
    const navPresent = Boolean(document.querySelector('nav,aside'));
    return {
      exactLinkPresent,
      exactVisibleLinkPresent,
      conversationLinkCount,
      mainPresent,
      navPresent
    };
  })()`;
}

async function _pr87ProbeHistoryPresence(message) {
  const conversationId = typeof message?.conversationId === "string"
    ? message.conversationId.trim()
    : "";
  if (!conversationId || conversationId.includes("/") || conversationId.includes("?") || conversationId.includes("#")) {
    throw new Error("TEMPORARY_CHAT_HISTORY_PROBE_CONVERSATION_ID_REQUIRED");
  }

  const timeoutMs = Math.max(
    10_000,
    Math.min(60_000, Number(message?.timeoutMs) || PR87_HISTORY_DEFAULT_TIMEOUT_MS)
  );
  const settleWindowMs = Math.min(
    PR87_HISTORY_MAX_SETTLE_MS,
    Math.max(PR87_HISTORY_MIN_SETTLE_MS, timeoutMs - 5_000)
  );
  const startedAt = performance.now();
  let tabId = null;
  let debuggee = null;
  let attached = false;
  let activationListener = null;
  let tabWasActive = false;
  let tabActiveAfter = null;
  let tabActivatedDuringProbe = false;
  let probeTabClosed = false;
  let lastSnapshot = null;
  let historyReadyAtMs = null;
  let firstSeenMs = null;
  let lastSeenMs = null;
  let seenSampleCount = 0;
  let absentSampleCount = 0;
  let disappearedAfterSeen = false;
  let seenPreviously = false;
  const finalVisibleSamples = [];

  const activatedTabIds = new Set();
  activationListener = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(activationListener);

  try {
    const tab = await chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false });
    if (!Number.isInteger(tab?.id)) throw new Error("TEMPORARY_CHAT_HISTORY_PROBE_TAB_CREATE_FAILED");
    tabId = tab.id;
    tabWasActive = Boolean(tab.active);
    await waitForTabComplete(tabId, Math.min(timeoutMs, 45_000));

    debuggee = { tabId };
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _pr87RawSendCommand(debuggee, "Runtime.enable");

    const expression = _pr87HistoryProbeExpression(conversationId);
    while (elapsedMs(startedAt) < timeoutMs) {
      const evaluated = await _pr87RawSendCommand(debuggee, "Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      const value = evaluated?.result?.value;
      if (value && typeof value === "object") lastSnapshot = value;

      const nowMs = elapsedMs(startedAt);
      const historyReady = lastSnapshot?.mainPresent === true && lastSnapshot?.navPresent === true;
      if (historyReady && historyReadyAtMs == null) historyReadyAtMs = nowMs;

      if (historyReady) {
        const visible = lastSnapshot?.exactVisibleLinkPresent === true;
        if (visible) {
          seenSampleCount += 1;
          if (firstSeenMs == null) firstSeenMs = nowMs;
          lastSeenMs = nowMs;
          seenPreviously = true;
        } else {
          absentSampleCount += 1;
          if (seenPreviously) disappearedAfterSeen = true;
        }
        finalVisibleSamples.push(visible);
        if (finalVisibleSamples.length > PR87_HISTORY_STABLE_SAMPLE_COUNT) {
          finalVisibleSamples.shift();
        }
      }

      if (
        historyReadyAtMs != null &&
        nowMs - historyReadyAtMs >= settleWindowMs &&
        finalVisibleSamples.length >= PR87_HISTORY_STABLE_SAMPLE_COUNT
      ) {
        break;
      }
      await sleep(PR87_HISTORY_SAMPLE_MS);
    }

    try {
      tabActiveAfter = Boolean((await chrome.tabs.get(tabId))?.active);
    } catch {
      tabActiveAfter = null;
    }
    tabActivatedDuringProbe = activatedTabIds.has(tabId);
  } finally {
    if (attached && debuggee) {
      try { await chrome.debugger.detach(debuggee); } catch {}
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

  const snapshot = lastSnapshot && typeof lastSnapshot === "object" ? lastSnapshot : {};
  const stableHistoryPresence = (
    finalVisibleSamples.length >= PR87_HISTORY_STABLE_SAMPLE_COUNT &&
    finalVisibleSamples.every((value) => value === true)
  );
  const transientHistoryPresence = firstSeenMs != null && disappearedAfterSeen;

  return {
    probeContext: "fresh_root_history_settling",
    conversationId,
    historyLinkPresent: firstSeenMs != null,
    historyVisibleLinkPresent: firstSeenMs != null,
    finalHistoryLinkPresent: snapshot.exactLinkPresent === true,
    finalHistoryVisibleLinkPresent: snapshot.exactVisibleLinkPresent === true,
    stableHistoryPresence,
    transientHistoryPresence,
    disappearedAfterSeen,
    firstSeenMs,
    lastSeenMs,
    seenSampleCount,
    absentSampleCount,
    settleWindowMs,
    observationWindowMs: elapsedMs(startedAt),
    conversationLinkCount: Number.isInteger(snapshot.conversationLinkCount)
      ? snapshot.conversationLinkCount
      : 0,
    historySurfaceReady: snapshot.mainPresent === true && snapshot.navPresent === true,
    tabWasActive,
    tabActiveAfter,
    tabActivatedDuringProbe,
    foregroundActivationObserved: Boolean(
      tabWasActive || tabActiveAfter === true || tabActivatedDuringProbe
    ),
    probeTabClosed,
    elapsedMs: elapsedMs(startedAt)
  };
}

executeNativeTurn = async function _executeNativeTurnWithTemporaryHistoryCharacterization(message) {
  if (message?.probeTemporaryHistoryPresence !== true) {
    return _pr87HistoryProbePriorExecuteNativeTurn(message);
  }
  if (message?.probeTemporaryMode === true || message?.characterizeTemporaryTurn === true) {
    throw new Error("TEMPORARY_CHAT_HISTORY_PROBE_FLAG_CONFLICT");
  }
  return _pr87ProbeHistoryPresence(message);
};
