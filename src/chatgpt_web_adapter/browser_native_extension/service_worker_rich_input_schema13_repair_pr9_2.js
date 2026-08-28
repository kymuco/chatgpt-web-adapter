// PR9.2 schema-13 attachment-staging deadline repair.
//
// Loaded after schema 12. This immutable layer closes the fresh exact-head
// review finding that the *actual* file-selection staging primitive still used
// raw CDP awaits captured from schema 1. Every awaited staging phase is now
// governed by the one outer rich-turn deadline. Non-cancellable file selection
// is dispatched only after the durable stale-composer fence has been proven;
// if its acknowledgement loses the deadline race, the turn fails closed and
// the fence remains authoritative for the next prewrite cleanup.

const _pr92Schema13PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA13_REPAIR_SCHEMA = 13;

function _pr92Schema13BestEffortDetach(debuggee) {
  if (typeof _pr92Schema12BestEffortDetach === "function") {
    _pr92Schema12BestEffortDetach(debuggee);
    return;
  }
  try {
    const pending = chrome.debugger.detach(debuggee);
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

function _pr92Schema13BestEffortReleaseObject(debuggee, objectId) {
  if (typeof objectId !== "string" || !objectId) return;
  try {
    const pending = chrome.debugger.sendCommand(
      debuggee,
      "Runtime.releaseObject",
      { objectId }
    );
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

async function _pr92Schema13AttachWithinDeadline(debuggee, context) {
  _pr92RemainingTurnMs(context, "SCHEMA13_STAGE_DEBUGGER_ATTACH");
  let attachPending;
  try {
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
  } catch (error) {
    throw error;
  }
  if (attachPending && typeof attachPending.catch === "function") {
    attachPending.catch(() => {});
  }

  try {
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_DEBUGGER_ATTACH",
      () => attachPending
    );
    return true;
  } catch (error) {
    // debugger.attach cannot be cancelled. If ownership is acquired only after
    // the local timeout, relinquish it without extending/changing the outcome.
    if (attachPending && typeof attachPending.then === "function") {
      attachPending.then(
        () => _pr92Schema13BestEffortDetach(debuggee),
        () => {}
      );
    }
    throw error;
  }
}

async function _pr92Schema13FindFileInputWithinDeadline(debuggee, context, stage) {
  return _pr92Schema7RunUntil(
    context.deadlineAt,
    stage,
    () => _pr92FindFileInputObjectId(debuggee)
  );
}

async function _pr92Schema13RevealFileInputWithinDeadline(debuggee, context) {
  const remaining = _pr92RemainingTurnMs(context, "SCHEMA13_REVEAL_FILE_INPUT");
  const pageDeadlineEpochMs = Date.now() + remaining;
  const encodedDeadline = JSON.stringify(pageDeadlineEpochMs);
  const expression = `(() => {
    const deadlineEpochMs = ${encodedDeadline};
    if (!Number.isFinite(deadlineEpochMs) || Date.now() >= deadlineEpochMs) {
      return null;
    }
    const selectors = [
      'button[data-testid="composer-plus-btn"]',
      'button[data-testid="composer-button-add-files"]',
      'button[aria-label*="Attach"]',
      'button[aria-label*="attach"]',
      'button[aria-label*="Upload"]',
      'button[aria-label*="Add files"]',
      'button[aria-label*="Прикреп"]'
    ];
    for (const selector of selectors) {
      if (Date.now() >= deadlineEpochMs) return null;
      const button = document.querySelector(selector);
      if (!(button instanceof HTMLElement)) continue;
      const rect = button.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      const style = getComputedStyle(button);
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        continue;
      }
      if (Date.now() >= deadlineEpochMs) return null;
      button.click();
      return selector;
    }
    return null;
  })()`;

  try {
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_REVEAL_FILE_INPUT_EVALUATE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: false
      })
    );
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")
    ) {
      throw error;
    }
    // Reveal remains only a compatibility aid. A non-timeout failure falls
    // through to the second bounded file-input lookup and fails closed there.
  }

  await _pr92BoundedSleep(
    context,
    100,
    "SCHEMA13_REVEAL_FILE_INPUT_SETTLE"
  );
}

async function _pr92Schema13StageFileSelection(tabId, attachmentPaths, context) {
  if (attachmentPaths.length === 0) return 0;

  const debuggee = { tabId };
  let attached = false;
  let objectId = null;
  try {
    attached = await _pr92Schema13AttachWithinDeadline(debuggee, context);

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_DOM_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "DOM.enable")
    );

    const readyBudget = Math.min(
      _pr92RemainingTurnMs(context, "SCHEMA13_STAGE_COMPOSER_READY"),
      DEFAULT_READY_TIMEOUT_MS
    );
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_COMPOSER_READY",
      () => waitForComposerReady(debuggee, readyBudget)
    );

    objectId = await _pr92Schema13FindFileInputWithinDeadline(
      debuggee,
      context,
      "SCHEMA13_STAGE_FILE_INPUT_LOOKUP"
    );
    if (!objectId) {
      await _pr92Schema13RevealFileInputWithinDeadline(debuggee, context);
      objectId = await _pr92Schema13FindFileInputWithinDeadline(
        debuggee,
        context,
        "SCHEMA13_STAGE_FILE_INPUT_LOOKUP_AFTER_REVEAL"
      );
    }
    if (!objectId) throw new Error("PR9_2_FILE_INPUT_NOT_FOUND");

    // The fence is the authority that makes a late/non-cancellable file selection
    // fail closed. Do not dispatch DOM.setFileInputFiles until persistence itself
    // has completed inside the outer deadline.
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_FENCE_PERSIST",
      () => _pr92PersistDirtyAttachmentFence(tabId)
    );
    if (!Number.isInteger(_pr92DirtyAttachmentTabId) || _pr92DirtyAttachmentTabId !== tabId) {
      throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_PERSIST_FAILED");
    }

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA13_STAGE_FILE_SELECTION",
      () => chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
        files: attachmentPaths,
        objectId
      })
    );

    await _pr92BoundedSleep(
      context,
      100,
      "SCHEMA13_STAGE_SELECTION_SETTLE"
    );
    return attachmentPaths.length;
  } catch (error) {
    if (
      error instanceof Error &&
      (
        error.message === "PR9_2_FILE_INPUT_NOT_FOUND" ||
        error.message.startsWith("PR9_2_STALE_ATTACHMENT_FENCE_") ||
        error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")
      )
    ) {
      throw error;
    }
    throw new Error("PR9_2_ATTACHMENT_STAGE_FAILED");
  } finally {
    // Cleanup after a command that may already have selected local files must not
    // extend the RPC or convert a bounded staging outcome into response loss.
    // The durable fence, not successful release/detach, is cleanup authority.
    _pr92Schema13BestEffortReleaseObject(debuggee, objectId);
    if (attached) _pr92Schema13BestEffortDetach(debuggee);
  }
}

// Replace schema 12's staging wrapper at the exact primitive that selects files.
// Preserve schema-10 official-composer cleanliness before selection and schema-12
// deadline-bounded post-stage page-owned evidence after selection.
_pr92StageOfficialPageAttachments = async function _pr92Schema13FullyBoundedStage(
  tabId,
  attachmentPaths,
  context
) {
  if (attachmentPaths.length === 0) return 0;

  await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(tabId, context);
  const stagedCount = await _pr92Schema13StageFileSelection(
    tabId,
    attachmentPaths,
    context
  );
  if (stagedCount !== attachmentPaths.length) {
    throw new Error("PR9_2_ATTACHMENT_STAGE_COUNT_MISMATCH");
  }

  return _pr92Schema12ObservePostStageAttachmentEvidence(
    tabId,
    attachmentPaths,
    context
  );
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema13Repair(message) {
  const result = await _pr92Schema13PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA13_REPAIR_SCHEMA,
    attachmentStagingPrimitiveDeadlineBounded: true,
    stagingDebuggerSetupDeadlineBounded: true,
    stagingComposerReadinessDeadlineBounded: true,
    stagingFileInputLookupDeadlineBounded: true,
    stagingFencePersistenceDeadlineBounded: true,
    stagingFileSelectionDeadlineBounded: true,
    lateStagingDebuggerAttachAutoDetached: true,
    lateFileSelectionFailsClosedBehindDurableFence: true,
    postSelectionCleanupNonBlocking: true
  };
};
