// PR9.2 schema-15 debugger-ownership handoff repair.
//
// Loaded after schema 14. Schema 10 and schema 12 correctly bound debugger
// acquisition and evidence work, but their successful observer paths released
// debugger ownership with fire-and-forget detach. The next rich-input phase can
// immediately need the same tab and therefore race that still-pending detach.
// This immutable layer makes both *successful* ownership handoffs explicit:
// detach must complete inside the same outer rich-turn deadline before the next
// phase may attach. Error/timeout paths retain the reviewed best-effort detach
// semantics and cannot extend or rewrite the already reported failure outcome.

const _pr92Schema15PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA15_REPAIR_SCHEMA = 15;

async function _pr92Schema15DetachWithinDeadline(debuggee, context, stage) {
  _pr92RemainingTurnMs(context, stage);
  return _pr92Schema7RunUntil(
    context.deadlineAt,
    stage,
    () => chrome.debugger.detach(debuggee)
  );
}

_pr92Schema10RequireOfficialCleanComposerBeforeStaging = async function _pr92Schema15RequireOfficialCleanComposerBeforeStaging(
  tabId,
  context
) {
  const debuggee = { tabId };
  let attached = false;
  let attachPending = null;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA15_PRESTAGE_CLEAN_ATTACH");
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    if (attachPending && typeof attachPending.catch === "function") {
      attachPending.catch(() => {});
    }

    try {
      await _pr92Schema7RunUntil(
        context.deadlineAt,
        "SCHEMA15_PRESTAGE_CLEAN_DEBUGGER_ATTACH",
        () => attachPending
      );
      attached = true;
    } catch (error) {
      // attach is non-cancellable. If it completes only after our deadline/error,
      // relinquish that late ownership without changing the failed outcome.
      if (attachPending && typeof attachPending.then === "function") {
        attachPending.then(
          () => _pr92Schema10BestEffortDetach(debuggee),
          () => {}
        );
      }
      throw error;
    }

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA15_PRESTAGE_CLEAN_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    let stable = 0;
    while (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
      const evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
        debuggee,
        [],
        context
      );
      const groupCount = Number(evidence?.groupLabelCount);
      const removalCount = Number(evidence?.removalLabelCount);
      const clean = evidence?.officialComposerMounted === true &&
        evidence?.exactBasenameAssociation === true &&
        evidence?.exactAttachmentSet === true &&
        groupCount === 0 && removalCount === 0;
      if (!clean) {
        throw new Error("PR9_2_OFFICIAL_COMPOSER_NOT_CLEAN_BEFORE_STAGING");
      }
      stable += 1;
      if (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA15_PRESTAGE_CLEAN_STABILITY"
        );
      }
    }

    // Success is not complete until debugger ownership is actually relinquished.
    // Schema 13 may attach for file selection immediately after this function.
    await _pr92Schema15DetachWithinDeadline(
      debuggee,
      context,
      "SCHEMA15_PRESTAGE_CLEAN_DEBUGGER_DETACH"
    );
    attached = false;
  } finally {
    // Only failure/timeout can arrive here still attached. Do not extend the
    // failed outcome; best-effort relinquish is sufficient on that path.
    if (attached) _pr92Schema10BestEffortDetach(debuggee);
  }
};

_pr92Schema12ObservePostStageAttachmentEvidence = async function _pr92Schema15ObservePostStageAttachmentEvidence(
  tabId,
  attachmentPaths,
  context
) {
  const debuggee = { tabId };
  let attached = false;
  let attachPending = null;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA15_POSTSTAGE_EVIDENCE_ATTACH");
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    if (attachPending && typeof attachPending.catch === "function") {
      attachPending.catch(() => {});
    }

    try {
      await _pr92Schema7RunUntil(
        context.deadlineAt,
        "SCHEMA15_POSTSTAGE_DEBUGGER_ATTACH",
        () => attachPending
      );
      attached = true;
    } catch (error) {
      // As above, a late successful non-cancellable attach is released without
      // changing the already failed/expired turn outcome.
      if (attachPending && typeof attachPending.then === "function") {
        attachPending.then(
          () => _pr92Schema12BestEffortDetach(debuggee),
          () => {}
        );
      }
      throw error;
    }

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA15_POSTSTAGE_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    const pageOwnedCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(
      debuggee,
      attachmentPaths,
      context,
      PR92_PAGE_ATTACHMENT_STABLE_POLLS
    );
    if (pageOwnedCount !== attachmentPaths.length) {
      throw new Error("PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH");
    }

    // The inherited protected-dispatch path attaches this debugger next. Do not
    // return page-owned evidence until the observer has fully relinquished it.
    await _pr92Schema15DetachWithinDeadline(
      debuggee,
      context,
      "SCHEMA15_POSTSTAGE_DEBUGGER_DETACH"
    );
    attached = false;
    return pageOwnedCount;
  } catch (error) {
    if (
      error instanceof Error &&
      (
        error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:") ||
        error.message === "PR9_2_PAGE_ATTACHMENT_REJECTED" ||
        error.message === "PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH"
      )
    ) {
      throw error;
    }
    throw new Error("PR9_2_PAGE_ATTACHMENT_EVIDENCE_FAILED");
  } finally {
    // A successful observer cleared `attached` only after bounded detach.
    // Error/timeout cleanup remains deliberately non-authoritative/best-effort.
    if (attached) _pr92Schema12BestEffortDetach(debuggee);
  }
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema15Repair(message) {
  const result = await _pr92Schema15PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA15_REPAIR_SCHEMA,
    preStageSuccessfulDebuggerDetachDeadlineBounded: true,
    postStageSuccessfulDebuggerDetachDeadlineBounded: true,
    debuggerOwnershipHandoffCompletedBeforeNextAttach: true,
    failurePathDebuggerDetachBestEffort: true
  };
};
