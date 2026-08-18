// PR8.8 explicit zero-product-write orphan Browser Authority lease reconciliation.
const PR88_ORPHAN_LEASE_SCHEMA = 1;
const _pr88OrphanPriorExecuteNativeTurn = executeNativeTurn;

function _pr88OrphanAssertReadOnly(message) {
  if (
    message?.text != null || message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null || message?.canonicalCompleted != null ||
    message?.canonicalCompletedAtMs != null
  ) throw new Error("PR8_8_ORPHAN_LEASE_RECONCILIATION_WRITE_FIELD_CONFLICT");
}

async function _pr88OrphanSnapshot() {
  const raw = await _pr824a3RawStoredRuntimeTabId();
  const runtimeTabId = Number.isInteger(raw) ? raw : null;
  const leaseId = await _pr88StoredLeaseId();
  if (runtimeTabId === null) {
    return { runtimeTabId: null, leaseId, runtimeTabState: "NO_RUNTIME_TAB_METADATA", liveChatGPTTab: false };
  }
  try {
    const tab = await chrome.tabs.get(runtimeTabId);
    const live = isChatGPTUrl(tab?.url || "");
    return { runtimeTabId, leaseId, runtimeTabState: live ? "LIVE_CHATGPT_TAB" : "NON_CHATGPT_TAB", liveChatGPTTab: live };
  } catch {
    return { runtimeTabId, leaseId, runtimeTabState: "MISSING_CHROME_TAB", liveChatGPTTab: false };
  }
}

function _pr88OrphanPublic(snapshot) {
  return {
    runtimeTabId: Number.isInteger(snapshot?.runtimeTabId) ? snapshot.runtimeTabId : null,
    runtimeTabState: snapshot?.runtimeTabState || "UNKNOWN",
    leaseIdPresent: typeof snapshot?.leaseId === "string" && snapshot.leaseId.length > 0,
    liveChatGPTTabObserved: snapshot?.liveChatGPTTab === true
  };
}

function _pr88OrphanResult(status, initial, final, extra = {}) {
  return {
    probeContext: "orphaned_browser_authority_lease_zero_write_reconciliation",
    orphanLeaseReconciliationSupported: true,
    orphanLeaseReconciliationSchemaVersion: PR88_ORPHAN_LEASE_SCHEMA,
    reconciliationStatus: status,
    initialState: _pr88OrphanPublic(initial),
    finalState: _pr88OrphanPublic(final),
    cleanBaseline: final?.runtimeTabId == null && final?.leaseId == null,
    leaseIdExported: false,
    zeroProductWrites: true,
    automaticRetry: false,
    ...extra
  };
}

async function _pr88OrphanSupport(message) {
  _pr88OrphanAssertReadOnly(message);
  return {
    orphanLeaseReconciliationSupported: true,
    orphanLeaseReconciliationSchemaVersion: PR88_ORPHAN_LEASE_SCHEMA,
    serializedZeroWriteReconciliationSupported: true,
    exactLeaseCompareAndClearSupported: true,
    runtimeTabPresenceFenceSupported: true,
    stateChangeAbstentionSupported: true,
    leaseIdExported: false,
    zeroProductWrites: true,
    automaticRetry: false
  };
}

async function _pr88ReconcileOrphanLease(message) {
  _pr88OrphanAssertReadOnly(message);
  const initial = await _pr88OrphanSnapshot();
  if (initial.liveChatGPTTab) return _pr88OrphanResult("LIVE_AUTHORITY_RETAINED", initial, initial);

  let staleRuntimeTabMetadataCleared = false;
  if (Number.isInteger(initial.runtimeTabId)) {
    staleRuntimeTabMetadataCleared = await _pr824a3ClearStoredRuntimeTabIdIfMatches(initial.runtimeTabId);
    if (!staleRuntimeTabMetadataCleared) {
      return _pr88OrphanResult("STATE_CHANGED_ABSTAINED", initial, await _pr88OrphanSnapshot(), { stateChangedBeforeCommit: true });
    }
  }

  const precommit = await _pr88OrphanSnapshot();
  if (precommit.liveChatGPTTab || Number.isInteger(precommit.runtimeTabId)) {
    return _pr88OrphanResult("STATE_CHANGED_ABSTAINED", initial, precommit, { staleRuntimeTabMetadataCleared, stateChangedBeforeCommit: true });
  }
  if (initial.leaseId == null) {
    return _pr88OrphanResult(staleRuntimeTabMetadataCleared ? "STALE_TAB_METADATA_CLEARED_NO_LEASE" : "ALREADY_CLEAN", initial, precommit, { staleRuntimeTabMetadataCleared });
  }
  if (precommit.leaseId !== initial.leaseId) {
    return _pr88OrphanResult("STATE_CHANGED_ABSTAINED", initial, precommit, { staleRuntimeTabMetadataCleared, stateChangedBeforeCommit: true });
  }

  const orphanLeaseCleared = await _pr88ClearLeaseIdIfMatches(initial.leaseId);
  if (!orphanLeaseCleared) {
    return _pr88OrphanResult("STATE_CHANGED_ABSTAINED", initial, await _pr88OrphanSnapshot(), { staleRuntimeTabMetadataCleared, stateChangedBeforeCommit: true });
  }
  const final = await _pr88OrphanSnapshot();
  const clean = final.runtimeTabId == null && final.leaseId == null;
  return _pr88OrphanResult(
    clean ? (staleRuntimeTabMetadataCleared ? "STALE_TAB_AND_ORPHAN_LEASE_CLEARED" : "ORPHAN_LEASE_CLEARED") : "POST_CLEAN_STATE_CHANGED",
    initial,
    final,
    { staleRuntimeTabMetadataCleared, orphanLeaseCleared: true, stateChangedBeforeCommit: !clean }
  );
}

executeNativeTurn = async function _executeNativeTurnWithOrphanLeaseReconciliation(message) {
  if (message?.characterizeOrphanLeaseReconciliationSupport === true) return _pr88OrphanSupport(message);
  if (message?.reconcileOrphanedBrowserAuthorityLease === true) return _pr88ReconcileOrphanLease(message);
  return _pr88OrphanPriorExecuteNativeTurn(message);
};
