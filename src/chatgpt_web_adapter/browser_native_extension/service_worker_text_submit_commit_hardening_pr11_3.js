// PR11.3 ordinary-text protected-submit hardening.
//
// Rich-input and Temporary Chat turns already have specialized submit authority
// chains. This layer delegates those contexts unchanged and fixes only ordinary
// browser-owned text submission: Enter fallback is permitted only before the
// click commit boundary is attempted. Once mouseReleased is delegated, the
// outcome is ambiguous on ACK loss and a second submit is forbidden.

const PR113_TEXT_SUBMIT_SCHEMA = 3;
const PR113_MOUSE_RELEASE_UNCONFIRMED = "PR11_3_TEXT_MOUSE_RELEASE_OUTCOME_UNCONFIRMED";
const PR113_ENTER_KEYDOWN_UNCONFIRMED = "PR11_3_TEXT_ENTER_KEYDOWN_OUTCOME_UNCONFIRMED";

function _pr113SpecialSubmitContextActive() {
  try {
    const richInputActive = (
      typeof _pr92ActiveRichInputContext !== "undefined" &&
      _pr92ActiveRichInputContext !== null
    );
    const temporaryChatActive = (
      typeof _pr813TemporaryTurnContext !== "undefined" &&
      _pr813TemporaryTurnContext !== null
    );
    return richInputActive || temporaryChatActive;
  } catch {
    // Missing historical context markers mean this is not one of those specialized
    // paths. The ordinary text path remains eligible for PR11.3 hardening.
    return false;
  }
}

function _pr113IsMouseReleaseOutcomeUnconfirmed(error) {
  return Boolean(
    error instanceof Error &&
    error.message === PR113_MOUSE_RELEASE_UNCONFIRMED
  );
}

async function _pr113LocateComposerForTextSubmit(debuggee) {
  if (typeof _pr117LocateAndFocusComposer === "function") {
    return _pr117LocateAndFocusComposer(debuggee);
  }
  return locateAndFocusComposer(debuggee);
}

async function _pr113WaitForSubmitPoint(debuggee, timeoutMs) {
  if (typeof _pr117WaitForSendButtonPoint === "function") {
    return _pr117WaitForSendButtonPoint(debuggee, timeoutMs);
  }
  return waitForSendButtonPoint(debuggee, timeoutMs);
}

async function _pr113DocumentFocusSnapshot(debuggee) {
  try {
    const result = await sendCommand(debuggee, "Runtime.evaluate", {
      expression: "(() => ({hasFocus: document.hasFocus()}))()",
      returnByValue: true,
      awaitPromise: true
    });
    return result?.result?.value?.hasFocus === true;
  } catch {
    return false;
  }
}

async function _pr113EnableBackgroundKeyboardFocus(debuggee) {
  const tabActive = await _pr113RuntimeTabActive(debuggee);
  if (tabActive === true) {
    return {
      attempted: false,
      enabled: false,
      proven: true
    };
  }

  await sendCommand(
    debuggee,
    "Emulation.setFocusEmulationEnabled",
    { enabled: true }
  );
  const proven = await _pr113DocumentFocusSnapshot(debuggee);
  if (proven !== true) {
    try {
      await sendCommand(
        debuggee,
        "Emulation.setFocusEmulationEnabled",
        { enabled: false }
      );
    } catch {}
    throw new Error("PR11_3_BACKGROUND_FOCUS_EMULATION_NOT_PROVEN");
  }

  const tabActiveAfter = await _pr113RuntimeTabActive(debuggee);
  if (tabActiveAfter === true) {
    try {
      await sendCommand(
        debuggee,
        "Emulation.setFocusEmulationEnabled",
        { enabled: false }
      );
    } catch {}
    throw new Error("PR11_3_BACKGROUND_FOCUS_EMULATION_ACTIVATED_TAB");
  }

  return {
    attempted: true,
    enabled: true,
    proven: true
  };
}

async function _pr113DisableBackgroundKeyboardFocus(debuggee, state) {
  if (state?.enabled !== true) return true;
  try {
    await sendCommand(
      debuggee,
      "Emulation.setFocusEmulationEnabled",
      { enabled: false }
    );
    return true;
  } catch {
    return false;
  }
}

async function _pr113SubmitTextWithEnterOnce(debuggee) {
  const focusState = await _pr113EnableBackgroundKeyboardFocus(debuggee);
  let focusRestored = false;
  try {
    await _pr113LocateComposerForTextSubmit(debuggee);

    // Enter keyDown is the keyboard protected-write boundary. A rejected/lost CDP
    // ACK can coexist with a real keyDown, so the attempt itself is ambiguous and
    // must never look like proof that no write happened.
    try {
      await sendCommand(debuggee, "Input.dispatchKeyEvent", {
        type: "keyDown",
        key: "Enter",
        code: "Enter",
        text: "\r",
        unmodifiedText: "\r",
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13
      });
    } catch {
      throw new Error(PR113_ENTER_KEYDOWN_UNCONFIRMED);
    }

    // Once keyDown is acknowledged, keyUp is cleanup only and must not turn a
    // possibly committed write into a local failure that callers could interpret
    // as permission to retry.
    try {
      Promise.resolve(sendCommand(debuggee, "Input.dispatchKeyEvent", {
        type: "keyUp",
        key: "Enter",
        code: "Enter",
        windowsVirtualKeyCode: 13,
        nativeVirtualKeyCode: 13
      })).catch(() => {});
    } catch {}
  } finally {
    focusRestored = await _pr113DisableBackgroundKeyboardFocus(
      debuggee,
      focusState
    );
  }

  return {
    strategy: "enter_fallback",
    selector: null,
    backgroundFocusEmulationAttempted: focusState?.attempted === true,
    backgroundFocusEmulationProven: focusState?.proven === true,
    backgroundFocusEmulationRestored: focusRestored === true
  };
}

async function _pr113RuntimeTabActive(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) return null;
  try {
    const tab = await chrome.tabs.get(tabId);
    return tab?.active === true;
  } catch {
    return null;
  }
}

async function _pr113SubmitTextWithMouseOnce(
  debuggee,
  point
) {
  const x = Number(point?.x);
  const y = Number(point?.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error("CHATGPT_SEND_BUTTON_POINT_INVALID");
  }

  // Mouse commit is permitted only when the runtime tab is already active.
  // Background turns must use the protected Enter boundary instead of changing
  // the user's active tab.
  const tabActive = await _pr113RuntimeTabActive(debuggee);
  if (tabActive !== true) {
    throw new Error("PR11_3_MOUSE_COMMIT_REQUIRES_ALREADY_ACTIVE_TAB");
  }

  await sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x,
    y
  });
  await sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x,
    y,
    button: "left",
    clickCount: 1
  });

  try {
    await sendCommand(debuggee, "Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1
    });
  } catch {
    throw new Error(PR113_MOUSE_RELEASE_UNCONFIRMED);
  }

  return {
    strategy: "send_button_click",
    selector: point?.selector ?? null
  };
}

async function _pr113SubmitOfficialTextWithoutPostCommitRetry(
  debuggee,
  timeoutMs,
  next
) {
  if (_pr113SpecialSubmitContextActive()) {
    return next(debuggee, timeoutMs);
  }

  const tabActive = await _pr113RuntimeTabActive(debuggee);
  if (tabActive !== true) {
    return _pr113SubmitTextWithEnterOnce(debuggee);
  }

  let point = null;
  try {
    point = await _pr113WaitForSubmitPoint(
      debuggee,
      Math.min(timeoutMs, DEFAULT_SUBMIT_READY_TIMEOUT_MS)
    );
  } catch {
    return _pr113SubmitTextWithEnterOnce(debuggee);
  }

  try {
    return await _pr113SubmitTextWithMouseOnce(debuggee, point);
  } catch (error) {
    if (_pr113IsMouseReleaseOutcomeUnconfirmed(error)) {
      throw error;
    }
    return _pr113SubmitTextWithEnterOnce(debuggee);
  }
}
