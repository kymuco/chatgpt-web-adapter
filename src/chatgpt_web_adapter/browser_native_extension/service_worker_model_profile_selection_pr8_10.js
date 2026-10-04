// PR8.10 generalized semantic model-profile selector over the proven PR8.8 effort slider.
// Supports only the three product states already characterized in production:
// INSTANT (0), MEDIUM (1), HIGH (2). Explicit unsupported modes fail before write.

const PR810_MODEL_PROFILE_SCHEMA_VERSION = 1;
const PR810_MODEL_PROFILE_STORAGE_KEY = "browserAuthorityLastModelProfileSelectionV1";
const PR810_MODEL_MODE_INDEX = Object.freeze({INSTANT: 0, MEDIUM: 1, HIGH: 2});
const PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS = PR88_INSTANT_PROBE_TIMEOUT_MS;

let _pr810ModelProfileContext = null;

function _pr810Mode(value) {
  const mode = typeof value === "string" ? value.trim().toUpperCase() : "";
  return Object.prototype.hasOwnProperty.call(PR810_MODEL_MODE_INDEX, mode) ? mode : null;
}

function _pr810Lease(value) {
  const lease = typeof value === "string" ? value.trim() : "";
  return lease || null;
}

function _pr810QueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true
  );
}

function _pr810InitialModeFailure(before) {
  const proofKind = typeof before?.proofKind === "string" ? before.proofKind : "unknown";
  const composerReady = before?.composerReady === true ? "true" : "false";
  const candidateCount = Number.isInteger(before?.candidateCount) ? before.candidateCount : 0;
  return `PR8_10_MODEL_PROFILE_INITIAL_MODE_NOT_PROVEN:${proofKind}:composer_ready=${composerReady}:candidate_count=${candidateCount}`;
}

async function _pr810DispatchKey(debuggee, key, code, virtualKeyCode) {
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "rawKeyDown", key, code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp", key, code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode
  });
}

async function _pr810WaitForTarget(debuggee, targetMode, targetIndex, timeoutMs = 8000) {
  const startedAt = performance.now();
  let selected = null;
  let slider = null;
  let proofKind = null;
  while (performance.now() - startedAt < timeoutMs) {
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    slider = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "snapshot");
    const sliderTargetProven = (
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === targetIndex &&
      slider?.currentMode === targetMode
    );
    const selectedTargetProven = (
      selected?.selectedModeProven === true &&
      selected?.selectedMode === targetMode
    );
    if (sliderTargetProven && (selectedTargetProven || selected?.selectedModeProven !== true)) {
      proofKind = selectedTargetProven
        ? "selected_mode_and_exact_slider"
        : "unique_exact_slider_value";
      return {selected, slider, proofKind};
    }
    if (selectedTargetProven && slider?.found !== true) {
      proofKind = "selected_mode_control";
      return {selected, slider, proofKind};
    }
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return {selected, slider, proofKind};
}

function _pr810InstallWriteBoundary(debuggee, context) {
  const listener = (source, method, params) => {
    if (source?.tabId !== debuggee.tabId || method !== "Network.requestWillBeSent") return;
    const request = params?.request;
    if (isConversationWrite(request?.url || "", request?.method || "")) {
      if (context.selectionComplete !== true) context.conversationWriteBeforeSelection = true;
      try { chrome.debugger.onEvent.removeListener(listener); } catch {}
      context.writeBoundaryListener = null;
    }
  };
  chrome.debugger.onEvent.addListener(listener);
  context.writeBoundaryListener = listener;
}

async function _pr810EnsureTargetMode(debuggee, context) {
  if (context.selectionChecked === true) return;
  context.selectionChecked = true;
  const startedAt = performance.now();
  const targetMode = context.requestedModelMode;
  const targetIndex = PR810_MODEL_MODE_INDEX[targetMode];

  const initialModeStartedAt = performance.now();
  await waitForComposerReady(
    debuggee,
    PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS
  );
  context.initialModeComposerReadyElapsedMs = Math.max(
    0,
    Math.round(performance.now() - initialModeStartedAt)
  );
  const initialModeRemainingMs = Math.max(
    0,
    PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS -
      (performance.now() - initialModeStartedAt)
  );
  const before = await _pr88InstantWaitForSelectedMode(
    debuggee,
    initialModeRemainingMs
  );
  context.initialModeAcquisitionElapsedMs = Math.max(
    0,
    Math.round(performance.now() - initialModeStartedAt)
  );
  context.initialModeComposerReady = before?.composerReady === true;
  context.selectedModeBefore = before?.selectedMode || null;
  context.selectedModeBeforeProven = before?.selectedModeProven === true;
  context.selectedModeBeforeProofKind = before?.proofKind || "unknown";
  context.selectedModeBeforeCandidateCount = Number.isInteger(before?.candidateCount)
    ? before.candidateCount
    : 0;
  context.selectedModeBeforeNearestDistancePx = Number.isFinite(before?.nearestDistancePx)
    ? Math.max(0, Math.round(before.nearestDistancePx))
    : null;

  if (before?.selectedModeProven !== true || typeof before?.selectedMode !== "string") {
    throw new Error(_pr810InitialModeFailure(before));
  }
  if (_pr810Mode(before.selectedMode) === null) {
    throw new Error(`PR8_10_MODEL_PROFILE_INITIAL_MODE_UNSUPPORTED:${before.selectedMode}`);
  }

  if (before.selectedMode === targetMode) {
    context.selectionPerformed = false;
    context.selectionMechanism = "NO_SELECTION_REQUIRED";
    context.selectedModeAfter = targetMode;
    context.selectedModeAfterProven = true;
    context.selectionComplete = true;
    context.selectionElapsedMs = Math.max(0, Math.round(performance.now() - startedAt));
    return;
  }

  context.selectionPerformed = true;
  context.selectionMechanism = "REASONING_EFFORT_SLIDER_HOME_PLUS_RIGHT";
  _pr810InstallWriteBoundary(debuggee, context);

  context.transientForegroundActivated = false;
  context.transientForegroundProven = false;
  context.foregroundRestoreAttempted = false;
  context.foregroundRestoreProven = true;
  context.backgroundSelectionAttempted = true;
  const picker = await _pr88SelectionPoint(debuggee, "picker");
  if (picker?.found !== true || picker?.candidateCount !== 1 || picker?.mode !== before.selectedMode) {
    throw new Error(`PR8_10_MODEL_PROFILE_PICKER_NOT_PROVEN:${picker?.reason || "identity_mismatch"}`);
  }

  let slider = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "snapshot");
  const alreadyOpen = (
    slider?.found === true && slider?.candidateCount === 1 &&
    slider?.min === 0 && slider?.max === 2 && slider?.stepCount === 3 &&
    slider?.currentControlOpen === true && slider?.currentMode === before.selectedMode
  );
  if (!alreadyOpen) {
    await _pr88InstantEffortOpenPickerWithFallback(debuggee, picker, before.selectedMode);
    slider = await _pr88InstantEffortWaitForResolvedSlider(debuggee, before.selectedMode, 3000);
  }
  if (
    slider?.found !== true || slider?.candidateCount !== 1 ||
    slider?.min !== 0 || slider?.max !== 2 || slider?.stepCount !== 3
  ) {
    throw new Error(`PR8_10_MODEL_PROFILE_SLIDER_CONTRACT_NOT_PROVEN:${slider?.reason || "range_mismatch"}`);
  }

  const focused = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "focus");
  if (focused?.focusProven !== true || focused?.min !== 0 || focused?.max !== 2 || focused?.stepCount !== 3) {
    throw new Error("PR8_10_MODEL_PROFILE_SLIDER_FOCUS_NOT_PROVEN");
  }

  await _pr88InstantEffortDispatchHome(debuggee);
  for (let index = 0; index < targetIndex; index += 1) {
    await _pr810DispatchKey(debuggee, "ArrowRight", "ArrowRight", 39);
  }

  const settled = await _pr810WaitForTarget(debuggee, targetMode, targetIndex);
  const after = settled?.selected;
  const sliderAfter = settled?.slider;
  context.selectedModeAfterProofKind = settled?.proofKind || null;
  context.sliderValueAfter = Number.isFinite(sliderAfter?.now) ? sliderAfter.now : targetIndex;
  context.selectedModeAfter =
    after?.selectedModeProven === true
      ? after.selectedMode
      : sliderAfter?.currentMode || null;
  context.selectedModeAfterProven = (
    context.selectedModeAfter === targetMode &&
    (
      after?.selectedModeProven === true ||
      (
        sliderAfter?.found === true &&
        sliderAfter?.now === targetIndex &&
        sliderAfter?.currentMode === targetMode
      )
    )
  );
  if (context.conversationWriteBeforeSelection === true) {
    throw new Error("PR8_10_MODEL_PROFILE_CONVERSATION_WRITE_BEFORE_SELECTION");
  }
  if (after?.selectedModeProven !== true || after?.selectedMode !== targetMode) {
    throw new Error(`PR8_10_MODEL_PROFILE_DID_NOT_SETTLE:${targetMode}`);
  }
  if (sliderAfter?.found === true && sliderAfter?.now !== targetIndex) {
    throw new Error(`PR8_10_MODEL_PROFILE_SLIDER_TARGET_NOT_REACHED:${targetIndex}`);
  }
  context.selectionComplete = true;
  context.backgroundSelectionProven = true;
  context.selectionElapsedMs = Math.max(0, Math.round(performance.now() - startedAt));
}

async function _pr810PrepareComposer(debuggee) {
  if (_pr810ModelProfileContext !== null) {
    await _pr810EnsureTargetMode(debuggee, _pr810ModelProfileContext);
  }
}

function _pr810Record(context) {
  return {
    schemaVersion: PR810_MODEL_PROFILE_SCHEMA_VERSION,
    browserAuthorityLeaseId: context.leaseId,
    requestedModelMode: context.requestedModelMode,
    requestedSliderIndex: PR810_MODEL_MODE_INDEX[context.requestedModelMode],
    initialModeAcquisitionTimeoutMs: PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS,
    initialModeAcquisitionElapsedMs: Number.isFinite(context.initialModeAcquisitionElapsedMs)
      ? context.initialModeAcquisitionElapsedMs
      : null,
    initialModeComposerReadyElapsedMs: Number.isFinite(
      context.initialModeComposerReadyElapsedMs
    )
      ? context.initialModeComposerReadyElapsedMs
      : null,
    initialModeComposerReady: context.initialModeComposerReady === true,
    selectedModeBefore: context.selectedModeBefore,
    selectedModeBeforeProven: context.selectedModeBeforeProven === true,
    selectedModeBeforeProofKind: context.selectedModeBeforeProofKind || null,
    selectedModeBeforeCandidateCount: Number.isInteger(context.selectedModeBeforeCandidateCount)
      ? context.selectedModeBeforeCandidateCount
      : 0,
    selectedModeBeforeNearestDistancePx: Number.isFinite(context.selectedModeBeforeNearestDistancePx)
      ? context.selectedModeBeforeNearestDistancePx
      : null,
    selectionPerformed: context.selectionPerformed === true,
    selectionMechanism: context.selectionMechanism || null,
    selectedModeAfter: context.selectedModeAfter,
    selectedModeAfterProven: context.selectedModeAfterProven === true,
    selectedModeAfterProofKind: context.selectedModeAfterProofKind || null,
    sliderValueAfter: Number.isFinite(context.sliderValueAfter) ? context.sliderValueAfter : null,
    selectionComplete: context.selectionComplete === true,
    conversationWriteBeforeSelection: context.conversationWriteBeforeSelection === true,
    transientForegroundActivated: context.transientForegroundActivated === true,
    transientForegroundProven: context.transientForegroundProven === true,
    backgroundSelectionAttempted: context.backgroundSelectionAttempted === true,
    backgroundSelectionProven: context.backgroundSelectionProven === true,
    foregroundRestoreAttempted: context.foregroundRestoreAttempted === true,
    foregroundRestoreProven: context.foregroundRestoreProven !== false,
    selectionElapsedMs: Number.isFinite(context.selectionElapsedMs) ? context.selectionElapsedMs : null
  };
}

async function _pr810StoredRecord() {
  try {
    const stored = await chrome.storage.local.get(PR810_MODEL_PROFILE_STORAGE_KEY);
    const value = stored?.[PR810_MODEL_PROFILE_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

async function _executeNativeTurnWithModelProfile(message, next) {
  if (message?.characterizeProductModelProfileSupport === true) {
    if (_pr810QueryConflict(message)) throw new Error("PR8_10_MODEL_PROFILE_SUPPORT_FLAG_CONFLICT");
    return {
      modelProfileSelectionSupported: true,
      modelProfileSelectionSchemaVersion: PR810_MODEL_PROFILE_SCHEMA_VERSION,
      supportedProductModes: ["INSTANT", "MEDIUM", "HIGH"],
      sliderIndices: {...PR810_MODEL_MODE_INDEX},
      strictPrewriteVerification: true,
      boundedInitialModeAcquisition: true,
      initialModeAcquisitionTimeoutMs: PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS,
      backgroundSelectionSupported: true,
      transientForegroundRequired: false,
      maxProfileMapped: false
    };
  }

  if (message?.characterizeProductModelProfileSelectionRecord === true) {
    if (_pr810QueryConflict(message)) throw new Error("PR8_10_MODEL_PROFILE_RECORD_FLAG_CONFLICT");
    const expectedLease = _pr810Lease(message?.expectedBrowserAuthorityLeaseId);
    const record = await _pr810StoredRecord();
    if (!record) throw new Error("PR8_10_MODEL_PROFILE_RECORD_UNAVAILABLE");
    if (expectedLease && record.browserAuthorityLeaseId !== expectedLease) {
      throw new Error("PR8_10_MODEL_PROFILE_LEASE_MISMATCH");
    }
    return {
      modelProfileSelectionSupported: true,
      modelProfileSelection: record
    };
  }

  const requestedRaw = message?.requiredModelMode;
  const requestedMode = _pr810Mode(requestedRaw);
  const leaseId = _pr810Lease(message?.browserAuthorityLeaseId);
  const ordinaryWrite = typeof message?.text === "string" && Boolean(message.text.trim()) && leaseId !== null;
  if (!ordinaryWrite || requestedRaw == null) return next(message);
  if (requestedMode === null) throw new Error(`PR8_10_MODEL_MODE_UNSUPPORTED:${String(requestedRaw)}`);
  if (_pr810ModelProfileContext !== null) throw new Error("PR8_10_MODEL_PROFILE_CONTEXT_ALREADY_ACTIVE");

  const context = {
    leaseId,
    requestedModelMode: requestedMode,
    selectionChecked: false,
    selectionComplete: false,
    conversationWriteBeforeSelection: false,
    writeBoundaryListener: null
  };
  _pr810ModelProfileContext = context;
  try {
    const result = await next(message);
    if (context.selectionComplete !== true || context.selectedModeAfterProven !== true || context.selectedModeAfter !== requestedMode) {
      throw new Error("PR8_10_MODEL_PROFILE_PREWRITE_PROOF_MISSING");
    }
    const record = _pr810Record(context);
    try {
      await chrome.storage.local.set({[PR810_MODEL_PROFILE_STORAGE_KEY]: record});
    } catch {}
    return {...result, modelProfileSelection: record};
  } finally {
    if (context.writeBoundaryListener) {
      try { chrome.debugger.onEvent.removeListener(context.writeBoundaryListener); } catch {}
    }
    _pr810ModelProfileContext = null;
  }
};