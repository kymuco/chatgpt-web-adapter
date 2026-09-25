// PR9.2 schema-12 post-stage / send-readiness deadline repair.
//
// Loaded after schema 11. This immutable layer closes the two fresh exact-head
// closure-review findings without weakening any earlier rich-input authority:
//   1. the post-stage debugger attach + Runtime.enable used to observe page-owned
//      attachment evidence are bounded by the one outer rich-turn deadline, with
//      best-effort detach if a non-cancellable attach completes only after timeout;
//   2. the complete Send-readiness wait is bounded by that same outer deadline,
//      including any stalled Runtime.evaluate inside querySendButtonPoint.

const _pr92Schema12PriorWaitForSendButtonPoint = waitForSendButtonPoint;
const PR92_SCHEMA12_REPAIR_SCHEMA = 12;

function _pr92Schema12BestEffortDetach(debuggee) {
  // Reuse schema 10's reviewed non-blocking detach semantics when available.
  if (typeof _pr92Schema10BestEffortDetach === "function") {
    _pr92Schema10BestEffortDetach(debuggee);
    return;
  }
  try {
    const pending = chrome.debugger.detach(debuggee);
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

async function _pr92Schema12ObservePostStageAttachmentEvidence(
  tabId,
  attachmentPaths,
  context
) {
  const debuggee = { tabId };
  let attached = false;
  let attachPending = null;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA12_POSTSTAGE_EVIDENCE_ATTACH");
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    if (attachPending && typeof attachPending.catch === "function") {
      attachPending.catch(() => {});
    }

    try {
      await _pr92Schema7RunUntil(
        context.deadlineAt,
        "SCHEMA12_POSTSTAGE_DEBUGGER_ATTACH",
        () => attachPending
      );
      attached = true;
    } catch (error) {
      // debugger.attach cannot be cancelled. If it acquires ownership after the
      // deadline race has already failed, relinquish that late ownership without
      // extending or changing the reported timeout outcome.
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
      "SCHEMA12_POSTSTAGE_RUNTIME_ENABLE",
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
    if (attached) _pr92Schema12BestEffortDetach(debuggee);
  }
}

// Preserve schema-10 official-composer cleanliness before any file selection,
// then invoke the explicit base staging primitive that performs DOM.setFileInputFiles
// and persists the durable fence. Schema 12 adds the same stable latest-generation
// page-owned evidence proof with deadline-bounded debugger setup.
async function _pr92Schema12StageWithBoundedPostStageEvidence(
  tabId,
  attachmentPaths,
  context
) {
  if (attachmentPaths.length === 0) return 0;

  await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(tabId, context);
  const stagedCount = await _pr92BaseStageOfficialPageAttachments(
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
}

// Schema 7 owns the final atomic attachment-validation + click implementation, but
// its readiness helper can internally await Runtime.evaluate beyond readyBudget.
// Bound the complete helper invocation by the authoritative outer rich-turn deadline.
// A late readiness read has no write authority and cannot trigger submission.
waitForSendButtonPoint = async function _pr92Schema12DeadlineBoundedSendReadiness(
  debuggee,
  timeoutMs
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92Schema12PriorWaitForSendButtonPoint(debuggee, timeoutMs);
  }
  return _pr92Schema7RunUntil(
    context.deadlineAt,
    "SCHEMA12_SEND_READINESS_WAIT",
    () => _pr92Schema12PriorWaitForSendButtonPoint(debuggee, timeoutMs)
  );
};

function _pr92Schema12AugmentSupportResult(result) {
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA12_REPAIR_SCHEMA,
    postStageDebuggerSetupDeadlineBounded: true,
    latePostStageDebuggerAttachAutoDetached: true,
    sendReadinessWaitDeadlineBounded: true
  };
}
