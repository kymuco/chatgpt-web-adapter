// PR17.2 branch-only background reasoning-slider MEDIUM -> HIGH proof.
//
// This gate requires the inactive runtime tab to start at MEDIUM. It proves an
// absolute Home baseline (INSTANT/0), then proves the discrete sequence
// ArrowRight -> MEDIUM/1 -> ArrowRight -> HIGH/2. It has zero conversation
// write, mouse, navigation, tab-create, or tab-activate authority.

async function _pr172StepWaitForHigh(debuggee, timeoutMs = 3000) {
  const startedAt = performance.now();
  let slider = null;
  let selected = null;
  while (performance.now() - startedAt < timeoutMs) {
    slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "HIGH"
    );
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    const selectedHigh =
      selected?.selectedModeProven === true &&
      selected?.selectedMode === "HIGH";
    const sliderHigh =
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 2 &&
      slider?.currentMode === "HIGH";
    if (sliderHigh && (selectedHigh || selected?.selectedModeProven !== true)) {
      return {slider, selected, settled: true};
    }
    await sleep(100);
  }
  return {slider, selected, settled: false};
}

async function _pr172CharacterizeBackgroundSliderMediumToHigh() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    throw new Error("PR17_2_BACKGROUND_HIGH_RUNTIME_TAB_MISSING");
  }
  const tab = await chrome.tabs.get(storedId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR17_2_BACKGROUND_HIGH_RUNTIME_TAB_INVALID");
  }
  if (tab?.active === true) {
    throw new Error("PR17_2_BACKGROUND_HIGH_REQUIRES_INACTIVE_RUNTIME_TAB");
  }

  const debuggee = {tabId: storedId};
  let attached = false;
  let openedByProbe = false;
  let selectedModeBefore = null;
  let initialModeProofKind = null;
  let uiTriggerRestoreAttempted = false;
  let uiTriggerRestoreProven = false;
  let debuggerAttachedAfter = null;
  let conversationWriteCount = 0;
  let networkRequestCount = 0;
  let tabActivatedDuringGate = false;
  let result = null;

  const onActivated = (activeInfo) => {
    if (activeInfo?.tabId === storedId) tabActivatedDuringGate = true;
  };
  const onDebuggerEvent = (source, method, params) => {
    if (source?.tabId !== storedId || method !== "Network.requestWillBeSent") return;
    networkRequestCount += 1;
    if (
      _pr172MutationIsConversationWrite(
        params?.request?.url || "",
        params?.request?.method || ""
      )
    ) {
      conversationWriteCount += 1;
    }
  };

  chrome.tabs.onActivated.addListener(onActivated);
  chrome.debugger.onEvent.addListener(onDebuggerEvent);
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "Network.enable");

    const visibility = await chrome.debugger.sendCommand(
      debuggee,
      "Runtime.evaluate",
      {
        expression:
          "(() => ({visible: document.visibilityState === 'visible' && document.hidden !== true}))()",
        returnByValue: true,
        awaitPromise: true
      }
    );
    const documentVisibleBefore = visibility?.result?.value?.visible === true;

    const before = await _pr88InstantSelectedModeSnapshot(debuggee);
    const beforeMode =
      typeof before?.selectedMode === "string" ? before.selectedMode : null;
    if (before?.selectedModeProven === true && beforeMode !== "MEDIUM") {
      throw new Error(
        `PR17_2_BACKGROUND_HIGH_INITIAL_MODE_MISMATCH:${beforeMode}`
      );
    }

    const picker = await _pr88SelectionPoint(debuggee, "picker");
    const pickerMediumProven = (
      picker?.found === true &&
      picker?.candidateCount === 1 &&
      picker?.mode === "MEDIUM"
    );

    let slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "MEDIUM"
    );
    const sliderMediumAlreadyProven = (
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 1 &&
      slider?.currentMode === "MEDIUM"
    );

    if (before?.selectedModeProven === true && beforeMode === "MEDIUM") {
      initialModeProofKind = "selected_mode_control";
    } else if (sliderMediumAlreadyProven) {
      initialModeProofKind = "exact_slider_value";
    } else if (pickerMediumProven) {
      initialModeProofKind = "picker_mode_control";
    }

    if (initialModeProofKind === null) {
      throw new Error(
        `PR17_2_BACKGROUND_HIGH_INITIAL_MEDIUM_NOT_PROVEN:` +
        `selected=${beforeMode || "unknown"};` +
        `picker=${picker?.mode || picker?.reason || "unknown"};` +
        `slider=${slider?.reason || "unknown"}`
      );
    }
    selectedModeBefore = "MEDIUM";

    if (slider?.found !== true) {
      if (!pickerMediumProven) {
        throw new Error(
          `PR17_2_BACKGROUND_HIGH_PICKER_NOT_PROVEN:${picker?.reason || "unknown"}`
        );
      }
      const opened = await _pr172BackgroundDomTriggerClick(debuggee, "MEDIUM");
      if (
        opened?.clicked !== true ||
        opened?.candidateCount !== 1 ||
        opened?.mode !== "MEDIUM"
      ) {
        throw new Error(
          `PR17_2_BACKGROUND_HIGH_TRIGGER_CLICK_NOT_PROVEN:${opened?.reason || "unknown"}`
        );
      }
      openedByProbe = opened?.openBefore !== true;
      slider = await _pr172WaitForSliderSnapshot(debuggee, "MEDIUM", 3000);
    }

    if (
      slider?.found !== true ||
      slider?.candidateCount !== 1 ||
      slider?.min !== 0 ||
      slider?.max !== 2 ||
      slider?.stepCount !== 3 ||
      slider?.now !== 1 ||
      slider?.currentMode !== "MEDIUM"
    ) {
      throw new Error(
        `PR17_2_BACKGROUND_HIGH_INITIAL_SLIDER_NOT_PROVEN:${slider?.reason || "unknown"}`
      );
    }

    const focused = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "focus",
      "MEDIUM"
    );
    if (
      focused?.found !== true ||
      focused?.focusProven !== true ||
      focused?.now !== 1
    ) {
      throw new Error("PR17_2_BACKGROUND_HIGH_SLIDER_FOCUS_NOT_PROVEN");
    }

    await _pr172StepDispatchKey(debuggee, "Home", "Home", 36);
    const afterHome = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "INSTANT"
    );
    if (
      afterHome?.found !== true ||
      afterHome?.now !== 0 ||
      afterHome?.currentMode !== "INSTANT"
    ) {
      throw new Error("PR17_2_BACKGROUND_HIGH_HOME_BASELINE_NOT_PROVEN");
    }

    await _pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39);
    const mediumSettled = await _pr172StepWaitForMedium(debuggee, 3000);
    if (mediumSettled?.settled !== true || mediumSettled?.slider?.now !== 1) {
      throw new Error("PR17_2_BACKGROUND_HIGH_INTERMEDIATE_MEDIUM_NOT_PROVEN");
    }

    await _pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39);
    const settled = await _pr172StepWaitForHigh(debuggee, 3000);
    if (settled?.settled !== true) {
      throw new Error("PR17_2_BACKGROUND_HIGH_DID_NOT_SETTLE_TO_HIGH");
    }
    if (conversationWriteCount !== 0) {
      throw new Error("PR17_2_BACKGROUND_HIGH_CONVERSATION_WRITE_OBSERVED");
    }

    const tabAfter = await chrome.tabs.get(storedId);
    if (tabActivatedDuringGate || tabAfter?.active === true) {
      throw new Error("PR17_2_BACKGROUND_HIGH_TAB_ACTIVATION_OBSERVED");
    }

    result = {
      diagnosticOnly: true,
      backgroundReasoningHighMutation: true,
      runtimeTabPresent: true,
      tabWasActive: false,
      documentVisibleBefore,
      selectedModeBefore,
      selectedModeBeforeProven: true,
      initialModeProofKind,
      sliderFound: true,
      sliderMin: 0,
      sliderMax: 2,
      sliderNowBefore: 1,
      sliderFocusProven: true,
      homeDispatched: true,
      homeBaselineProven: afterHome?.now === 0,
      intermediateMediumProven: mediumSettled?.slider?.now === 1,
      arrowRightDispatchCount: 2,
      targetMode: "HIGH",
      targetSliderValue: 2,
      sliderNowAfter: settled.slider?.now ?? null,
      selectedModeAfter:
        settled.selected?.selectedModeProven === true
          ? settled.selected.selectedMode
          : settled.slider?.currentMode || null,
      selectedModeAfterProven: true,
      reasoningValueMutationAttempted: true,
      reasoningValueMutationProven: settled.slider?.now === 2,
      keyDispatchPerformed: true,
      mouseDispatchPerformed: false,
      conversationWriteAttempted: false,
      conversationWriteObserved: false,
      conversationWriteCount,
      networkRequestCount,
      tabActivated: false,
      tabActivatedDuringGate
    };
  } finally {
    if (attached && openedByProbe && selectedModeBefore === "MEDIUM") {
      uiTriggerRestoreAttempted = true;
      try {
        const restored = await _pr172BackgroundDomTriggerClick(
          debuggee,
          "MEDIUM",
          true
        );
        uiTriggerRestoreProven = (
          restored?.clicked === true &&
          restored?.retainedReferenceUsed === true
        );
      } catch {
        uiTriggerRestoreProven = false;
      }
    }

    if (result) {
      result.uiTriggerRestoreAttempted = uiTriggerRestoreAttempted;
      result.uiTriggerRestoreProven = openedByProbe
        ? uiTriggerRestoreProven
        : true;
    }

    try { chrome.tabs.onActivated.removeListener(onActivated); } catch {}
    try { chrome.debugger.onEvent.removeListener(onDebuggerEvent); } catch {}

    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === storedId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
    if (result) result.debuggerAttachedAfter = debuggerAttachedAfter;
  }

  if (!result) {
    throw new Error("PR17_2_BACKGROUND_HIGH_RESULT_MISSING");
  }
  return result;
}

function _pr172HighDiagnosticMatches(message) {
  return message?.characterizeBackgroundReasoningSliderMediumToHigh === true;
}

async function _pr172HandleHighDiagnostic(message) {
  _pr172MutationRejectWriteBearingMessage(message);
  return _pr172CharacterizeBackgroundSliderMediumToHigh();
}

registerNativeTurnDiagnosticHandler(
  "reasoning-slider-background-high-mutation",
  _pr172HighDiagnosticMatches,
  _pr172HandleHighDiagnostic
);
