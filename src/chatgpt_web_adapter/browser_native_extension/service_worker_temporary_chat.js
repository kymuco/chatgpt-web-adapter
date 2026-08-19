importScripts("service_worker_runtime_tab_reconciliation.js");

const PR87_TEMPORARY_PROBE_DEFAULT_TIMEOUT_MS = 30_000;
const PR87_TEMPORARY_PROBE_MAX_TIMEOUT_MS = 120_000;
const PR87_TEMPORARY_SELECTION_TIMEOUT_MS = 5_000;
const _pr87OriginalExecuteNativeTurn = executeNativeTurn;

function _pr87ClampProbeTimeoutMs(value) {
  if (!Number.isFinite(value)) return PR87_TEMPORARY_PROBE_DEFAULT_TIMEOUT_MS;
  return Math.max(10_000, Math.min(Number(value), PR87_TEMPORARY_PROBE_MAX_TIMEOUT_MS));
}

function _pr87TemporaryControlSnapshotExpression() {
  return `(() => {
    const normalize = (value) => typeof value === 'string'
      ? value.trim().toLowerCase().replace(/\\s+/g, ' ')
      : '';
    const matchesTemporary = (value) => {
      const text = normalize(value);
      return text.includes('temporary') || text.includes('временн');
    };
    const explicitTrueStates = new Set(['on', 'checked', 'active', 'selected']);
    const explicitFalseStates = new Set(['off', 'unchecked', 'inactive', 'unselected']);
    const candidates = [];

    for (const element of Array.from(document.querySelectorAll('button,[role="button"]'))) {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden' || style.display === 'none') {
        continue;
      }

      const fields = {
        text: element.innerText || element.textContent || '',
        aria_label: element.getAttribute('aria-label') || '',
        title: element.getAttribute('title') || '',
        data_testid: element.getAttribute('data-testid') || ''
      };
      const matchSignals = Object.entries(fields)
        .filter(([, value]) => matchesTemporary(value))
        .map(([name]) => name);
      if (!matchSignals.length) continue;

      const proofSignals = [];
      const falseSignals = [];
      const ariaPressed = normalize(element.getAttribute('aria-pressed'));
      const ariaChecked = normalize(element.getAttribute('aria-checked'));
      const ariaCurrent = normalize(element.getAttribute('aria-current'));
      const dataState = normalize(element.getAttribute('data-state'));
      const dataSelected = normalize(element.getAttribute('data-selected'));

      if (ariaPressed === 'true') proofSignals.push('aria-pressed:true');
      else if (ariaPressed === 'false') falseSignals.push('aria-pressed:false');
      if (ariaChecked === 'true') proofSignals.push('aria-checked:true');
      else if (ariaChecked === 'false') falseSignals.push('aria-checked:false');
      if (ariaCurrent === 'true') proofSignals.push('aria-current:true');
      if (explicitTrueStates.has(dataState)) proofSignals.push('data-state:' + dataState);
      else if (explicitFalseStates.has(dataState)) falseSignals.push('data-state:' + dataState);
      if (dataSelected === 'true') proofSignals.push('data-selected:true');
      else if (dataSelected === 'false') falseSignals.push('data-selected:false');

      const selected = proofSignals.length
        ? true
        : (falseSignals.length ? false : null);
      candidates.push({
        matchSignals,
        proofSignals,
        selected,
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      });
    }

    const primary = candidates.length === 1 ? candidates[0] : null;
    return {
      candidateCount: candidates.length,
      controlFound: candidates.length > 0,
      ambiguous: candidates.length > 1,
      selected: primary ? primary.selected : null,
      matchSignals: primary ? primary.matchSignals : [],
      proofSignals: primary ? primary.proofSignals : [],
      point: primary ? { x: primary.x, y: primary.y } : null
    };
  })()`;
}

async function _pr87RawSendCommand(debuggee, method, params = undefined) {
  return chrome.debugger.sendCommand(debuggee, method, params);
}

async function _pr87TemporaryControlSnapshot(debuggee) {
  const result = await _pr87RawSendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr87TemporaryControlSnapshotExpression(),
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object"
    ? value
    : {
        candidateCount: 0,
        controlFound: false,
        ambiguous: false,
        selected: null,
        matchSignals: [],
        proofSignals: [],
        point: null
      };
}

async function _pr87ClickPoint(debuggee, point) {
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    throw new Error("TEMPORARY_CHAT_CONTROL_POINT_UNAVAILABLE");
  }
  await _pr87RawSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: point.x,
    y: point.y
  });
  await _pr87RawSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: point.x,
    y: point.y,
    button: "left",
    buttons: 1,
    clickCount: 1
  });
  await _pr87RawSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: point.x,
    y: point.y,
    button: "left",
    buttons: 0,
    clickCount: 1
  });
}

async function _pr87WaitForSelectedTemporaryControl(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let last = await _pr87TemporaryControlSnapshot(debuggee);
  while (Math.round(performance.now() - startedAt) < timeoutMs) {
    if (last?.selected === true) return last;
    await sleep(100);
    last = await _pr87TemporaryControlSnapshot(debuggee);
  }
  return last;
}

async function _pr87ExecuteTemporaryModeProbe(message) {
  const timeoutMs = _pr87ClampProbeTimeoutMs(message?.timeoutMs);
  const startedAt = performance.now();
  let tabId = null;
  let debuggee = null;
  let attached = false;
  let debuggerListener = null;
  let activationListener = null;
  let conversationWriteObserved = false;
  let tabWasActive = false;
  let tabActiveAfter = null;
  let tabActivatedDuringProbe = false;
  let probeTabClosed = false;
  let result = null;

  const activatedTabIds = new Set();
  activationListener = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(activationListener);

  try {
    const tab = await chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false });
    if (!Number.isInteger(tab?.id)) throw new Error("TEMPORARY_CHAT_PROBE_TAB_CREATE_FAILED");
    tabId = tab.id;
    tabWasActive = Boolean(tab.active);
    await waitForTabComplete(tabId, Math.min(timeoutMs, 45_000));

    debuggee = { tabId };
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _pr87RawSendCommand(debuggee, "Network.enable");
    await _pr87RawSendCommand(debuggee, "Runtime.enable");
    await waitForComposerReady(debuggee, Math.min(timeoutMs, DEFAULT_READY_TIMEOUT_MS));

    debuggerListener = (source, method, params) => {
      if (source?.tabId !== tabId || method !== "Network.requestWillBeSent") return;
      const request = params?.request;
      if (isConversationWrite(request?.url || "", request?.method || "")) {
        conversationWriteObserved = true;
      }
    };
    chrome.debugger.onEvent.addListener(debuggerListener);

    const before = await _pr87TemporaryControlSnapshot(debuggee);
    let after = before;
    let selectionAction = "none";
    let reason = "TEMPORARY_CHAT_SELECTION_NOT_PROVEN";

    if (!before.controlFound) {
      reason = "TEMPORARY_CHAT_CONTROL_NOT_FOUND";
    } else if (before.ambiguous) {
      reason = "TEMPORARY_CHAT_CONTROL_AMBIGUOUS";
    } else if (before.selected === true) {
      selectionAction = "already_selected";
      reason = "TEMPORARY_CHAT_SELECTED_STATE_OBSERVED";
    } else {
      selectionAction = "cdp_control_click";
      await _pr87ClickPoint(debuggee, before.point);
      after = await _pr87WaitForSelectedTemporaryControl(
        debuggee,
        Math.min(PR87_TEMPORARY_SELECTION_TIMEOUT_MS, timeoutMs)
      );
      reason = after?.selected === true
        ? "TEMPORARY_CHAT_SELECTION_PROVEN"
        : "TEMPORARY_CHAT_SELECTION_NOT_PROVEN";
    }

    await sleep(250);
    if (conversationWriteObserved) {
      throw new Error("TEMPORARY_CHAT_PROBE_UNEXPECTED_CONVERSATION_WRITE");
    }

    try {
      const finalTab = await chrome.tabs.get(tabId);
      tabActiveAfter = Boolean(finalTab?.active);
    } catch {
      tabActiveAfter = null;
    }
    tabActivatedDuringProbe = activatedTabIds.has(tabId);

    result = {
      probeContext: "isolated_new_chat",
      controlFound: Boolean(before.controlFound),
      candidateCount: Number.isInteger(before.candidateCount) ? before.candidateCount : 0,
      selectedBefore: typeof before.selected === "boolean" ? before.selected : null,
      selectedAfter: typeof after?.selected === "boolean" ? after.selected : null,
      modeSelectionProven: after?.selected === true,
      selectionAction,
      reason,
      matchSignals: Array.isArray(after?.matchSignals) ? after.matchSignals : [],
      selectionProofSignals: Array.isArray(after?.proofSignals) ? after.proofSignals : [],
      conversationWriteObserved,
      tabWasActive,
      tabActiveAfter,
      tabActivatedDuringProbe,
      foregroundActivationObserved: Boolean(
        tabWasActive || tabActiveAfter === true || tabActivatedDuringProbe
      ),
      elapsedMs: Math.round(performance.now() - startedAt)
    };
  } finally {
    if (debuggerListener) chrome.debugger.onEvent.removeListener(debuggerListener);
    if (attached && debuggee) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // The isolated probe tab may already have disappeared.
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

  if (!result) throw new Error("TEMPORARY_CHAT_PROBE_NO_RESULT");
  return {
    ...result,
    probeTabClosed,
    elapsedMs: Math.round(performance.now() - startedAt)
  };
}

executeNativeTurn = async function _executeNativeTurnWithTemporaryModeProbe(message) {
  if (message?.probeTemporaryMode !== true) {
    return _pr87OriginalExecuteNativeTurn(message);
  }
  if (message?.conversationId != null) {
    throw new Error("TEMPORARY_CHAT_PROBE_REQUIRES_NEW_CHAT");
  }
  if (message?.text != null) {
    throw new Error("TEMPORARY_CHAT_PROBE_MUST_NOT_INCLUDE_TEXT");
  }
  return _pr87ExecuteTemporaryModeProbe(message);
};
