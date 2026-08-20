const CHATGPT_ORIGIN = "https://chatgpt.com";
const HOST_NAME = "com.kymuco.chatgpt_web_adapter";
const BRIDGE_PROTOCOL_VERSION = 1;
const CDP_PROTOCOL_VERSION = "1.3";
const DEFAULT_TIMEOUT_MS = 150_000;
const DEFAULT_READY_TIMEOUT_MS = 120_000;
const DEFAULT_SUBMIT_READY_TIMEOUT_MS = 10_000;
const DEFAULT_SUBMIT_ACK_TIMEOUT_MS = 10_000;
const RUNTIME_TAB_KEY = "browserNativeRuntimeTabId";

let nativePort = null;
let reconnectDelayMs = 1000;
let reconnectTimer = null;
let activeRequestId = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function elapsedMs(startedAt) {
  return Math.round(performance.now() - startedAt);
}

function remainingMs(startedAt, timeoutMs, floorMs = 1000) {
  return Math.max(floorMs, timeoutMs - elapsedMs(startedAt));
}

function isChatGPTUrl(url) {
  try {
    return new URL(url).origin === CHATGPT_ORIGIN;
  } catch {
    return false;
  }
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

function extractSafeStreamMetadata(body, base64Encoded) {
  const result = { conversationId: null, turnExchangeId: null };
  if (base64Encoded || typeof body !== "string") return result;
  for (const rawLine of body.split(/\r?\n/)) {
    if (!rawLine.startsWith("data:")) continue;
    const payloadText = rawLine.slice(5).trim();
    if (!payloadText.startsWith("{") || !payloadText.includes('"type":"stream_handoff"')) continue;
    try {
      const payload = JSON.parse(payloadText);
      if (payload?.type !== "stream_handoff") continue;
      if (typeof payload.conversation_id === "string") result.conversationId = payload.conversation_id;
      if (typeof payload.turn_exchange_id === "string") result.turnExchangeId = payload.turn_exchange_id;
    } catch {
      // Ignore partial SSE. Raw response data never leaves this worker.
    }
  }
  return result;
}

async function sendCommand(debuggee, method, params = undefined) {
  return chrome.debugger.sendCommand(debuggee, method, params);
}

async function waitForTabComplete(tabId, timeoutMs = 45_000) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return current;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("CHATGPT_RUNTIME_TAB_LOAD_TIMEOUT"));
    }, timeoutMs);

    async function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      try {
        resolve(await chrome.tabs.get(tabId));
      } catch (error) {
        reject(error);
      }
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

async function storedRuntimeTabId() {
  const value = await chrome.storage.local.get(RUNTIME_TAB_KEY);
  return Number.isInteger(value?.[RUNTIME_TAB_KEY]) ? value[RUNTIME_TAB_KEY] : null;
}

async function storeRuntimeTabId(tabId) {
  await chrome.storage.local.set({ [RUNTIME_TAB_KEY]: tabId });
  postNative({
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "runtime_state",
    runtimeTabId: tabId
  });
}

async function ensureRuntimeTab(conversationId) {
  const targetUrl = conversationId
    ? `${CHATGPT_ORIGIN}/c/${encodeURIComponent(conversationId)}`
    : `${CHATGPT_ORIGIN}/`;

  let tab = null;
  const storedId = await storedRuntimeTabId();
  if (Number.isInteger(storedId)) {
    try {
      const candidate = await chrome.tabs.get(storedId);
      if (isChatGPTUrl(candidate.url || "")) tab = candidate;
    } catch {
      tab = null;
    }
  }

  if (!tab) {
    tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab.id)) throw new Error("CHATGPT_RUNTIME_TAB_CREATE_FAILED");
    await storeRuntimeTabId(tab.id);
    return waitForTabComplete(tab.id);
  }

  const currentConversationId = conversationIdFromUrl(tab.url || "");
  const alreadyTargeted = conversationId
    ? currentConversationId === conversationId
    : currentConversationId == null && new URL(tab.url || CHATGPT_ORIGIN).pathname === "/";

  if (!alreadyTargeted) {
    await chrome.tabs.update(tab.id, { url: targetUrl, active: false });
    tab = await waitForTabComplete(tab.id);
  }
  return tab;
}

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const storedId = await storedRuntimeTabId();
  if (storedId === tabId) {
    await chrome.storage.local.remove(RUNTIME_TAB_KEY);
    postNative({
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "runtime_state",
      runtimeTabId: null
    });
  }
});

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
        if (consecutiveReady >= 2) return elapsedMs(startedAt);
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
      await sendCommand(debuggee, "DOM.focus", { backendNodeId: node.backendDOMNodeId });
      return "accessibility";
    }
  } catch {
    // Fall through to the bounded DOM fallback.
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
        return true;
      }
      return false;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  if (!result?.result?.value) throw new Error("CHATGPT_COMPOSER_NOT_FOUND");
  return "bounded_dom_fallback";
}

async function clearComposer(debuggee) {
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown", key: "a", code: "KeyA", modifiers: 2,
    windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp", key: "a", code: "KeyA", modifiers: 2,
    windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown", key: "Backspace", code: "Backspace",
    windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp", key: "Backspace", code: "Backspace",
    windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8
  });
}

async function querySendButtonPoint(debuggee) {
  const result = await sendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const selectors = [
        'button[data-testid="send-button"]',
        'button[data-testid="composer-submit-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label="Send message"]',
        'button[aria-label="Отправить сообщение"]'
      ];
      for (const selector of selectors) {
        const button = document.querySelector(selector);
        if (!button) continue;
        const rect = button.getBoundingClientRect();
        const style = getComputedStyle(button);
        const disabled = button.disabled === true || button.getAttribute('aria-disabled') === 'true';
        if (rect.width <= 0 || rect.height <= 0 || disabled || style.pointerEvents === 'none') continue;
        return {
          selector,
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        };
      }
      return null;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value || null;
}

async function waitForSendButtonPoint(debuggee, timeoutMs = DEFAULT_SUBMIT_READY_TIMEOUT_MS) {
  const startedAt = performance.now();
  while (elapsedMs(startedAt) < timeoutMs) {
    const point = await querySendButtonPoint(debuggee);
    if (point && Number.isFinite(point.x) && Number.isFinite(point.y)) return point;
    await sleep(100);
  }
  throw new Error("CHATGPT_SEND_BUTTON_NOT_READY");
}

async function clickSendButton(debuggee, point) {
  await sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: point.x,
    y: point.y
  });
  await sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: point.x,
    y: point.y,
    button: "left",
    clickCount: 1
  });
  await sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: point.x,
    y: point.y,
    button: "left",
    clickCount: 1
  });
}

async function submitWithEnter(debuggee) {
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown", key: "Enter", code: "Enter", text: "\r", unmodifiedText: "\r",
    windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13
  });
  await sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp", key: "Enter", code: "Enter",
    windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13
  });
}

async function submitOfficialPageTurn(debuggee, timeoutMs) {
  try {
    const point = await waitForSendButtonPoint(
      debuggee,
      Math.min(timeoutMs, DEFAULT_SUBMIT_READY_TIMEOUT_MS)
    );
    await clickSendButton(debuggee, point);
    return { strategy: "send_button_click", selector: point.selector };
  } catch {
    // Keep the proven PR8.0 keyboard path as a bounded fallback.
    await locateAndFocusComposer(debuggee);
    await submitWithEnter(debuggee);
    return { strategy: "enter_fallback", selector: null };
  }
}

async function executeOfficialPageTurn({ tabId, text, timeoutMs }) {
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

    const requestId = await Promise.race([
      completed,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("CHATGPT_TURN_TIMEOUT")),
        remainingMs(startedAt, timeoutMs)
      ))
    ]);

    let safeMetadata = { conversationId: null, turnExchangeId: null };
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

    const finalTab = await chrome.tabs.get(tabId);
    const urlConversationId = conversationIdFromUrl(finalTab.url || "");
    diagnostics.elapsedMs = elapsedMs(startedAt);
    return {
      diagnostics,
      finalUrl: finalTab.url || "",
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
}

async function executeNativeTurn(message) {
  const conversationId = typeof message.conversationId === "string" && message.conversationId.trim()
    ? message.conversationId.trim()
    : null;
  const timeoutMs = Number.isFinite(message.timeoutMs)
    ? Math.max(10_000, Math.min(Number(message.timeoutMs), 300_000))
    : DEFAULT_TIMEOUT_MS;

  const tab = await ensureRuntimeTab(conversationId);
  if (!Number.isInteger(tab.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");
  const result = await executeOfficialPageTurn({
    tabId: tab.id,
    text: message.text,
    timeoutMs
  });
  const resolvedConversationId = result.conversationId || conversationId;
  if (!resolvedConversationId) throw new Error("CHATGPT_TURN_MISSING_CONVERSATION_ID");
  if (result.diagnostics.responseStatus !== 200) {
    throw new Error(`CHATGPT_TURN_HTTP_STATUS:${result.diagnostics.responseStatus}`);
  }
  if (result.diagnostics.debuggerAttachedAfter === true) {
    throw new Error("CHATGPT_DEBUGGER_ATTACHMENT_LEAK");
  }
  return {
    conversationId: resolvedConversationId,
    turnExchangeId: result.turnExchangeId,
    responseStatus: result.diagnostics.responseStatus,
    responseMimeType: result.diagnostics.responseMimeType,
    finalUrl: result.finalUrl,
    tabId: tab.id,
    tabWasActive: result.diagnostics.tabWasActive,
    elapsedMs: result.diagnostics.elapsedMs,
    submitStrategy: result.diagnostics.submitStrategy,
    submitAckMs: result.diagnostics.submitAckMs
  };
}

function safePortPost(port, message) {
  if (!port) return false;
  try {
    port.postMessage(message);
    return true;
  } catch {
    return false;
  }
}

function postNative(message) {
  return safePortPost(nativePort, message);
}

async function onNativeMessage(message, port) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION) return;
  if (message?.type !== "turn") return;
  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (activeRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "turn_result",
      request_id: requestId,
      ok: false,
      error: "BROWSER_NATIVE_EXTENSION_BUSY"
    });
    return;
  }

  activeRequestId = requestId;
  try {
    const result = await executeNativeTurn(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "turn_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "turn_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  } finally {
    activeRequestId = null;
  }
}

function scheduleReconnect() {
  if (reconnectTimer !== null) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectNativeBridge();
  }, reconnectDelayMs);
  reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30_000);
}

function connectNativeBridge() {
  if (nativePort !== null) return;
  let port;
  try {
    port = chrome.runtime.connectNative(HOST_NAME);
  } catch {
    scheduleReconnect();
    return;
  }

  nativePort = port;
  const thisPort = port;
  port.onMessage.addListener((message) => {
    onNativeMessage(message, thisPort);
  });
  port.onDisconnect.addListener(() => {
    if (nativePort === thisPort) nativePort = null;
    scheduleReconnect();
  });
  reconnectDelayMs = 1000;

  storedRuntimeTabId().then((runtimeTabId) => {
    if (nativePort !== thisPort) return;
    postNative({
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "hello",
      extensionId: chrome.runtime.id,
      extensionVersion: chrome.runtime.getManifest().version,
      runtimeTabId
    });
  });
}

chrome.runtime.onInstalled.addListener(() => connectNativeBridge());
chrome.runtime.onStartup.addListener(() => connectNativeBridge());
connectNativeBridge();
