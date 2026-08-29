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

const _pr92Schema28DiagnosticRepairPriorExecuteNativeTurn = executeNativeTurn;
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

executeNativeTurn = async function _executeNativeTurnWithPr92Schema28DiagnosticRepair(message) {
  if (message?.diagnosePr92CommittedIdentityStateSchema28 === true) {
    return _pr92Schema28CommittedIdentityDiagnosticRepaired(message);
  }
  return _pr92Schema28DiagnosticRepairPriorExecuteNativeTurn(message);
};
