importScripts("service_worker_temporary_chat_turn_probe.js");

// PR8.7 live characterization #5:
// After a Temporary-looking one-shot turn, manual observation reported that the
// returned conversation appeared in ordinary ChatGPT history. Verify that
// user-facing persistence signal without another chat write by opening a fresh
// inactive root page and checking only whether an exact /c/<conversation_id>
// link is present. Conversation titles, link text, raw DOM, and page payloads
// never leave the browser context.

const _pr87HistoryProbePriorExecuteNativeTurn = executeNativeTurn;

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

  const timeoutMs = Math.max(5_000, Math.min(60_000, Number(message?.timeoutMs) || 30_000));
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
      if (lastSnapshot?.exactLinkPresent === true) break;
      if (lastSnapshot?.mainPresent === true && lastSnapshot?.navPresent === true && elapsedMs(startedAt) >= 5_000) break;
      await sleep(500);
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
  return {
    probeContext: "fresh_root_history_presence",
    conversationId,
    historyLinkPresent: snapshot.exactLinkPresent === true,
    historyVisibleLinkPresent: snapshot.exactVisibleLinkPresent === true,
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
