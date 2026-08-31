// PR9.2 schema-27 staging-only live evidence diagnostic.
//
// Explicit diagnostic RPC only. It may stage/upload one generated local fixture on
// the official page, but it grants no conversation-write authority: no text is
// inserted and no submit primitive is invoked. It reuses production staging and the
// schema-27 page-owned evidence expression, then requires the schema-27 ambiguity
// proof before invoking the existing durable-fence destructive cleanup.

const _pr92Schema27StagingDiagnosticPriorExecuteNativeTurn = executeNativeTurn;

executeNativeTurn = async function _executeNativeTurnWithPr92Schema27StagingDiagnostic(message) {
  if (message?.diagnosePr92StagedAttachmentEvidenceSchema27 !== true) {
    return _pr92Schema27StagingDiagnosticPriorExecuteNativeTurn(message);
  }
  if (message?.text != null) {
    throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_TEXT_FORBIDDEN");
  }
  if (_pr92ActiveTurnContext !== null || _pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_TURN_CONTEXT_BUSY");
  }

  const attachmentPaths = _pr92NormalizeAttachmentPaths(message?.attachmentPaths);
  if (attachmentPaths.length !== 1) {
    throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_EXACTLY_ONE_ATTACHMENT_REQUIRED");
  }

  const context = _pr92CreateTurnContext(message);
  context.attachmentPaths = attachmentPaths;
  _pr92ActiveTurnContext = context;
  let stagedTabId = null;
  try {
    await _pr92RequireCleanAttachmentState(context);

    const tab = await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA27_STAGING_DIAGNOSTIC_RUNTIME_TAB",
      () => ensureRuntimeTab(null)
    );
    if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");
    stagedTabId = tab.id;

    // This production binding already performs the schema-24 clean proof, schema-13
    // durable-fenced DOM.setFileInputFiles staging, and stable page-owned evidence.
    // Because schema 27 rebound the shared evidence expression, every evidence read
    // inside this call uses the bidirectional ambiguity-safe matcher.
    const stagedCount = await _pr92StageOfficialPageAttachments(
      tab.id,
      attachmentPaths,
      context
    );
    if (stagedCount !== 1) {
      throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_STAGE_COUNT_MISMATCH");
    }

    // Reuse the bounded diagnostic DOM observer only as a reader. Its historical
    // schema-26 normalization field is deliberately ignored; schema 27 recomputes
    // normalization from the raw DOM below.
    const evidence = await _pr92Schema26ReadStagedDiagnosticEvidence(
      tab.id,
      attachmentPaths,
      context
    );
    const pageOwned = evidence.pageOwnedEvidence;
    const schema27Normalization = _pr92Schema27DiagnosticRemovalNormalization({
      evidence: evidence.rawEvidence
    });

    if (
      pageOwned?.ready !== true ||
      pageOwned?.exactAttachmentSet !== true ||
      pageOwned?.crossEvidenceChannelExact !== true ||
      pageOwned?.indexedRemovalAmbiguityBidirectionalFailClosed !== true ||
      pageOwned?.indexedRemovalLiteralInterpretationRequiresIndependentFilenameGroup !== true ||
      pageOwned?.indexedRemovalStrippedInterpretationRequiresIndependentFilenameGroup !== true ||
      Number(pageOwned?.matchedCount) !== 1
    ) {
      throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_EXACT_EVIDENCE_NOT_PROVEN");
    }
    if (schema27Normalization?.singleAttachmentCrossChannelExact !== true) {
      throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_NORMALIZATION_NOT_PROVEN");
    }

    // The durable fence was persisted before file selection. Successful diagnostic
    // completion reuses production prewrite recovery, which may destructively close
    // only the exact extension-managed fenced runtime tab under its identity guards
    // and clears the fence only after tab absence is proven.
    await _pr92RequireCleanAttachmentState(context);
    const remainingFence = await _pr92ReadDirtyAttachmentFence();
    if (Number.isInteger(remainingFence)) {
      throw new Error("PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_CLEANUP_UNPROVEN");
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
      richInputSchemaVersion: PR92_SCHEMA27_REPAIR_SCHEMA,
      tabId: stagedTabId,
      attachmentCount: stagedCount,
      expectedBasenames: _pr92ClosureExpectedBasenames(attachmentPaths),
      pageOwnedEvidence: pageOwned,
      rawEvidence: evidence.rawEvidence,
      schema27RemovalNormalizationProof: schema27Normalization,
      cleanupProven: true,
      durableFenceCleared: true
    };
  } catch (error) {
    // The full production staging wrapper can fail after DOM.setFileInputFiles has
    // already executed (for example, during post-stage evidence). Do not key cleanup
    // eligibility on the wrapper having returned successfully. The durable fence was
    // persisted before file selection and is the authoritative proof that partial
    // staging may exist. If budget remains, read that fence and invoke the established
    // destructive prewrite recovery; otherwise retain it so the next write fails closed.
    try {
      if (_pr92RemainingTurnMsOrZero(context) > 0) {
        const residualFence = await _pr92ReadDirtyAttachmentFence();
        if (Number.isInteger(residualFence)) {
          await _pr92RequireCleanAttachmentState(context);
        }
      }
    } catch {}
    throw error;
  } finally {
    _pr92ActiveTurnContext = null;
  }
};
