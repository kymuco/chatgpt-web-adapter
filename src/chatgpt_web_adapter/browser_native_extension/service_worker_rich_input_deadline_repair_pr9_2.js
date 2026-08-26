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
const PR92_DEADLINE_REPAIR_SCHEMA = 3;

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

function _pr92DeadlineRepairIsTimeoutError(error) {
  return Boolean(
    error instanceof Error &&
    error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")
  );
}

function _pr92DeadlineRepairIsMissingTabError(error) {
  const message = error instanceof Error ? error.message : String(error || "");
  return /no tab with id|invalid tab id|tab not found/i.test(message);
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

  // keyDown is the protected write boundary. If it succeeds, the conversation may
  // already be delegated. A later keyUp must therefore never convert that submitted
  // outcome into a local timeout/error. Dispatch release best-effort and return
  // immediately so post-submit housekeeping cannot consume the remaining RPC budget.
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
  try {
    chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13
    }).catch(() => {});
  } catch {}
};

async function _pr92DeadlineRepairProveTabAbsent(tabId, deadlineAt) {
  try {
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_TAB_ABSENCE_CONFIRM",
      () => chrome.tabs.get(tabId)
    );
    return false;
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
    return _pr92DeadlineRepairIsMissingTabError(error);
  }
}

// Clearing input.files is not sufficient cleanup authority: the product page may
// already have ingested the file into composer/upload state. For a durable dirty
// fence, the only generic proof available without reconstructing product internals
// is destruction of the dedicated runtime tab followed by explicit absence proof.
// The same rich turn never performs that destructive cleanup; it returns/throws
// with the fence intact. The next prewrite closes the dirty tab under its own outer
// deadline, proves it no longer exists, and only then may clear the durable fence.
_pr92ClearOfficialPageAttachments = async function _pr92ClearAttachmentsWithinDeadline(
  tabId,
  timeoutMs
) {
  if (!Number.isInteger(tabId) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return false;
  }

  const richContext = _pr92ActiveRichInputContext;
  if (richContext !== null && richContext.staged === true) {
    return false;
  }

  const deadlineAt = _pr92DeadlineRepairDeadlineFromBudget(timeoutMs);
  try {
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_TAB_LOOKUP",
      () => chrome.tabs.get(tabId)
    );
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
    return _pr92DeadlineRepairIsMissingTabError(error);
  }

  try {
    await _pr92DeadlineRepairRunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_TAB_CLOSE",
      () => chrome.tabs.remove(tabId)
    );
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
    // A concurrent close can race this call. Only explicit subsequent absence
    // proof can turn that race into successful cleanup authority.
  }

  return _pr92DeadlineRepairProveTabAbsent(tabId, deadlineAt);
};

// Never remove the durable fence in the same rich turn after attachment staging.
// Even after cleanup succeeds, returning the completed write takes priority over
// a late storage mutation. The next turn re-proves cleanup before clearing the
// fence and before any subsequent write authority is available.
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
    postWriteFenceRetainedUntilNextPrewrite: true,
    enterKeyReleaseAffectsSubmittedOutcome: false,
    staleAttachmentCleanupProof: "RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED"
  };
};
