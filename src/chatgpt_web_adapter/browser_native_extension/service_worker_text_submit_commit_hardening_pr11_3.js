// PR11.3 ordinary-text protected-submit hardening.
//
// Rich-input and Temporary Chat turns already have specialized submit authority
// chains. This layer delegates those contexts unchanged and fixes only ordinary
// browser-owned text submission: Enter fallback is permitted only before the
// click commit boundary is attempted. Once mouseReleased is delegated, the
// outcome is ambiguous on ACK loss and a second submit is forbidden.

const _pr113PriorSubmitOfficialPageTurn = submitOfficialPageTurn;
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

async function _pr113SubmitTextWithEnterOnce(debuggee) {
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

  return { strategy: "enter_fallback", selector: null };
}

async function _pr113SubmitTextWithMouseOnce(debuggee, point) {
  const x = Number(point?.x);
  const y = Number(point?.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error("CHATGPT_SEND_BUTTON_POINT_INVALID");
  }

  // move/press are pre-commit for the established CWA click contract. If either
  // fails, Enter remains a single safe fallback because mouseReleased has not
  // been attempted.
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

  // mouseReleased is the click protected-write boundary. Mark the outcome
  // ambiguous as soon as the command is attempted: a rejected/lost CDP ACK can
  // coexist with a real page click and therefore can never authorize Enter.
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

  return { strategy: "send_button_click", selector: point?.selector ?? null };
}

submitOfficialPageTurn = async function _pr113SubmitOfficialTextWithoutPostCommitRetry(
  debuggee,
  timeoutMs
) {
  if (_pr113SpecialSubmitContextActive()) {
    return _pr113PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
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
};
