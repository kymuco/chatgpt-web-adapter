// PR8.8 shipping hardening for fresh runtime tabs.
// Fresh Browser Authority tabs are intentionally created inactive. Current ChatGPT
// effort-picker UI is allowed one bounded transient foreground window only while
// Instant selection is required. The previously active tab is restored in finally.

const _pr88InstantEffortForegroundPriorEnsureInstant = _pr88SelectionEnsureInstant;

async function _pr88InstantEffortDocumentVisible(debuggee) {
  try {
    const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
      expression: `(() => ({visible:document.visibilityState==='visible' && document.hidden!==true}))()`,
      returnByValue: true,
      awaitPromise: true
    });
    return result?.result?.value?.visible === true;
  } catch {
    return false;
  }
}

async function _pr88InstantEffortWaitForeground(debuggee, timeoutMs = 2500) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) return false;
  const startedAt = performance.now();
  while (performance.now() - startedAt < timeoutMs) {
    try {
      const tab = await chrome.tabs.get(tabId);
      if (tab?.active === true && await _pr88InstantEffortDocumentVisible(debuggee)) {
        return true;
      }
    } catch {}
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return false;
}

async function _pr88InstantEffortRestorePriorTab(state) {
  const result = {
    attempted: false,
    restored: state?.activated !== true,
    priorTabPresent: Number.isInteger(state?.priorActiveTabId)
  };
  if (state?.activated !== true || !Number.isInteger(state?.priorActiveTabId)) {
    return result;
  }
  result.attempted = true;
  try {
    const prior = await chrome.tabs.get(state.priorActiveTabId);
    if (!prior || prior.windowId !== state.windowId) return result;
    await chrome.tabs.update(state.priorActiveTabId, {active: true});
    const startedAt = performance.now();
    while (performance.now() - startedAt < 1500) {
      const current = await chrome.tabs.get(state.priorActiveTabId);
      if (current?.active === true) {
        result.restored = true;
        return result;
      }
      await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
    }
  } catch {}
  return result;
}

async function _pr88InstantEffortBeginTransientForeground(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) {
    throw new Error('PR8_8_INSTANT_EFFORT_RUNTIME_TAB_REQUIRED');
  }

  const runtimeTab = await chrome.tabs.get(tabId);
  const windowId = Number.isInteger(runtimeTab?.windowId) ? runtimeTab.windowId : null;
  if (windowId === null) {
    throw new Error('PR8_8_INSTANT_EFFORT_RUNTIME_WINDOW_REQUIRED');
  }

  let priorActiveTabId = null;
  try {
    const activeTabs = await chrome.tabs.query({active: true, windowId});
    const prior = activeTabs.find((tab) => Number.isInteger(tab?.id) && tab.id !== tabId);
    priorActiveTabId = Number.isInteger(prior?.id) ? prior.id : null;
  } catch {}

  const state = {
    tabId,
    windowId,
    activated: runtimeTab?.active !== true,
    priorActiveTabId,
    foregroundProven: false
  };

  try {
    if (state.activated) {
      await chrome.tabs.update(tabId, {active: true});
    }
    state.foregroundProven = await _pr88InstantEffortWaitForeground(debuggee, 2500);
    if (state.foregroundProven !== true) {
      throw new Error('PR8_8_INSTANT_EFFORT_FOREGROUND_NOT_PROVEN');
    }
    // Give the product surface one bounded paint/event-loop turn after visibility.
    await sleep(150);
    return state;
  } catch (error) {
    await _pr88InstantEffortRestorePriorTab(state);
    throw error;
  }
}

_pr88SelectionEnsureInstant =
  async function _pr88SelectionEnsureInstantWithTransientForeground(debuggee, context) {
    if (context?.selectionChecked === true) {
      return _pr88InstantEffortForegroundPriorEnsureInstant(debuggee, context);
    }

    const before = await _pr88InstantSelectedModeSnapshot(debuggee);
    if (before?.selectedModeProven !== true || before?.selectedMode === 'INSTANT') {
      return _pr88InstantEffortForegroundPriorEnsureInstant(debuggee, context);
    }

    const foreground = await _pr88InstantEffortBeginTransientForeground(debuggee);
    context.instantEffortTransientForegroundRequested = true;
    context.instantEffortTransientForegroundActivated = foreground.activated === true;
    context.instantEffortTransientForegroundProven = foreground.foregroundProven === true;
    context.instantEffortPriorActiveTabPresent = Number.isInteger(foreground.priorActiveTabId);

    try {
      return await _pr88InstantEffortForegroundPriorEnsureInstant(debuggee, context);
    } finally {
      const restored = await _pr88InstantEffortRestorePriorTab(foreground);
      context.instantEffortForegroundRestoreAttempted = restored.attempted === true;
      context.instantEffortForegroundRestoreProven = restored.restored === true;
    }
  };
