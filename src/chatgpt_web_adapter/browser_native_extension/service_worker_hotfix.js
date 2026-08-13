const HOTFIX_SUBMIT_ACK_MS = 1_500;
const HOTFIX_FINAL_ACK_MS = 2_500;

const _originalDebuggerSendCommand = chrome.debugger.sendCommand.bind(chrome.debugger);
const _submitStateByTabId = new Map();

function _isConversationWrite(url, method) {
  if (method !== "POST") return false;
  try {
    const parsed = new URL(url);
    if (parsed.origin !== "https://chatgpt.com") return false;
    const path = parsed.pathname.replace(/\/+$/, "");
    return path.endsWith("/backend-api/f/conversation") ||
      path.endsWith("/backend-api/conversation");
  } catch {
    return false;
  }
}

function _newSubmitState(tabId) {
  const state = {
    tabId,
    observed: false,
    resolver: null,
    strategy: null
  };
  _submitStateByTabId.set(tabId, state);
  return state;
}

function _markSubmitObserved(tabId) {
  const state = _submitStateByTabId.get(tabId);
  if (!state || state.observed) return;
  state.observed = true;
  if (state.resolver) {
    const resolve = state.resolver;
    state.resolver = null;
    resolve(true);
  }
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (!Number.isInteger(source?.tabId) || method !== "Network.requestWillBeSent") return;
  const request = params?.request;
  if (_isConversationWrite(request?.url || "", request?.method || "")) {
    _markSubmitObserved(source.tabId);
  }
});

async function _waitForSubmitAck(tabId, timeoutMs) {
  const state = _submitStateByTabId.get(tabId);
  if (!state) return false;
  if (state.observed) return true;
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (state.resolver === finish) state.resolver = null;
      resolve(value);
    };
    state.resolver = finish;
    setTimeout(() => finish(Boolean(state.observed)), timeoutMs);
  });
}

function _sendButtonExpression(action) {
  return `(() => {
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
      const disabled = button.disabled === true || button.getAttribute('aria-disabled') === 'true';
      if (rect.width <= 0 || rect.height <= 0 || disabled) continue;
      if (${JSON.stringify(action)} === 'focus') button.focus();
      if (${JSON.stringify(action)} === 'click') button.click();
      return { selector };
    }
    return null;
  })()`;
}

async function _focusSendButton(debuggee) {
  const result = await _originalDebuggerSendCommand(debuggee, "Runtime.evaluate", {
    expression: _sendButtonExpression("focus"),
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value?.selector || null;
}

async function _pageActivateSendButton(debuggee) {
  const result = await _originalDebuggerSendCommand(debuggee, "Runtime.evaluate", {
    expression: _sendButtonExpression("click"),
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value?.selector || null;
}

async function _pressFocusedButton(debuggee, key, code, virtualKeyCode, text = undefined) {
  const base = {
    key,
    code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode
  };
  await _originalDebuggerSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    ...base,
    ...(text ? { text, unmodifiedText: text } : {})
  });
  await _originalDebuggerSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    ...base
  });
}

async function _runSubmitFallbackLadder(debuggee) {
  const tabId = debuggee?.tabId;
  if (!Number.isInteger(tabId)) return null;
  const state = _submitStateByTabId.get(tabId) || _newSubmitState(tabId);

  if (await _waitForSubmitAck(tabId, HOTFIX_SUBMIT_ACK_MS)) {
    state.strategy = "cdp_mouse";
    return state.strategy;
  }

  const selector = await _focusSendButton(debuggee);
  if (selector && !state.observed) {
    await _pressFocusedButton(debuggee, "Enter", "Enter", 13, "\r");
    if (await _waitForSubmitAck(tabId, HOTFIX_SUBMIT_ACK_MS)) {
      state.strategy = "focused_button_enter";
      return state.strategy;
    }
  }

  if (selector && !state.observed) {
    await _pressFocusedButton(debuggee, " ", "Space", 32, " ");
    if (await _waitForSubmitAck(tabId, HOTFIX_SUBMIT_ACK_MS)) {
      state.strategy = "focused_button_space";
      return state.strategy;
    }
  }

  if (!state.observed) {
    const pageSelector = await _pageActivateSendButton(debuggee);
    if (pageSelector && await _waitForSubmitAck(tabId, HOTFIX_FINAL_ACK_MS)) {
      state.strategy = "page_button_click";
      return state.strategy;
    }
  }

  return null;
}

async function _patchedDebuggerSendCommand(debuggee, method, params = undefined) {
  if (method !== "Input.dispatchMouseEvent" || !Number.isInteger(debuggee?.tabId)) {
    return _originalDebuggerSendCommand(debuggee, method, params);
  }

  if (params?.type === "mousePressed" && params?.button === "left") {
    _newSubmitState(debuggee.tabId);
    return _originalDebuggerSendCommand(debuggee, method, {
      ...params,
      buttons: 1
    });
  }

  if (params?.type === "mouseReleased" && params?.button === "left") {
    const result = await _originalDebuggerSendCommand(debuggee, method, {
      ...params,
      buttons: 0
    });
    try {
      await _runSubmitFallbackLadder(debuggee);
    } finally {
      setTimeout(() => _submitStateByTabId.delete(debuggee.tabId), 15_000);
    }
    return result;
  }

  return _originalDebuggerSendCommand(debuggee, method, params);
}

try {
  chrome.debugger.sendCommand = _patchedDebuggerSendCommand;
} catch {
  // Fall through to defineProperty for Chrome API objects that reject assignment.
}
if (chrome.debugger.sendCommand !== _patchedDebuggerSendCommand) {
  Object.defineProperty(chrome.debugger, "sendCommand", {
    configurable: true,
    writable: true,
    value: _patchedDebuggerSendCommand
  });
}

importScripts("service_worker.js");
