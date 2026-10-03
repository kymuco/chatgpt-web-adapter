// PR17.2 branch-only background reasoning-slider INSTANT -> MEDIUM proof.
//
// The already-proven HIGH -> INSTANT diagnostic remains untouched. This gate
// requires an inactive runtime tab already proven at INSTANT, focuses the exact
// 0..2 slider, dispatches Home followed by one ArrowRight, and proves MEDIUM.
// It has zero conversation-write, mouse, navigation, tab-create, or tab-activate
// authority.

async function _pr172StepDispatchKey(debuggee, key, code, virtualKeyCode) {
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key,
    code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode
  });
}

async function _pr172StepWaitForMedium(debuggee, timeoutMs = 3000) {
  const startedAt = performance.now();
  let slider = null;
  let selected = null;
  while (performance.now() - startedAt < timeoutMs) {
    slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "MEDIUM"
    );
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    const selectedMedium =
      selected?.selectedModeProven === true &&
      selected?.selectedMode === "MEDIUM";
    const sliderMedium =
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 1 &&
      slider?.currentMode === "MEDIUM";
    if (sliderMedium && (selectedMedium || selected?.selectedModeProven !== true)) {
      return {slider, selected, settled: true};
    }
    await sleep(100);
  }
  return {slider, selected, settled: false};
}

async function _pr172CharacterizeBackgroundSliderInstantToMedium() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    throw new Error("PR17_2_BACKGROUND_STEP_RUNTIME_TAB_MISSING");
  }
  const tab = await chrome.tabs.get(storedId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR17_2_BACKGROUND_STEP_RUNTIME_TAB_INVALID");
  }
  if (tab?.active === true) {
    throw new Error("PR17_2_BACKGROUND_STEP_REQUIRES_INACTIVE_RUNTIME_TAB");
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
    if (before?.selectedModeProven === true && beforeMode !== "INSTANT") {
      throw new Error(
        `PR17_2_BACKGROUND_STEP_INITIAL_MODE_MISMATCH:${beforeMode}`
      );
    }

    const picker = await _pr88SelectionPoint(debuggee, "picker");
    const pickerInstantProven = (
      picker?.found === true &&
      picker?.candidateCount === 1 &&
      picker?.mode === "INSTANT"
    );

    let slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "INSTANT"
    );
    const sliderInstantAlreadyProven = (
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 0 &&
      slider?.currentMode === "INSTANT"
    );

    if (before?.selectedModeProven === true && beforeMode === "INSTANT") {
      initialModeProofKind = "selected_mode_control";
    } else if (sliderInstantAlreadyProven) {
      initialModeProofKind = "exact_slider_value";
    } else if (pickerInstantProven) {
      initialModeProofKind = "picker_mode_control";
    }

    if (initialModeProofKind === null) {
      throw new Error(
        `PR17_2_BACKGROUND_STEP_INITIAL_INSTANT_NOT_PROVEN:` +
        `selected=${beforeMode || "unknown"};` +
        `picker=${picker?.mode || picker?.reason || "unknown"};` +
        `slider=${slider?.reason || "unknown"}`
      );
    }
    selectedModeBefore = "INSTANT";

    if (slider?.found !== true) {
      if (!pickerInstantProven) {
        throw new Error(
          `PR17_2_BACKGROUND_STEP_PICKER_NOT_PROVEN:${picker?.reason || "unknown"}`
        );
      }
      const opened = await _pr172BackgroundDomTriggerClick(debuggee, "INSTANT");
      if (
        opened?.clicked !== true ||
        opened?.candidateCount !== 1 ||
        opened?.mode !== "INSTANT"
      ) {
        throw new Error(
          `PR17_2_BACKGROUND_STEP_TRIGGER_CLICK_NOT_PROVEN:${opened?.reason || "unknown"}`
        );
      }
      openedByProbe = opened?.openBefore !== true;
      slider = await _pr172WaitForSliderSnapshot(debuggee, "INSTANT", 3000);
    }

    if (
      slider?.found !== true ||
      slider?.candidateCount !== 1 ||
      slider?.min !== 0 ||
      slider?.max !== 2 ||
      slider?.stepCount !== 3 ||
      slider?.now !== 0 ||
      slider?.currentMode !== "INSTANT"
    ) {
      throw new Error(
        `PR17_2_BACKGROUND_STEP_INITIAL_SLIDER_NOT_PROVEN:${slider?.reason || "unknown"}`
      );
    }

    const focused = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "focus",
      "INSTANT"
    );
    if (
      focused?.found !== true ||
      focused?.focusProven !== true ||
      focused?.now !== 0
    ) {
      throw new Error("PR17_2_BACKGROUND_STEP_SLIDER_FOCUS_NOT_PROVEN");
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
      throw new Error("PR17_2_BACKGROUND_STEP_HOME_BASELINE_NOT_PROVEN");
    }

    await _pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39);
    const settled = await _pr172StepWaitForMedium(debuggee, 3000);
    if (settled?.settled !== true) {
      throw new Error("PR17_2_BACKGROUND_STEP_DID_NOT_SETTLE_TO_MEDIUM");
    }
    if (conversationWriteCount !== 0) {
      throw new Error("PR17_2_BACKGROUND_STEP_CONVERSATION_WRITE_OBSERVED");
    }

    const tabAfter = await chrome.tabs.get(storedId);
    if (tabActivatedDuringGate || tabAfter?.active === true) {
      throw new Error("PR17_2_BACKGROUND_STEP_TAB_ACTIVATION_OBSERVED");
    }

    result = {
      diagnosticOnly: true,
      backgroundReasoningStepMutation: true,
      runtimeTabPresent: true,
      tabWasActive: false,
      documentVisibleBefore,
      selectedModeBefore,
      selectedModeBeforeProven: true,
      initialModeProofKind,
      sliderFound: true,
      sliderMin: 0,
      sliderMax: 2,
      sliderNowBefore: 0,
      sliderFocusProven: true,
      homeDispatched: true,
      homeBaselineProven: afterHome?.now === 0,
      arrowRightDispatchCount: 1,
      targetMode: "MEDIUM",
      targetSliderValue: 1,
      sliderNowAfter: settled.slider?.now ?? null,
      selectedModeAfter:
        settled.selected?.selectedModeProven === true
          ? settled.selected.selectedMode
          : settled.slider?.currentMode || null,
      selectedModeAfterProven: true,
      reasoningValueMutationAttempted: true,
      reasoningValueMutationProven: settled.slider?.now === 1,
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
    if (attached && openedByProbe && selectedModeBefore === "INSTANT") {
      uiTriggerRestoreAttempted = true;
      try {
        const restored = await _pr172BackgroundDomTriggerClick(
          debuggee,
          "INSTANT",
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
    throw new Error("PR17_2_BACKGROUND_STEP_RESULT_MISSING");
  }
  return result;
}

function _pr172StepDiagnosticMatches(message) {
  return message?.characterizeBackgroundReasoningSliderInstantToMedium === true;
}

async function _pr172HandleStepDiagnostic(message) {
  _pr172MutationRejectWriteBearingMessage(message);
  return _pr172CharacterizeBackgroundSliderInstantToMedium();
}

registerNativeTurnDiagnosticHandler(
  "reasoning-slider-background-step-mutation",
  _pr172StepDiagnosticMatches,
  _pr172HandleStepDiagnostic
);
