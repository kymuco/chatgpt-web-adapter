const CHATGPT_ORIGIN = "https://chatgpt.com";
const PROTOCOL_VERSION = "1.3";
const DEFAULT_TIMEOUT_MS = 90_000;
const DEFAULT_READY_TIMEOUT_MS = 60_000;
const STRESS_TURN_COUNT = 20;
const STRESS_PREFIX = "SDK_BRIDGE_STRESS_";

function isChatGPTUrl(url) {
  try {
    return new URL(url).origin === CHATGPT_ORIGIN;
  } catch {
    return false;
  }
}

function isConversationWrite(url, method) {
  if (method !== "POST") return false;
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return false;
    const path = parsed.pathname.replace(/\/+$/, "");
    return path.endsWith("/backend-api/f/conversation") ||
      path.endsWith("/backend-api/conversation");
  } catch {
    return false;
  }
}

function elapsedMs(startedAt) {
  return Math.round(performance.now() - startedAt);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function conversationIdFromUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return null;
    const match = parsed.pathname.match(/^\/c\/([^/]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

function extractSafeStreamMetadata(body, base64Encoded) {
  const result = { conversationId: null, turnExchangeId: null };
  if (base64Encoded || typeof body !== "string") return result;

  for (const rawLine of body.split(/\r?\n/)) {
    if (!rawLine.startsWith("data:")) continue;
    const payloadText = rawLine.slice(5).trim();
    if (!payloadText.startsWith("{") || !payloadText.includes('"type":"stream_handoff"')) {
      continue;
    }
    try {
      const payload = JSON.parse(payloadText);
      if (payload?.type !== "stream_handoff") continue;
      if (typeof payload.conversation_id === "string") {
        result.conversationId = payload.conversation_id;
      }
      if (typeof payload.turn_exchange_id === "string") {
        result.turnExchangeId = payload.turn_exchange_id;
      }
    } catch {
      // Ignore malformed or partial SSE lines. Never return raw response data.
    }
  }
  return result;
}

async function findChatGPTTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs
    .filter((tab) => Number.isInteger(tab.id) && isChatGPTUrl(tab.url || ""))
    .map((tab) => ({
      id: tab.id,
      active: Boolean(tab.active),
      title: tab.title || "",
      url: tab.url || ""
    }));
}

async function waitForTabComplete(tabId, timeoutMs = 30_000) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return;

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("CHATGPT_TAB_LOAD_TIMEOUT"));
    }, timeoutMs);

    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      resolve();
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

async function selectExplicitTab(tabId) {
  if (!Number.isInteger(tabId)) {
    throw new Error("TAB_ID_REQUIRED");
  }
  const tab = await chrome.tabs.get(tabId);
  if (!isChatGPTUrl(tab.url || "")) {
    throw new Error("REQUESTED_TAB_IS_NOT_CHATGPT");
  }
  return tab;
}

async function sendCommand(debuggee, method, params = undefined) {
  return chrome.debugger.sendCommand(debuggee, method, params);
}

async function queryComposerReadiness(debuggee) {
  const result = await sendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const selectors = [
        '#prompt-textarea',
        '[contenteditable="true"][data-lexical-editor="true"]',
        'textarea[placeholder]'
      ];
      const composer = selectors
        .map((selector) => document.querySelector(selector))
        .find((el) => {
          if (!el) return false;
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
      if (!composer) return { ready: false, reason: 'composer_missing' };

      const stopSelectors = [
        '[data-testid="stop-button"]',
        '[data-testid="stop-generating-button"]',
        'button[aria-label*="Stop generating"]',
        'button[aria-label*="Остановить"]'
      ];
      const stopVisible = stopSelectors.some((selector) => {
        const el = document.querySelector(selector);
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      });
      const busy = composer.getAttribute('aria-busy') === 'true' ||
        composer.getAttribute('contenteditable') === 'false' ||
        composer.disabled === true;
      return {
        ready: !stopVisible && !busy,
        reason: stopVisible ? 'generation_control_visible' : (busy ? 'composer_busy' : 'ready')
      };
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value || { ready: false, reason: "unknown" };
}

async function waitForComposerReady(debuggee, timeoutMs = DEFAULT_READY_TIMEOUT_MS) {
  const startedAt = performance.now();
  let consecutiveReady = 0;
  let lastReason = "unknown";
  while (elapsedMs(startedAt) < timeoutMs) {
    try {
      const state = await queryComposerReadiness(debuggee);
      lastReason = state?.reason || "unknown";
      if (state?.ready) {
        consecutiveReady += 1;
        if (consecutiveReady >= 2) {
          return elapsedMs(startedAt);
        }
      } else {
        consecutiveReady = 0;
      }
    } catch {
      consecutiveReady = 0;
      lastReason = "readiness_probe_failed";
    }
    await sleep(250);
  }
  throw new Error(`CHATGPT_COMPOSER_NOT_READY:${lastReason}`);
}

async function locateAndFocusComposer(debuggee) {
  await sendCommand(debuggee, "DOM.enable");
  await sendCommand(debuggee, "Accessibility.enable");

  try {
    const tree = await sendCommand(debuggee, "Accessibility.getFullAXTree");
    const nodes = Array.isArray(tree?.nodes) ? tree.nodes : [];
    const candidates = nodes.filter((node) => {
      const role = node?.role?.value;
      const backendDOMNodeId = node?.backendDOMNodeId;
      if (role !== "textbox" || !Number.isInteger(backendDOMNodeId)) return false;
      const props = Array.isArray(node?.properties) ? node.properties : [];
      const editable = props.find((prop) => prop?.name === "editable");
      return editable == null || Boolean(editable?.value?.value);
    });

    if (candidates.length) {
      const node = candidates[candidates.length - 1];
      await sendCommand(debuggee, "DOM.focus", {
        backendNodeId: node.backendDOMNodeId
      });
      return { strategy: "accessibility" };
    }
  } catch {
    // Fall through to the bounded selector probe below.
  }

  const result = await sendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const selectors = [
        '#prompt-textarea',
        '[contenteditable="true"][data-lexical-editor="true"]',
        'textarea[placeholder]'
      ];
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        el.focus();
        return { selector, tag: el.tagName };
      }
      return null;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  if (!value) throw new Error("CHATGPT_COMPOSER_NOT_FOUND");
  return { strategy: "bounded_dom_fallback" };
}

async function clearComposer(debuggee) {
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "a",
    code: "KeyA",
    modifiers: 2,
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "a",
    code: "KeyA",
    modifiers: 2,
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Backspace",
    code: "Backspace",
    windowsVirtualKeyCode: 8,
    nativeVirtualKeyCode: 8
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Backspace",
    code: "Backspace",
    windowsVirtualKeyCode: 8,
    nativeVirtualKeyCode: 8
  });
}

async function submitWithEnter(debuggee) {
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Enter",
    code: "Enter",
    text: "\r",
    unmodifiedText: "\r",
    windowsVirtualKeyCode: 13,
    nativeVirtualKeyCode: 13
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Enter",
    code: "Enter",
    windowsVirtualKeyCode: 13,
    nativeVirtualKeyCode: 13
  });
}

async function executeOfficialPageTurn({
  tabId,
  text,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  readyTimeoutMs = DEFAULT_READY_TIMEOUT_MS
}) {
  if (!Number.isInteger(tabId)) throw new Error("TAB_ID_REQUIRED");
  if (typeof text !== "string" || !text.trim()) throw new Error("TEXT_REQUIRED");
  if (text.length > 200_000) throw new Error("TEXT_TOO_LARGE_FOR_RESEARCH_PROBE");

  const startedAt = performance.now();
  const tab = await selectExplicitTab(tabId);
  await waitForTabComplete(tab.id);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let eventListener = null;

  const diagnostics = {
    tabId: tab.id,
    tabWasActive: Boolean(tab.active),
    tabActiveAfter: null,
    attached: false,
    detached: false,
    debuggerAttachedAfter: null,
    readinessWaitMs: null,
    composerStrategy: null,
    conversationRequestSeen: false,
    conversationRequestObservedMs: null,
    conversationResponseSeen: false,
    conversationResponseObservedMs: null,
    responseStatus: null,
    responseMimeType: null,
    loadingFinished: false,
    loadingFinishedMs: null,
    safeStreamMetadataAvailable: false,
    elapsedMs: null
  };

  try {
    await chrome.debugger.attach(debuggee, PROTOCOL_VERSION);
    attached = true;
    diagnostics.attached = true;
    await sendCommand(debuggee, "Network.enable");
    await sendCommand(debuggee, "Runtime.enable");
    diagnostics.readinessWaitMs = await waitForComposerReady(debuggee, readyTimeoutMs);

    let conversationRequestId = null;
    let resolveCompleted;
    let rejectCompleted;
    const completed = new Promise((resolve, reject) => {
      resolveCompleted = resolve;
      rejectCompleted = reject;
    });

    eventListener = (source, method, params) => {
      if (source.tabId !== tab.id) return;
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (!conversationRequestId && isConversationWrite(request?.url || "", request?.method || "")) {
          conversationRequestId = params.requestId;
          diagnostics.conversationRequestSeen = true;
          diagnostics.conversationRequestObservedMs = elapsedMs(startedAt);
        }
        return;
      }
      if (!conversationRequestId || params?.requestId !== conversationRequestId) return;

      if (method === "Network.responseReceived") {
        diagnostics.conversationResponseSeen = true;
        diagnostics.conversationResponseObservedMs = elapsedMs(startedAt);
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
        diagnostics.loadingFinishedMs = elapsedMs(startedAt);
        resolveCompleted(conversationRequestId);
      }
    };
    chrome.debugger.onEvent.addListener(eventListener);

    const composer = await locateAndFocusComposer(debuggee);
    diagnostics.composerStrategy = composer.strategy;
    await clearComposer(debuggee);
    await sendCommand(debuggee, "Input.insertText", { text });
    await submitWithEnter(debuggee);

    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error("CHATGPT_TURN_TIMEOUT")), timeoutMs);
    });
    const requestId = await Promise.race([completed, timeout]);

    let safeMetadata = { conversationId: null, turnExchangeId: null };
    try {
      const response = await sendCommand(debuggee, "Network.getResponseBody", { requestId });
      safeMetadata = extractSafeStreamMetadata(
        response?.body,
        Boolean(response?.base64Encoded)
      );
      diagnostics.safeStreamMetadataAvailable = Boolean(
        safeMetadata.conversationId || safeMetadata.turnExchangeId
      );
    } catch {
      // Metadata extraction is secondary. The official page already completed
      // the protected write; raw response data is never returned from the worker.
    }

    const finalTab = await chrome.tabs.get(tab.id);
    diagnostics.tabActiveAfter = Boolean(finalTab.active);
    diagnostics.elapsedMs = elapsedMs(startedAt);
    return {
      ok: true,
      diagnostics,
      finalUrl: finalTab.url || "",
      conversationId: safeMetadata.conversationId,
      turnExchangeId: safeMetadata.turnExchangeId
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
        diagnostics.detached = true;
      } catch {
        // Tab may have closed or DevTools may have detached us already.
      }
    }
    try {
      const targets = await chrome.debugger.getTargets();
      diagnostics.debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === tab.id)?.attached
      );
    } catch {
      diagnostics.debuggerAttachedAfter = null;
    }
  }
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[middle];
  return Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

async function runRepeatabilityStress({ tabId }) {
  if (!Number.isInteger(tabId)) throw new Error("TAB_ID_REQUIRED");
  const initialTab = await selectExplicitTab(tabId);
  if (initialTab.active) throw new Error("STRESS_TARGET_MUST_BE_BACKGROUND");

  const startedAt = performance.now();
  let expectedConversationId = conversationIdFromUrl(initialTab.url || "");
  const turns = [];

  for (let index = 1; index <= STRESS_TURN_COUNT; index += 1) {
    const turnNumber = String(index).padStart(2, "0");
    const marker = `${STRESS_PREFIX}${turnNumber}`;
    const tabBefore = await chrome.tabs.get(tabId);
    if (tabBefore.active) {
      turns.push({
        turn: index,
        ok: false,
        error: "STRESS_TARGET_BECAME_ACTIVE_BEFORE_TURN"
      });
      break;
    }

    let result;
    try {
      result = await executeOfficialPageTurn({
        tabId,
        text: `Reply with exactly: ${marker}`
      });
    } catch (error) {
      turns.push({
        turn: index,
        ok: false,
        error: error instanceof Error ? error.message : String(error)
      });
      break;
    }

    const diagnostics = result.diagnostics || {};
    const observedConversationId = result.conversationId ||
      conversationIdFromUrl(result.finalUrl || "");
    if (!expectedConversationId && observedConversationId) {
      expectedConversationId = observedConversationId;
    }
    const conversationIdStable = Boolean(
      expectedConversationId && observedConversationId === expectedConversationId
    );
    const backgroundStable = diagnostics.tabWasActive === false &&
      diagnostics.tabActiveAfter === false;
    const detachedCleanly = diagnostics.detached === true &&
      diagnostics.debuggerAttachedAfter === false;
    const transportOk = diagnostics.conversationRequestSeen === true &&
      diagnostics.conversationResponseSeen === true &&
      diagnostics.responseStatus === 200 &&
      diagnostics.loadingFinished === true;
    const ok = transportOk && backgroundStable && detachedCleanly && conversationIdStable;

    turns.push({
      turn: index,
      ok,
      status: diagnostics.responseStatus,
      elapsedMs: diagnostics.elapsedMs,
      readinessWaitMs: diagnostics.readinessWaitMs,
      composerStrategy: diagnostics.composerStrategy,
      requestSeen: diagnostics.conversationRequestSeen,
      responseSeen: diagnostics.conversationResponseSeen,
      loadingFinished: diagnostics.loadingFinished,
      backgroundStable,
      detachedCleanly,
      conversationIdStable
    });

    if (!ok) break;
  }

  const completed = turns.filter((turn) => turn.ok).length;
  const durations = turns
    .map((turn) => turn.elapsedMs)
    .filter((value) => Number.isFinite(value));
  const pass = turns.length === STRESS_TURN_COUNT && completed === STRESS_TURN_COUNT &&
    turns.every((turn) => turn.ok);

  return {
    ok: pass,
    summary: {
      turnsRequested: STRESS_TURN_COUNT,
      turnsCompleted: completed,
      conversationId: expectedConversationId,
      allStatus200: turns.length === STRESS_TURN_COUNT && turns.every((turn) => turn.status === 200),
      allBackground: turns.length === STRESS_TURN_COUNT && turns.every((turn) => turn.backgroundStable === true),
      allDetached: turns.length === STRESS_TURN_COUNT && turns.every((turn) => turn.detachedCleanly === true),
      conversationIdStable: turns.length === STRESS_TURN_COUNT && turns.every((turn) => turn.conversationIdStable === true),
      medianTurnElapsedMs: median(durations),
      maxTurnElapsedMs: durations.length ? Math.max(...durations) : null,
      totalElapsedMs: elapsedMs(startedAt)
    },
    turns
  };
}

async function probeCapabilities() {
  const tabs = await findChatGPTTabs();
  const targets = await chrome.debugger.getTargets();
  const targetByTabId = new Map(
    targets
      .filter((target) => Number.isInteger(target.tabId))
      .map((target) => [target.tabId, target])
  );
  return {
    chromeDebuggerAvailable: typeof chrome.debugger?.attach === "function",
    chatgptTabs: tabs.map((tab) => ({
      ...tab,
      debuggerAlreadyAttached: Boolean(targetByTabId.get(tab.id)?.attached)
    }))
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    const op = message?.op;
    if (op === "probe_capabilities") {
      sendResponse({ ok: true, result: await probeCapabilities() });
      return;
    }
    if (op === "send_text_probe") {
      sendResponse({ ok: true, result: await executeOfficialPageTurn(message) });
      return;
    }
    if (op === "run_repeatability_stress") {
      sendResponse({ ok: true, result: await runRepeatabilityStress(message) });
      return;
    }
    sendResponse({ ok: false, error: "UNKNOWN_OPERATION" });
  })().catch((error) => {
    sendResponse({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  });
  return true;
});
