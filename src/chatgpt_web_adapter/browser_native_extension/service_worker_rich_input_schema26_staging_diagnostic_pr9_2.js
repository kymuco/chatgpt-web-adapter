// PR9.2 schema-26 staging-only live evidence diagnostic.
//
// This overlay does not advance the rich-input schema and grants no conversation
// write authority. Its explicit diagnostic RPC stages exactly one local fixture
// through the production attachment path, proves the schema-26 page-owned exact
// attachment evidence, snapshots the current composer DOM, and then invokes the
// existing durable-fence prewrite cleanup so the diagnostic cannot leave a usable
// stale attachment behind on a successful result.
//
// It never inserts text, never calls the prior page-turn chain, and never invokes a
// submit primitive. Staging may upload the selected file to the official page; that
// page mutation is reported explicitly and is distinct from a conversation write.

const _pr92Schema26StagingDiagnosticPriorExecuteNativeTurn = executeNativeTurn;

async function _pr92Schema26ReadStagedDiagnosticEvidence(tabId, attachmentPaths, context) {
  const debuggee = { tabId };
  let attached = false;
  try {
    attached = await _pr92Schema13AttachWithinDeadline(debuggee, context);
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA26_STAGING_DIAGNOSTIC_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );
    const pageOwnedEvidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
      debuggee,
      _pr92ClosureExpectedBasenames(attachmentPaths),
      context
    );
    const raw = await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA26_STAGING_DIAGNOSTIC_RAW_DOM",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
        expression: _pr92Schema23DiagnosticExpression(),
        returnByValue: true,
        awaitPromise: false
      })
    );
    const rawEvidence = raw?.result?.value || null;
    const normalizationProof = _pr92Schema26DiagnosticRemovalNormalization({
      evidence: rawEvidence
    });

    await _pr92Schema15DetachWithinDeadline(
      debuggee,
      context,
      "SCHEMA26_STAGING_DIAGNOSTIC_DEBUGGER_DETACH"
    );
    attached = false;
    return {
      pageOwnedEvidence,
      rawEvidence,
      normalizationProof
    };
  } finally {
    if (attached) _pr92Schema13BestEffortDetach(debuggee);
  }
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema26StagingDiagnostic(message) {
  if (message?.diagnosePr92StagedAttachmentEvidence !== true) {
    return _pr92Schema26StagingDiagnosticPriorExecuteNativeTurn(message);
  }
  if (message?.text != null) {
    throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_TEXT_FORBIDDEN");
  }
  if (_pr92ActiveTurnContext !== null || _pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_TURN_CONTEXT_BUSY");
  }

  const attachmentPaths = _pr92NormalizeAttachmentPaths(message?.attachmentPaths);
  if (attachmentPaths.length !== 1) {
    throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_EXACTLY_ONE_ATTACHMENT_REQUIRED");
  }

  const context = _pr92CreateTurnContext(message);
  context.attachmentPaths = attachmentPaths;
  _pr92ActiveTurnContext = context;
  let staged = false;
  let stagedTabId = null;
  try {
    // Reuse normal fail-closed prewrite cleanup before creating any new staged state.
    await _pr92RequireCleanAttachmentState(context);

    const tab = await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA26_STAGING_DIAGNOSTIC_RUNTIME_TAB",
      () => ensureRuntimeTab(null)
    );
    if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");
    stagedTabId = tab.id;

    const stagedCount = await _pr92StageOfficialPageAttachments(
      tab.id,
      attachmentPaths,
      context
    );
    if (stagedCount !== 1) {
      throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_STAGE_COUNT_MISMATCH");
    }
    staged = true;

    const evidence = await _pr92Schema26ReadStagedDiagnosticEvidence(
      tab.id,
      attachmentPaths,
      context
    );
    const pageOwned = evidence.pageOwnedEvidence;
    if (
      pageOwned?.ready !== true ||
      pageOwned?.exactAttachmentSet !== true ||
      pageOwned?.crossEvidenceChannelExact !== true ||
      Number(pageOwned?.matchedCount) !== 1
    ) {
      throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_EXACT_EVIDENCE_NOT_PROVEN");
    }
    if (evidence.normalizationProof?.singleAttachmentCrossChannelExact !== true) {
      throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_CROSS_CHANNEL_NORMALIZATION_NOT_PROVEN");
    }

    // The normal staging path persisted the durable attachment fence before file
    // selection. Reuse the production stale-state cleanup while the same bounded
    // context is active; a successful diagnostic is not returned until cleanup is
    // proven and the persisted fence is gone.
    await _pr92RequireCleanAttachmentState(context);
    const remainingFence = await _pr92ReadDirtyAttachmentFence();
    if (Number.isInteger(remainingFence)) {
      throw new Error("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_CLEANUP_UNPROVEN");
    }

    return {
      diagnosticOnly: true,
      stagingOnly: true,
      fileUploadPerformed: true,
      writePerformed: false,
      conversationWritePerformed: false,
      textInsertionPerformed: false,
      protectedSubmitAttempted: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      richInputSchemaVersion: PR92_SCHEMA26_REPAIR_SCHEMA,
      tabId: stagedTabId,
      attachmentCount: stagedCount,
      expectedBasenames: _pr92ClosureExpectedBasenames(attachmentPaths),
      pageOwnedEvidence: pageOwned,
      rawEvidence: evidence.rawEvidence,
      schema26RemovalNormalizationProof: evidence.normalizationProof,
      cleanupProven: true,
      durableFenceCleared: true
    };
  } catch (error) {
    // If staging occurred and cleanup cannot be proven, deliberately retain the
    // durable fence. The next ordinary turn must execute the existing destructive
    // prewrite cleanup before it can obtain any write authority.
    if (staged) {
      try {
        if (_pr92RemainingTurnMsOrZero(context) > 0) {
          await _pr92RequireCleanAttachmentState(context);
        }
      } catch {}
    }
    throw error;
  } finally {
    _pr92ActiveTurnContext = null;
  }
};
