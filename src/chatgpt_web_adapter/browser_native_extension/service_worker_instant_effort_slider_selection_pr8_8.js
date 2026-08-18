// PR8.8 production Instant selection overlay.
// Uses explicit reasoning-effort helpers. No monkey-patching of the shared raw
// click or slider snapshot primitives is required.

_pr88SelectionEnsureInstant = async function _pr88SelectionEnsureInstantViaEffortSlider(debuggee, context) {
  if (context.selectionChecked === true) return;
  context.selectionChecked = true;
  const startedAt = performance.now();

  const before = await _pr88InstantSelectedModeSnapshot(debuggee);
  context.selectedModeBeforeSelection = before?.selectedMode || null;
  context.selectedModeBeforeSelectionProven = before?.selectedModeProven === true;
  context.selectedModeBeforeSelectionProofKind = before?.proofKind || "unknown";
  context.selectedModeBeforeSelectionCandidateCount = Number.isInteger(before?.candidateCount)
    ? before.candidateCount : 0;

  Object.assign(context, {
    instantEffortSelectionSchemaVersion: PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION,
    selectionMechanism: null,
    instantEffortPickerClickPerformed: false,
    effortSliderCandidateCount: 0,
    effortSliderAriaValueMin: null,
    effortSliderAriaValueMax: null,
    effortSliderAriaValueNowBefore: null,
    effortSliderAriaValueNowAfter: null,
    effortSliderStepCount: null,
    effortSliderFocusProven: false,
    effortSliderHomeDispatched: false,
    effortSliderMinReachedProven: false,
    effortSliderObservedAfterHome: false,
    advancedControlClicked: false,
    modelControlClicked: false
  });

  if (before?.selectedModeProven !== true || typeof before?.selectedMode !== "string") {
    throw new Error("PR8_8_INSTANT_EFFORT_INITIAL_MODE_NOT_PROVEN");
  }
  if (before.selectedMode === "INSTANT") {
    context.selectionPerformed = false;
    context.selectionMechanism = "NO_SELECTION_REQUIRED";
    context.selectedModeAfterSelection = "INSTANT";
    context.selectedModeAfterSelectionProven = true;
    context.selectedModeAfterSelectionProofKind = before.proofKind || "unknown";
    context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
    context.selectionMutationElapsedMs = 0;
    context.selectionComplete = true;
    return;
  }

  context.selectionPerformed = true;
  context.selectionMechanism = "REASONING_EFFORT_SLIDER_HOME";
  _pr88SelectionInstallNetworkWindow(debuggee, context);
  const mutationStartedAt = performance.now();

  const picker = await _pr88SelectionPoint(debuggee, "picker");
  context.pickerCandidateCount = Number.isInteger(picker?.candidateCount) ? picker.candidateCount : 0;
  context.pickerNearestDistancePx = _pr88SelectionSafeInt(picker?.nearestDistancePx);
  context.pickerModeBeforeClick = typeof picker?.mode === "string" ? picker.mode : null;
  context.instantOptionCandidateCount = 0;
  if (picker?.found !== true || picker?.candidateCount !== 1 || picker?.mode !== before.selectedMode) {
    throw new Error(`PR8_8_INSTANT_EFFORT_PICKER_NOT_PROVEN:${picker?.reason || "identity_mismatch"}`);
  }

  let slider = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "snapshot");
  const alreadyOpen = (
    slider?.found === true && slider?.candidateCount === 1 &&
    slider?.min === 0 && slider?.max === 2 && slider?.stepCount === 3 &&
    slider?.currentControlOpen === true && slider?.currentMode === before.selectedMode
  );
  if (!alreadyOpen) {
    await _pr88InstantEffortOpenPickerWithFallback(debuggee, picker, before.selectedMode);
    context.instantEffortPickerClickPerformed = true;
    slider = await _pr88InstantEffortWaitForResolvedSlider(debuggee, before.selectedMode, 3000);
  }

  context.effortSliderCandidateCount = Number.isInteger(slider?.candidateCount) ? slider.candidateCount : 0;
  context.effortSliderAriaValueMin = Number.isFinite(slider?.min) ? slider.min : null;
  context.effortSliderAriaValueMax = Number.isFinite(slider?.max) ? slider.max : null;
  context.effortSliderAriaValueNowBefore = Number.isFinite(slider?.now) ? slider.now : null;
  context.effortSliderStepCount = Number.isInteger(slider?.stepCount) ? slider.stepCount : null;
  if (
    slider?.found !== true || slider?.candidateCount !== 1 ||
    slider?.min !== 0 || slider?.max !== 2 || slider?.stepCount !== 3
  ) {
    throw new Error(`PR8_8_INSTANT_EFFORT_SLIDER_CONTRACT_NOT_PROVEN:${slider?.reason || "range_mismatch"}`);
  }
  if (context.unexpectedConversationWriteBeforeSelectionComplete === true) {
    throw new Error("PR8_8_INSTANT_EFFORT_CONVERSATION_WRITE_BEFORE_SELECTION");
  }

  const focused = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "focus");
  context.effortSliderFocusProven = focused?.focusProven === true;
  if (
    focused?.found !== true || focused?.candidateCount !== 1 ||
    focused?.min !== 0 || focused?.max !== 2 ||
    focused?.stepCount !== 3 || focused?.focusProven !== true
  ) throw new Error("PR8_8_INSTANT_EFFORT_SLIDER_FOCUS_NOT_PROVEN");

  await _pr88InstantEffortDispatchHome(debuggee);
  context.effortSliderHomeDispatched = true;

  const settled = await _pr88InstantEffortWaitForResolvedSelected(
    debuggee, PR88_INSTANT_EFFORT_SELECTION_SETTLE_TIMEOUT_MS
  );
  const after = settled?.selected || null;
  const sliderAfter = settled?.slider || null;
  context.effortSliderMinReachedProven = settled?.sliderMinReached === true;
  context.effortSliderObservedAfterHome = settled?.sliderObservedAfterHome === true;
  context.effortSliderAriaValueNowAfter = Number.isFinite(sliderAfter?.now)
    ? sliderAfter.now : (context.effortSliderMinReachedProven ? 0 : null);
  context.selectedModeAfterSelection = after?.selectedMode || null;
  context.selectedModeAfterSelectionProven = after?.selectedModeProven === true;
  context.selectedModeAfterSelectionProofKind = after?.proofKind || "unknown";

  if (context.unexpectedConversationWriteBeforeSelectionComplete === true) {
    throw new Error("PR8_8_INSTANT_EFFORT_CONVERSATION_WRITE_BEFORE_SELECTION");
  }
  if (after?.selectedModeProven !== true || after?.selectedMode !== "INSTANT") {
    throw new Error("PR8_8_INSTANT_EFFORT_DID_NOT_SETTLE_TO_INSTANT");
  }
  if (settled?.sliderObservedAfterHome === true && settled?.sliderMinReached !== true) {
    throw new Error("PR8_8_INSTANT_EFFORT_SLIDER_MIN_NOT_REACHED");
  }

  context.selectionMutationElapsedMs = _pr88SelectionDurationMs(mutationStartedAt);
  context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
  context.selectionComplete = true;
};
