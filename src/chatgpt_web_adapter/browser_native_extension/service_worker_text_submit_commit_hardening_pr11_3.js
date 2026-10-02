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

async function _pr113PrepareMouseCommitTab(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) {
    return {
      activated: false,
      tabId: null,
      previousActiveTabId: null
    };
  }

  const tab = await chrome.tabs.get(tabId);
  if (tab?.active === true) {
    return {
      activated: false,
      tabId,
      previousActiveTabId: null
    };
  }

  let previousActiveTabId = null;
  if (Number.isInteger(tab?.windowId)) {
    try {
      const activeTabs = await chrome.tabs.query({
        active: true,
        windowId: tab.windowId
      });
      const previous = activeTabs.find(
        (candidate) =>
          Number.isInteger(candidate?.id) &&
          candidate.id !== tabId
      );
      previousActiveTabId = Number.isInteger(previous?.id)
        ? previous.id
        : null;
    } catch {
      previousActiveTabId = null;
    }
  }

  const activated = await chrome.tabs.update(tabId, { active: true });
  if (activated?.active !== true) {
    const current = await chrome.tabs.get(tabId);
    if (current?.active !== true) {
      throw new Error("PR11_3_COMMIT_TAB_ACTIVATION_NOT_PROVEN");
    }
  }

  return {
    activated: true,
    tabId,
    previousActiveTabId
  };
}

async function _pr113RestoreMouseCommitTab(state) {
  if (
    state?.activated !== true ||
    !Number.isInteger(state?.previousActiveTabId)
  ) {
    return;
  }
  try {
    await chrome.tabs.update(state.previousActiveTabId, { active: true });
  } catch {
    // Selection restoration is post-commit cleanup only. It must never rewrite
    // a possibly committed product write into a local failure.
  }
}


function _pr113SubmitEventProbeInstallExpression(x, y) {
  return `(() => {
    const key = "__cwaPr171SubmitEventProbeV1";
    try {
      const previous = globalThis[key];
      if (previous?.listeners && Array.isArray(previous.listeners)) {
        for (const item of previous.listeners) {
          try {
            window.removeEventListener(item.type, item.listener, item.capture);
          } catch {}
        }
      }

      const hit = document.elementFromPoint(${JSON.stringify(x)}, ${JSON.stringify(y)});
      if (!hit) return { installed: false, reason: "no_hit" };
      const button = hit?.closest?.("button") || null;
      if (!button) {
        return {
          installed: false,
          reason: "no_button",
          hitTag: String(hit?.tagName || "").toLowerCase() || null
        };
      }
      const form = button?.closest?.("form") || null;
      if (!form) {
        return {
          installed: false,
          reason: "no_form",
          hitTag: String(hit?.tagName || "").toLowerCase() || null
        };
      }
      const state = {
        button,
        form,
        listeners: [],
        pointerDownSeen: false,
        mouseDownSeen: false,
        pointerUpSeen: false,
        mouseUpSeen: false,
        clickSeen: false,
        submitSeen: false,
        allTrusted: true,
        clickDefaultPrevented: null,
        submitDefaultPrevented: null,
        clickTargetWithinButton: null,
        submitterIsButton: null
      };

      const observe = (type, capture) => {
        const listener = (event) => {
          if (event?.isTrusted !== true) state.allTrusted = false;
          if (type === "pointerdown") state.pointerDownSeen = true;
          if (type === "mousedown") state.mouseDownSeen = true;
          if (type === "pointerup") state.pointerUpSeen = true;
          if (type === "mouseup") state.mouseUpSeen = true;
          if (type === "click") {
            state.clickSeen = true;
            if (!capture) {
              state.clickDefaultPrevented = event.defaultPrevented === true;
              state.clickTargetWithinButton = Boolean(
                state.button &&
                event.target instanceof Node &&
                state.button.contains(event.target)
              );
            }
          }
          if (type === "submit") {
            state.submitSeen = true;
            if (!capture) {
              state.submitDefaultPrevented = event.defaultPrevented === true;
              state.submitterIsButton = event.submitter === state.button;
            }
          }
        };
        window.addEventListener(type, listener, { capture, passive: true });
        state.listeners.push({ type, listener, capture });
      };

      for (const type of [
        "pointerdown",
        "mousedown",
        "pointerup",
        "mouseup",
        "click",
        "submit"
      ]) {
        observe(type, true);
        observe(type, false);
      }

      globalThis[key] = state;
      return {
        installed: true,
        reason: "installed",
        hitTag: String(hit?.tagName || "").toLowerCase() || null
      };
    } catch (error) {
      return {
        installed: false,
        reason: "exception",
        errorName: typeof error?.name === "string" ? error.name : null
      };
    }
  })()`;
}

function _pr113SubmitEventProbeReadExpression() {
  return `(() => {
    const key = "__cwaPr171SubmitEventProbeV1";
    const state = globalThis[key];
    if (!state) return null;
    try {
      for (const item of state.listeners || []) {
        try {
          window.removeEventListener(item.type, item.listener, item.capture);
        } catch {}
      }
      return {
        pointerDownSeen: state.pointerDownSeen === true,
        mouseDownSeen: state.mouseDownSeen === true,
        pointerUpSeen: state.pointerUpSeen === true,
        mouseUpSeen: state.mouseUpSeen === true,
        clickSeen: state.clickSeen === true,
        submitSeen: state.submitSeen === true,
        allTrusted: state.allTrusted === true,
        clickDefaultPrevented: state.clickDefaultPrevented,
        submitDefaultPrevented: state.submitDefaultPrevented,
        clickTargetWithinButton: state.clickTargetWithinButton,
        submitterIsButton: state.submitterIsButton
      };
    } finally {
      try { delete globalThis[key]; } catch {}
    }
  })()`;
}

async function _pr113InstallSubmitEventProbe(debuggee, x, y) {
  try {
    const result = await sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr113SubmitEventProbeInstallExpression(x, y),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (!value || typeof value !== "object") {
      return { installed: false, reason: "invalid_result" };
    }
    return {
      installed: value.installed === true,
      reason: typeof value.reason === "string" ? value.reason : "unknown",
      hitTag: typeof value.hitTag === "string" ? value.hitTag : null,
      errorName: typeof value.errorName === "string" ? value.errorName : null
    };
  } catch (error) {
    return {
      installed: false,
      reason: "cdp_error",
      errorName: typeof error?.name === "string" ? error.name : null
    };
  }
}

async function _pr113ReadSubmitEventProbe(debuggee) {
  const attempt = Promise.resolve(
    sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr113SubmitEventProbeReadExpression(),
      returnByValue: true,
      awaitPromise: true
    })
  ).then((result) => result?.result?.value || null).catch(() => null);

  try {
    return await Promise.race([
      attempt,
      sleep(250).then(() => null)
    ]);
  } catch {
    return null;
  }
}

function _pr113FormatSubmitEventProbe(probe) {
  if (!probe || typeof probe !== "object") return "unavailable";
  const bit = (value) => value === true ? "1" : "0";
  const tri = (value) => value === true ? "1" : (value === false ? "0" : "n");
  return [
    `pd=${bit(probe.pointerDownSeen)}`,
    `md=${bit(probe.mouseDownSeen)}`,
    `pu=${bit(probe.pointerUpSeen)}`,
    `mu=${bit(probe.mouseUpSeen)}`,
    `click=${bit(probe.clickSeen)}`,
    `submit=${bit(probe.submitSeen)}`,
    `trusted=${bit(probe.allTrusted)}`,
    `click_prevented=${tri(probe.clickDefaultPrevented)}`,
    `submit_prevented=${tri(probe.submitDefaultPrevented)}`,
    `click_on_button=${tri(probe.clickTargetWithinButton)}`,
    `submitter_button=${tri(probe.submitterIsButton)}`
  ].join(",");
}

async function _pr113SubmitTextWithMouseOnce(
  debuggee,
  point,
  timeoutMs = DEFAULT_SUBMIT_READY_TIMEOUT_MS
) {
  const initialX = Number(point?.x);
  const initialY = Number(point?.y);
  if (!Number.isFinite(initialX) || !Number.isFinite(initialY)) {
    throw new Error("CHATGPT_SEND_BUTTON_POINT_INVALID");
  }

  // Current ChatGPT may update composer geometry when the browser-owned runtime
  // tab becomes foreground. Activate first, then re-resolve the product-owned
  // Send control before the protected mouse commit. The re-resolution is still
  // pre-commit and therefore cannot authorize or duplicate a product write.
  const commitTab = await _pr113PrepareMouseCommitTab(debuggee);
  let eventProbe = { installed: false, reason: "not_attempted" };
  let eventProbeConsumed = false;

  try {
    let commitPoint = point;
    if (commitTab.activated === true) {
      commitPoint = await _pr113WaitForSubmitPoint(
        debuggee,
        Math.min(timeoutMs, DEFAULT_SUBMIT_READY_TIMEOUT_MS)
      );
    }

    const x = Number(commitPoint?.x);
    const y = Number(commitPoint?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error("CHATGPT_SEND_BUTTON_POINT_INVALID_AFTER_ACTIVATION");
    }

    const submitPointDeltaPx = Math.round(
      Math.hypot(x - initialX, y - initialY)
    );

    eventProbe = await _pr113InstallSubmitEventProbe(debuggee, x, y);

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

    const eventTrace = eventProbe.installed === true
      ? await _pr113ReadSubmitEventProbe(debuggee)
      : null;
    eventProbeConsumed = eventProbe.installed === true;

    return {
      strategy: "send_button_click",
      selector: commitPoint?.selector ?? null,
      tabActivatedForCommit: commitTab.activated === true,
      submitPointRefreshedAfterActivation: commitTab.activated === true,
      submitPointDeltaPx,
      eventProbeInstalled: eventProbe.installed === true,
      eventProbeInstallReason: eventProbe.reason || "unknown",
      eventProbeHitTag: eventProbe.hitTag || null,
      eventProbeErrorName: eventProbe.errorName || null,
      eventProbeSummary: _pr113FormatSubmitEventProbe(eventTrace)
    };
  } finally {
    if (eventProbe.installed === true && eventProbeConsumed !== true) {
      await _pr113ReadSubmitEventProbe(debuggee);
    }
    await _pr113RestoreMouseCommitTab(commitTab);
  }
}

async function _pr113SubmitOfficialTextWithoutPostCommitRetry(
  debuggee,
  timeoutMs,
  next
) {
  if (_pr113SpecialSubmitContextActive()) {
    return next(debuggee, timeoutMs);
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
    return await _pr113SubmitTextWithMouseOnce(debuggee, point, timeoutMs);
  } catch (error) {
    if (_pr113IsMouseReleaseOutcomeUnconfirmed(error)) {
      throw error;
    }
    return _pr113SubmitTextWithEnterOnce(debuggee);
  }
}
