// PR9.2 schema-28 diagnostic-only reconciliation repair.
//
// This overlay does not modify rich-input write, staging, protected-submit, or
// causal identity authority. It only repairs the committed-state reconciliation
// diagnostic added by schema 28:
//   1. optional route sampling must not consume cleanup authority/budget;
//   2. clearing the durable fence through production recovery does not always
//      imply that the numeric tab id is literally absent (a reused non-ChatGPT
//      id is intentionally left untouched), so tab presence is reported as a
//      separate tri-state diagnostic observation.
//
// Turn deadlines are monotonic (performance.now based), so every local diagnostic
// sub-budget below deliberately stays in that same clock domain.

const PR92_SCHEMA28_DIAGNOSTIC_ROUTE_SAMPLE_MAX_MS = 250;
const PR92_SCHEMA28_DIAGNOSTIC_CLEANUP_RESERVE_MS = 10000;
const PR92_SCHEMA28_DIAGNOSTIC_RETURN_RESERVE_MS = 1000;
const PR92_SCHEMA28_DIAGNOSTIC_POST_CLEANUP_SAMPLE_MAX_MS = 250;

function _pr92Schema28DiagnosticRemainingMs(context) {
  return Math.max(0, context.deadlineAt - performance.now());
}

async function _pr92Schema28DiagnosticReadTab(tabId, deadlineAt, label) {
  if (!Number.isInteger(tabId) || !Number.isFinite(deadlineAt) || deadlineAt <= performance.now()) {
    return {
      state: "unknown",
      tabId: Number.isInteger(tabId) ? tabId : null,
      url: null,
      routeConversationId: null
    };
  }
  try {
    const tab = await _pr92Schema7RunUntil(
      deadlineAt,
      label,
      () => chrome.tabs.get(tabId)
    );
    return {
      state: "present",
      tabId,
      url: typeof tab?.url === "string" ? tab.url : null,
      routeConversationId: conversationIdFromUrl(tab?.url || "") || null
    };
  } catch (error) {
    if (_pr92DeadlineRepairIsMissingTabError(error)) {
      return {
        state: "absent",
        tabId,
        url: null,
        routeConversationId: null
      };
    }
    return {
      state: "unknown",
      tabId,
      url: null,
      routeConversationId: null
    };
  }
}

async function _pr92Schema28DiagnosticRouteSample(tabId, context, cleanupRequired) {
  const remaining = _pr92Schema28DiagnosticRemainingMs(context);
  const reserve = cleanupRequired
    ? PR92_SCHEMA28_DIAGNOSTIC_CLEANUP_RESERVE_MS
    : PR92_SCHEMA28_DIAGNOSTIC_RETURN_RESERVE_MS;
  const available = remaining - reserve;
  if (!Number.isInteger(tabId) || available <= 0) {
    return {
      state: "unknown",
      tabId: Number.isInteger(tabId) ? tabId : null,
      url: null,
      routeConversationId: null,
      skippedForCleanupReserve: cleanupRequired
    };
  }
  const budget = Math.min(PR92_SCHEMA28_DIAGNOSTIC_ROUTE_SAMPLE_MAX_MS, available);
  const sampled = await _pr92Schema28DiagnosticReadTab(
    tabId,
    performance.now() + budget,
    "SCHEMA28_DIAGNOSTIC_ROUTE_SAMPLE"
  );
  return {
    ...sampled,
    skippedForCleanupReserve: false
  };
}

async function _pr92Schema28DiagnosticPostCleanupPresence(tabId, context) {
  if (!Number.isInteger(tabId)) {
    return { state: "unknown", tabId: null, url: null, routeConversationId: null };
  }
  const remaining = _pr92Schema28DiagnosticRemainingMs(context);
  const available = remaining - PR92_SCHEMA28_DIAGNOSTIC_RETURN_RESERVE_MS;
  if (available <= 0) {
    return { state: "unknown", tabId, url: null, routeConversationId: null };
  }
  const budget = Math.min(PR92_SCHEMA28_DIAGNOSTIC_POST_CLEANUP_SAMPLE_MAX_MS, available);
  return _pr92Schema28DiagnosticReadTab(
    tabId,
    performance.now() + budget,
    "SCHEMA28_DIAGNOSTIC_POST_CLEANUP_TAB_SAMPLE"
  );
}

async function _pr92Schema28CommittedIdentityDiagnosticRepaired(message) {
  if (message?.text != null || message?.attachmentPaths != null) {
    throw new Error("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_WRITE_INPUT_FORBIDDEN");
  }
  if (_pr92ActiveTurnContext !== null || _pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_TURN_CONTEXT_BUSY");
  }

  const context = _pr92CreateTurnContext(message);
  _pr92ActiveTurnContext = context;
  try {
    const fenceBefore = await _pr92ReadDirtyAttachmentFence();
    let runtimeTabId = null;
    if (Number.isInteger(fenceBefore)) {
      runtimeTabId = fenceBefore;
    } else {
      try {
        runtimeTabId = await _pr92Schema7RunUntil(
          context.deadlineAt,
          "SCHEMA28_DIAGNOSTIC_RUNTIME_TAB_ID",
          () => storedRuntimeTabId()
        );
      } catch {
        runtimeTabId = null;
      }
    }

    const cleanupRequired = Number.isInteger(fenceBefore);
    const tabBeforeCleanup = await _pr92Schema28DiagnosticRouteSample(
      runtimeTabId,
      context,
      cleanupRequired
    );

    let cleanupAttempted = false;
    if (cleanupRequired) {
      cleanupAttempted = true;
      await _pr92RequireCleanAttachmentState(context);
    }

    const fenceAfter = await _pr92ReadDirtyAttachmentFence();
    if (Number.isInteger(fenceAfter)) {
      throw new Error("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_FENCE_REMAINS");
    }

    const tabAfterCleanup = cleanupRequired
      ? await _pr92Schema28DiagnosticPostCleanupPresence(runtimeTabId, context)
      : { state: "unknown", tabId: runtimeTabId, url: null, routeConversationId: null };

    const fencedTabAbsentAfterCleanup = cleanupRequired
      ? (tabAfterCleanup.state === "absent"
          ? true
          : tabAfterCleanup.state === "present"
            ? false
            : null)
      : null;
    const fencedTabAbsenceAuthority = cleanupRequired
      ? (tabAfterCleanup.state === "absent"
          ? "POST_CLEANUP_TAB_ABSENCE_PROBE"
          : tabAfterCleanup.state === "present"
            ? "POST_CLEANUP_TAB_PRESENCE_PROBE"
            : null)
      : null;

    return {
      diagnosticOnly: true,
      reconciliationOnly: true,
      writePerformed: false,
      conversationWritePerformed: false,
      attachmentStagingPerformed: false,
      textInsertionPerformed: false,
      protectedSubmitAttempted: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      richInputSchemaVersion: PR92_SCHEMA28_REPAIR_SCHEMA,
      durableFencePresentBefore: cleanupRequired,
      cleanupAttempted,
      cleanupProven: !Number.isInteger(fenceAfter),
      staleComposerReconciled: !Number.isInteger(fenceAfter),
      cleanupProofAuthority: cleanupRequired
        ? "PRODUCTION_REQUIRE_CLEAN_ATTACHMENT_STATE"
        : null,
      durableFenceCleared: !Number.isInteger(fenceAfter),
      fencedTabAbsentAfterCleanup,
      fencedTabAbsenceAuthority,
      observedTabStateBeforeCleanup: tabBeforeCleanup.state,
      observedTabIdBeforeCleanup: tabBeforeCleanup.tabId ?? null,
      observedRouteConversationIdDiagnostic: tabBeforeCleanup.routeConversationId ?? null,
      observedUrlBeforeCleanup: tabBeforeCleanup.url ?? null,
      routeSampleSkippedForCleanupReserve:
        tabBeforeCleanup.skippedForCleanupReserve === true,
      observedTabStateAfterCleanup: cleanupRequired ? tabAfterCleanup.state : null,
      routeConversationIdentityAuthoritative: false
    };
  } finally {
    _pr92ActiveTurnContext = null;
  }
}

function _cwaRichInputDiagnosticMatches(message) {
  return (
    message?.diagnosePr92CommittedIdentityStateSchema28 === true ||
    message?.diagnosePr92StagedAttachmentEvidenceSchema27 === true ||
    message?.diagnosePr92StagedAttachmentEvidence === true ||
    message?.diagnosePr92ComposerEvidence === true ||
    message?.characterizeRichInputSupport === true
  );
}

function _cwaRichInputDiagnosticPrepareOuterState(message) {
  _pr92Schema28PrepareRichWriteDiagnostics(message);
  _pr92Schema29PrepareRichWriteDiagnostics(message);
}

function _cwaRichInputSupportResult(message) {
  let result = _pr92RichInputBaseSupportResult(message);
  result = _pr92DeadlineRepairAugmentSupportResult(result);
  result = _pr92ClosureAugmentSupportResult(result);
  result = _pr92Schema7AugmentSupportResult(result);
  result = _pr92Schema8AugmentSupportResult(result);
  result = _pr92Schema9AugmentSupportResult(result);
  result = _pr92Schema10AugmentSupportResult(result);
  result = _pr92Schema11AugmentSupportResult(result);
  result = _pr92Schema12AugmentSupportResult(result);
  result = _pr92Schema13AugmentSupportResult(result);
  result = _pr92Schema14AugmentSupportResult(result);
  result = _pr92Schema15AugmentSupportResult(result);
  result = _pr92Schema16AugmentSupportResult(result);
  result = _pr92Schema17AugmentSupportResult(result);
  result = _pr92Schema18AugmentSupportResult(result);
  result = _pr92Schema19AugmentSupportResult(result);
  result = _pr92Schema20AugmentSupportResult(result);
  result = _pr92Schema21AugmentSupportResult(result);
  result = _pr92Schema22AugmentSupportResult(result);
  result = _pr92Schema23AugmentSupportResult(result);
  result = _pr92Schema24AugmentSupportResult(result);
  result = _pr92Schema25AugmentSupportResult(result);
  result = _pr92Schema26AugmentSupportResult(result);
  result = _pr92Schema27AugmentSupportResult(result);
  result = _pr92Schema28AugmentSupportResult(result);
  return _pr92Schema29AugmentSupportResult(result);
}

function _cwaRichInputDiagnosticApplySupportTail(message, result, fromSchema) {
  if (
    message?.characterizeRichInputSupport !== true ||
    !result ||
    typeof result !== "object"
  ) {
    return result;
  }

  let next = result;
  if (fromSchema <= 26) next = _pr92Schema27AugmentSupportResult(next);
  if (fromSchema <= 27) next = _pr92Schema28AugmentSupportResult(next);
  next = _pr92Schema29AugmentSupportResult(next);
  return next;
}

async function _cwaHandleRichInputDiagnostic(message) {
  _cwaRichInputDiagnosticPrepareOuterState(message);

  // Preserve the historical outer-to-inner precedence of the detached wrappers:
  // schema28 reconciliation -> schema27 staging -> schema26 staging -> composer.
  if (message?.diagnosePr92CommittedIdentityStateSchema28 === true) {
    const result = await _pr92Schema28CommittedIdentityDiagnosticRepaired(message);
    return _cwaRichInputDiagnosticApplySupportTail(message, result, 28);
  }

  if (message?.diagnosePr92StagedAttachmentEvidenceSchema27 === true) {
    const result = await _pr92RunSchema27StagingDiagnostic(message);
    return _cwaRichInputDiagnosticApplySupportTail(message, result, 27);
  }

  if (message?.diagnosePr92StagedAttachmentEvidence === true) {
    const result = await _pr92RunSchema26StagingDiagnostic(message);
    return _cwaRichInputDiagnosticApplySupportTail(message, result, 26);
  }

  if (message?.diagnosePr92ComposerEvidence === true) {
    let result = await _pr92RunSchema23ComposerDiagnostic(message);
    if (result && typeof result === "object") {
      result = _pr92Schema25AugmentComposerDiagnostic(result);
      result = _pr92Schema26AugmentComposerDiagnostic(result);
      result = _pr92Schema27AugmentComposerDiagnostic(result);
    }
    return _cwaRichInputDiagnosticApplySupportTail(message, result, 27);
  }

  if (message?.characterizeRichInputSupport === true) {
    return _cwaRichInputSupportResult(message);
  }

  throw new Error("PR15_7_RICH_INPUT_CONTROL_PLANE_UNMATCHED");
}

registerNativeTurnDiagnosticHandler(
  "rich-input-diagnostics",
  _cwaRichInputDiagnosticMatches,
  _cwaHandleRichInputDiagnostic
);
