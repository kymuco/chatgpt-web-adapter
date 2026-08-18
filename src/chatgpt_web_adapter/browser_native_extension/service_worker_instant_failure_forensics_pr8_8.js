// PR8.8 fresh Instant failure evidence capture.
//
// Loaded after Instant selection repair and retained route/picker forensics.
// This layer does not add a new product mutation. It wraps the existing
// locateAndFocusComposer call only to persist bounded evidence if that call
// fails before control returns to the transport's clear/input/submit sequence.
//
// The original exception is always re-thrown unchanged. No automatic retry,
// navigation, tab close, prompt insertion, submit, raw DOM/error export, cookie,
// auth, or response-body access is introduced.

const PR88_INSTANT_FAILURE_FORENSICS_SCHEMA_VERSION = 1;
const PR88_INSTANT_FAILURE_FORENSICS_STORAGE_KEY =
  "browserAuthorityLastInstantFailureForensicsV1";

const _pr88FailurePriorExecuteNativeTurn = executeNativeTurn;
const _pr88FailurePriorLocateAndFocusComposer = locateAndFocusComposer;

function _pr88FailureLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88FailureCode(error) {
  const message = String(error?.message || error || "");
  if (message.startsWith("PR8_8_INSTANT_SELECTION_INITIAL_MODE_NOT_PROVEN")) {
    return "INITIAL_MODE_NOT_PROVEN";
  }
  if (message.startsWith("PR8_8_INSTANT_SELECTION_PICKER_NOT_FOUND:")) {
    return "PICKER_NOT_FOUND";
  }
  if (message.startsWith("PR8_8_INSTANT_SELECTION_OPTION_NOT_FOUND:")) {
    return "OPTION_NOT_FOUND";
  }
  if (message.startsWith("PR8_8_INSTANT_SELECTION_DID_NOT_SETTLE_TO_INSTANT")) {
    return "DID_NOT_SETTLE_TO_INSTANT";
  }
  return "LOCATE_OR_SELECTION_OTHER";
}

function _pr88FailureReason(error) {
  const message = String(error?.message || error || "");
  const allowed = new Set([
    "composer_missing",
    "picker_missing",
    "point_probe_failed",
    "instant_option_missing",
    "instant_option_ambiguous",
    "instant_option_timeout",
    "unknown"
  ]);
  const index = message.indexOf(":");
  if (index < 0) return null;
  const reason = message.slice(index + 1).trim();
  return allowed.has(reason) ? reason : "unknown";
}

function _pr88FailureSelectionPublic(context) {
  let source = {};
  try {
    if (typeof _pr88SelectionRecord === "function") {
      const record = _pr88SelectionRecord(context);
      source = record && typeof record === "object" ? record : {};
    }
  } catch {
    source = {};
  }

  return {
    requestedModelMode: source.requestedModelMode || "INSTANT",
    selectedModeBeforeSelection: source.selectedModeBeforeSelection || null,
    selectedModeBeforeSelectionProven:
      source.selectedModeBeforeSelectionProven === true,
    selectedModeBeforeSelectionProofKind:
      source.selectedModeBeforeSelectionProofKind || null,
    selectedModeBeforeSelectionCandidateCount:
      Number.isInteger(source.selectedModeBeforeSelectionCandidateCount)
        ? source.selectedModeBeforeSelectionCandidateCount
        : 0,
    selectionPerformed: source.selectionPerformed === true,
    selectionElapsedMs:
      Number.isInteger(source.selectionElapsedMs) ? source.selectionElapsedMs : null,
    selectionMutationElapsedMs:
      Number.isInteger(source.selectionMutationElapsedMs)
        ? source.selectionMutationElapsedMs
        : null,
    pickerModeBeforeClick: source.pickerModeBeforeClick || null,
    pickerCandidateCount:
      Number.isInteger(source.pickerCandidateCount) ? source.pickerCandidateCount : 0,
    pickerNearestDistancePx:
      Number.isInteger(source.pickerNearestDistancePx)
        ? source.pickerNearestDistancePx
        : null,
    instantOptionCandidateCount:
      Number.isInteger(source.instantOptionCandidateCount)
        ? source.instantOptionCandidateCount
        : 0,
    selectedModeAfterSelection: source.selectedModeAfterSelection || null,
    selectedModeAfterSelectionProven:
      source.selectedModeAfterSelectionProven === true,
    selectedModeAfterSelectionProofKind:
      source.selectedModeAfterSelectionProofKind || null,
    selectionComplete: source.selectionComplete === true,
    conversationWriteBoundaryObserved:
      source.conversationWriteBoundaryObserved === true,
    unexpectedConversationWriteBeforeSelectionComplete:
      source.unexpectedConversationWriteBeforeSelectionComplete === true,
    conversationWriteCountDuringSelection:
      Number.isInteger(source.conversationWriteCountDuringSelection)
        ? source.conversationWriteCountDuringSelection
        : 0,
    networkRequestCountDuringSelection:
      Number.isInteger(source.networkRequestCountDuringSelection)
        ? source.networkRequestCountDuringSelection
        : 0,
    chatgptRequestCountDuringSelection:
      Number.isInteger(source.chatgptRequestCountDuringSelection)
        ? source.chatgptRequestCountDuringSelection
        : 0,
    chatgptMutatingNonConversationRequestCount:
      Number.isInteger(source.chatgptMutatingNonConversationRequestCount)
        ? source.chatgptMutatingNonConversationRequestCount
        : 0,
    settingLikeMutationObserved: source.settingLikeMutationObserved === true,
    requestClasses: Array.isArray(source.requestClasses)
      ? source.requestClasses.filter((item) => typeof item === "string").slice(0, 16)
      : [],
    modelSelectionMaterializationStatus:
      source.modelSelectionMaterializationStatus || "INCONCLUSIVE"
  };
}

async function _pr88FailurePersist(error, context) {
  const leaseId = _pr88FailureLeaseId(context?.leaseId);
  if (leaseId === null) return false;

  const record = {
    schemaVersion: PR88_INSTANT_FAILURE_FORENSICS_SCHEMA_VERSION,
    leaseId,
    failureCaptured: true,
    failureCode: _pr88FailureCode(error),
    failureReason: _pr88FailureReason(error),
    preInputFailureBoundaryProven: true,
    promptInsertionReached: false,
    submitReached: false,
    rawErrorExported: false,
    selection: _pr88FailureSelectionPublic(context)
  };

  await chrome.storage.local.set({
    [PR88_INSTANT_FAILURE_FORENSICS_STORAGE_KEY]: record
  });
  return true;
}

locateAndFocusComposer = async function _locateAndFocusComposerWithInstantFailureEvidence(debuggee) {
  try {
    return await _pr88FailurePriorLocateAndFocusComposer(debuggee);
  } catch (error) {
    let context = null;
    try {
      if (typeof _pr88SelectionContext !== "undefined") {
        context = _pr88SelectionContext;
      }
    } catch {
      context = null;
    }
    if (context !== null && _pr88FailureLeaseId(context?.leaseId) !== null) {
      try {
        await _pr88FailurePersist(error, context);
      } catch {
        // Evidence persistence must never replace or mask the original failure.
      }
    }
    throw error;
  }
};

function _pr88FailureQueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true ||
    message?.canonicalCompletedAtMs != null
  );
}

async function _pr88FailureStoredRecord() {
  const stored = await chrome.storage.local.get(
    PR88_INSTANT_FAILURE_FORENSICS_STORAGE_KEY
  );
  const value = stored?.[PR88_INSTANT_FAILURE_FORENSICS_STORAGE_KEY];
  return value && typeof value === "object" ? value : null;
}

async function _pr88FailureRecord(message) {
  if (_pr88FailureQueryConflict(message)) {
    throw new Error("PR8_8_INSTANT_FAILURE_FORENSICS_RECORD_FLAG_CONFLICT");
  }
  const expectedLeaseId = _pr88FailureLeaseId(
    message?.expectedBrowserAuthorityLeaseId
  );
  if (expectedLeaseId === null) {
    throw new Error("PR8_8_INSTANT_FAILURE_FORENSICS_EXPECTED_LEASE_REQUIRED");
  }
  const record = await _pr88FailureStoredRecord();
  if (record === null) {
    throw new Error("PR8_8_INSTANT_FAILURE_FORENSICS_RECORD_NOT_AVAILABLE");
  }
  if (_pr88FailureLeaseId(record.leaseId) !== expectedLeaseId) {
    throw new Error("PR8_8_INSTANT_FAILURE_FORENSICS_LEASE_MISMATCH");
  }

  return {
    probeContext: "instant_failure_forensics_record",
    readOnly: true,
    zeroProductWrites: true,
    automaticRetry: false,
    instantFailureForensicsSupported: true,
    instantFailureForensicsSchemaVersion:
      PR88_INSTANT_FAILURE_FORENSICS_SCHEMA_VERSION,
    failureCaptured: record.failureCaptured === true,
    failureCode: record.failureCode || "UNKNOWN",
    failureReason: record.failureReason || null,
    preInputFailureBoundaryProven:
      record.preInputFailureBoundaryProven === true,
    promptInsertionReached: record.promptInsertionReached === true,
    submitReached: record.submitReached === true,
    rawErrorExported: record.rawErrorExported === true,
    leaseIdExported: false,
    selection:
      record.selection && typeof record.selection === "object"
        ? record.selection
        : {}
  };
}

executeNativeTurn = async function _executeNativeTurnWithInstantFailureForensics(message) {
  if (message?.characterizeInstantFailureForensicsSupport === true) {
    if (_pr88FailureQueryConflict(message) || message?.expectedBrowserAuthorityLeaseId != null) {
      throw new Error("PR8_8_INSTANT_FAILURE_FORENSICS_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "instant_failure_forensics_support",
      readOnly: true,
      zeroProductWrites: true,
      automaticRetry: false,
      instantFailureForensicsSupported: true,
      instantFailureForensicsSchemaVersion:
        PR88_INSTANT_FAILURE_FORENSICS_SCHEMA_VERSION,
      failureRecordPersistenceSupported: true,
      preInputFailureBoundarySupported: true,
      retainedRouteForensicsCompositionSupported: true,
      retainedPickerForensicsCompositionSupported: true,
      rawErrorRedactionSupported: true,
      leaseIdExported: false
    };
  }

  if (message?.characterizeInstantFailureForensicsRecord === true) {
    return _pr88FailureRecord(message);
  }

  return _pr88FailurePriorExecuteNativeTurn(message);
};
