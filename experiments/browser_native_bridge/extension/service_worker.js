const CHATGPT_ORIGIN = "https://chatgpt.com";
const PROTOCOL_VERSION = "1.3";
const DEFAULT_TIMEOUT_MS = 90_000;
const MAX_CAPTURE_CHARS = 1_000_000;

function isChatGPTUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.origin === CHATGPT_ORIGIN;
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

async function selectTab(requestedTabId) {
  if (Number.isInteger(requestedTabId)) {
    const tab = await chrome.tabs.get(requestedTabId);
    if (!isChatGPTUrl(tab.url || "")) {
      throw new Error("REQUESTED_TAB_IS_NOT_CHATGPT");
    }
    return tab;
  }

  const tabs = await findChatGPTTabs();
  if (!tabs.length) {
    throw new Error("NO_AUTHENTICATED_CHATGPT_TAB");
  }
  const preferred = tabs.find((tab) => tab.active) || tabs[0];
  return chrome.tabs.get(preferred.id);
}

async function sendCommand(debuggee, method, params = undefined) {
  return chrome.debugger.sendCommand(debuggee, method, params);
}

async function locateAndFocusComposer(debuggee) {
  await sendCommand(debuggee, "DOM.enable");
  await sendCommand(debuggee, "Accessibility.enable");

  // Prefer the semantic accessibility tree so the probe is not coupled to a
  // specific React component or CSS class. Current ChatGPT exposes the composer
  // as an editable textbox. Keep a narrow DOM fallback only for feasibility.
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
      // The composer is normally the final editable textbox in the accessibility
      // tree; searching from the end avoids unrelated search boxes.
      const node = candidates[candidates.length - 1];
      await sendCommand(debuggee, "DOM.focus", {
        backendNodeId: node.backendDOMNodeId
      });
      return { strategy: "accessibility", backendNodeId: node.backendDOMNodeId };
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
        return { selector, tag: el.tagName, width: rect.width, height: rect.height };
      }
      return null;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  if (!value) throw new Error("CHATGPT_COMPOSER_NOT_FOUND");
  return { strategy: "bounded_dom_fallback", ...value };
}

async function clearComposer(debuggee) {
  // Use trusted CDP keyboard input rather than mutating page state directly.
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

async function executeOfficialPageTurn({ tabId, text, timeoutMs = DEFAULT_TIMEOUT_MS }) {
  if (typeof text !== "string" || !text.trim()) {
    throw new Error("TEXT_REQUIRED");
  }
  if (text.length > 200_000) {
    throw new Error("TEXT_TOO_LARGE_FOR_RESEARCH_PROBE");
  }

  const tab = await selectTab(tabId);
  await waitForTabComplete(tab.id);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let eventListener = null;

  const diagnostics = {
    tabId: tab.id,
    tabWasActive: Boolean(tab.active),
    attached: false,
    composerStrategy: null,
    conversationRequestSeen: false,
    conversationResponseSeen: false,
    responseStatus: null,
    responseMimeType: null,
    loadingFinished: false,
    responseBodyAvailable: false
  };

  try {
    await chrome.debugger.attach(debuggee, PROTOCOL_VERSION);
    attached = true;
    diagnostics.attached = true;
    await sendCommand(debuggee, "Network.enable");
    await sendCommand(debuggee, "Runtime.enable");

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

    const composer = await locateAndFocusComposer(debuggee);
    diagnostics.composerStrategy = composer.strategy;
    await clearComposer(debuggee);
    await sendCommand(debuggee, "Input.insertText", { text });
    await submitWithEnter(debuggee);

    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error("CHATGPT_TURN_TIMEOUT")), timeoutMs);
    });
    const requestId = await Promise.race([completed, timeout]);

    let body = null;
    let base64Encoded = false;
    try {
      const response = await sendCommand(debuggee, "Network.getResponseBody", { requestId });
      if (typeof response?.body === "string") {
        body = response.body.slice(-MAX_CAPTURE_CHARS);
        base64Encoded = Boolean(response.base64Encoded);
        diagnostics.responseBodyAvailable = true;
      }
    } catch {
      // Response-body capture is a secondary feasibility signal. The official
      // page has already completed the turn even if DevTools does not retain it.
    }

    const finalTab = await chrome.tabs.get(tab.id);
    return {
      ok: true,
      diagnostics,
      finalUrl: finalTab.url || "",
      responseBody: body,
      responseBodyBase64Encoded: base64Encoded
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Tab may have closed or DevTools may have detached us already.
      }
    }
  }
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
    sendResponse({ ok: false, error: "UNKNOWN_OPERATION" });
  })().catch((error) => {
    sendResponse({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  });
  return true;
});
