// PR9.2 deadline-boundary repair overlay.
//
// Loaded after service_worker_rich_input_pr9_2.js. The original PR9.2 overlay
// owns recovery-before-staging and the durable stale-attachment fence; this
// final layer closes the remaining authority gaps at the exact protected-submit
// boundary and across post-write cleanup without changing text-only behavior.

const _pr92DeadlineRepairPriorClickSendButton = clickSendButton;
const _pr92DeadlineRepairPriorSubmitWithEnter = submitWithEnter;
const _pr92DeadlineRepairPriorTryClearDirtyAttachmentFence = (
  _pr92TryClearDirtyAttachmentFence
);
const _pr92DeadlineRepairPriorExecuteNativeTurn = executeNativeTurn;
const PR92_DEADLINE_REPAIR_SCHEMA = 2;

function _pr92DeadlineRepairTimeoutError(stage) {
  return new Error(`PR9_2_TOTAL_TURN_TIMEOUT:${stage}`);
}

function _pr92DeadlineRepairRemainingMs(deadlineAt, stage) {
  const remaining = Math.ceil(deadlineAt - performance.now());
  if (!Number.isFinite(remaining) || remaining <= 0) {
    throw _pr92DeadlineRepairTimeoutError(stage);
  }
  return remaining;
}

function _pr92DeadlineRepairDeadlineFromBudget(timeoutMs) {
  const now = performance.now();
  let deadlineAt = now + Math.max(1, Number(timeoutMs) || 1);
  const context = _pr92ActiveTurnContext;
  if (context && Number.isFinite(context.deadlineAt)) {
    deadlineAt = Math.min(deadlineAt, context.deadlineAt);
  }
  return deadlineAt;
}

async function _pr92DeadlineRepairRunUntil(deadlineAt, stage, operation) {
  const remaining = _pr92DeadlineRepairRemainingMs(deadlineAt, stage);
  let timer = null;
  try {
    return await Promise.race([
      Promise.resolve().then(operation),
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(_pr92DeadlineRepairTimeoutError(stage)),
          remaining
        );
      })
    ]);
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}

function _pr92DeadlineRepairRichContext() {
  return _pr92ActiveRichInputContext;
}

// The actual conversation write can be triggered by mouse release or Enter.
// Guard those exact CDP input events, rather than trusting nested timeoutMs
// values in the older page-turn chain whose prewrite waits can floor an expired
// budget back to one second.
clickSendButton = async function _pr92ClickSendButtonWithinDeadline(debuggee, point) {
  const context = _pr92DeadlineRepairRichContext();
  if (context === null) {
    return _pr92DeadlineRepairPriorClickSendButton(debuggee, point);
  }

  const x = Number(point?.x);
  const y = Number(point?.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error("CHATGPT_SEND_BUTTON_POINT_INVALID");
  }

  await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "PRE_SUBMIT_MOUSE_MOVE",
    () => chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
      type: "mouseMoved",
      x,
      y,
      button: "none"
    })
  );
  await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "PRE_SUBMIT_MOUSE_PRESS",
    () => chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1
    })
  );
  await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "PRE_SUBMIT_MOUSE_RELEASE",
    () => chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1
    })
  );
};

submitWithEnter = async function _pr92SubmitWithEnterWithinDeadline(debuggee) {
  const context = _pr92DeadlineRepairRichContext();
  if (context === null) {
    return _pr92DeadlineRepairPriorSubmitWithEnter(debuggee);
  }

  await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "PRE_SUBMIT_ENTER_KEY_DOWN",
    () => chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13
    })
  );
  await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "POST_SUBMIT_ENTER_KEY_UP",
    () => chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13
    })
  );
};

async function _pr92DeadlineRepairBestEffortReleaseObject(
  debuggee,
  objectId,
  deadlineAt
) {
  if (!objectId) return;
  try {
    if (performance.now() < deadlineAt) {
      await _pr92DeadlineRepairRunUntil(
        deadlineAt,
        "CLEANUP_RELEASE_OBJECT",
        () => chrome.debugger.sendCommand(debuggee, "Runtime.releaseObject", { objectId })
      );
    } else {
      chrome.debugger.sendCommand(
        debuggee,
        "Runtime.releaseObject",
        { objectId }
      ).catch(() => {});
    }
  } catch {}
}

async function _pr92DeadlineRepairBestEffortDetach(debuggee, deadlineAt) {
  try {
    if (performance.now() < deadlineAt) {
      await _pr92DeadlineRepairRunUntil(
        deadlineAt,
        "CLEANUP_DEBUGGER_DETACH",
        () => chrome.debugger.detach(debuggee)
      );
    } else {
      chrome.debugger.detach(debuggee).catch(() => {});
    }
  } catch {}
}

// Replace the original cleanup helper so every awaited browser operation shares
// one local cleanup deadline, itself capped by the outer rich-turn deadline.
// Expiry returns false and leaves the durable fence authoritative.
_pr92ClearOfficialPageAttachments = async function _pr92ClearAttachmentsWithinDeadline(
  tabId,
  timeoutMs
) {
  if (!Number.isInteger(tabId) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return false;
  }

  const deadlineAt = _pr92DeadlineRepairDeadlineFromBudget(timeoutMs);
  try {
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_TAB_LOOKUP",
      () => chrome.tabs.get(tabId)
    );
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")
    ) {
      return false;
    }
    // A synchronously proven removed tab cannot retain a stale composer.
    return true;
  }

  try {
    const remaining = _pr92DeadlineRepairRemainingMs(
      deadlineAt,
      "CLEANUP_TAB_COMPLETE"
    );
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_TAB_COMPLETE",
      () => waitForTabComplete(tabId, Math.max(1, Math.min(remaining, 10_000)))
    );
  } catch {
    return false;
  }

  const debuggee = { tabId };
  let attached = false;
  let objectId = null;
  try {
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_DEBUGGER_ATTACH",
      () => chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION)
    );
    attached = true;
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_DOM_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "DOM.enable")
    );
    objectId = await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_FILE_INPUT_LOOKUP",
      () => _pr92FindFileInputObjectId(debuggee)
    );
    if (!objectId) return false;
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_FILE_SELECTION_CLEAR",
      () => chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
        files: [],
        objectId
      })
    );
    return true;
  } catch {
    return false;
  } finally {
    if (objectId) {
      await _pr92DeadlineRepairBestEffortReleaseObject(
        debuggee,
        objectId,
        deadlineAt
      );
    }
    if (attached) {
      await _pr92DeadlineRepairBestEffortDetach(debuggee, deadlineAt);
    }
  }
};

// Never remove the durable fence in the same rich turn after attachment staging.
// Even after file-input cleanup succeeds, returning the completed write takes
// priority over a late storage mutation. The next turn re-proves cleanup before
// clearing the fence and before any subsequent write authority is available.
_pr92TryClearDirtyAttachmentFence = async function _pr92ClearFenceWithinDeadline() {
  const richContext = _pr92ActiveRichInputContext;
  if (richContext !== null && richContext.staged === true) {
    return false;
  }

  const context = _pr92ActiveTurnContext;
  if (context === null) {
    return _pr92DeadlineRepairPriorTryClearDirtyAttachmentFence();
  }

  try {
    return await _pr92DeadlineRepairRunUntil(
      context.deadlineAt,
      "STALE_ATTACHMENT_FENCE_CLEAR",
      async () => {
        await chrome.storage.local.remove(PR92_DIRTY_ATTACHMENT_STORAGE_KEY);
        _pr92DirtyAttachmentTabId = null;
        return true;
      }
    );
  } catch {
    return false;
  }
};

// Advance the no-write support contract so an installed pre-repair overlay cannot
// satisfy the authenticated live gate merely because ordinary writes do not hit
// the deadline edge cases during that run.
executeNativeTurn = async function _executeNativeTurnWithPr92DeadlineRepair(message) {
  const result = await _pr92DeadlineRepairPriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_DEADLINE_REPAIR_SCHEMA,
    preSubmitDeadlineGuard: true,
    deadlineBoundedPostWriteCleanup: true,
    postWriteFenceRetainedUntilNextPrewrite: true
  };
};
