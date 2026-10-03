// PR17.2 branch-only background reasoning-slider mutation proof.
//
// This diagnostic permits exactly one reasoning-value mutation: HIGH -> INSTANT
// through keyboard Home on the already-proven exact 0..2 slider. It must not
// insert/submit conversation text, dispatch mouse input, navigate, create, or
// activate tabs. Remove before production merge after evidence is preserved.

function _pr172MutationRejectWriteBearingMessage(message) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.requiredModelMode != null
  ) {
    throw new Error("PR17_2_BACKGROUND_MUTATION_MUST_BE_NO_CONVERSATION_WRITE");
  }
}

function _pr172MutationIsConversationWrite(url, method) {
  if (String(method || "").toUpperCase() !== "POST") return false;
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return false;
    const path = parsed.pathname.replace(/\/+$/, "");
    return (
      path.endsWith("/backend-api/f/conversation") ||
      path.endsWith("/backend-api/conversation")
    );
  } catch {
    return false;
  }
}

async function _pr172MutationDispatchHome(debuggee) {
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "Home",
    code: "Home",
    windowsVirtualKeyCode: 36,
    nativeVirtualKeyCode: 36
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Home",
    code: "Home",
    windowsVirtualKeyCode: 36,
    nativeVirtualKeyCode: 36
  });
}

async function _pr172MutationWaitForInstant(debuggee, timeoutMs = 3000) {
  const startedAt = performance.now();
  let slider = null;
  let selected = null;
  while (performance.now() - startedAt < timeoutMs) {
    slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "INSTANT"
    );
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    const selectedInstant =
      selected?.selectedModeProven === true &&
      selected?.selectedMode === "INSTANT";
    const sliderInstant =
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 0 &&
      slider?.currentMode === "INSTANT";
    if (sliderInstant && (selectedInstant || selected?.selectedModeProven !== true)) {
      return {slider, selected, settled: true};
    }
    await sleep(100);
  }
  return {slider, selected, settled: false};
}

async function _pr172CharacterizeBackgroundSliderHomeToInstant() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    throw new Error("PR17_2_BACKGROUND_MUTATION_RUNTIME_TAB_MISSING");
  }
  const tab = await chrome.tabs.get(storedId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR17_2_BACKGROUND_MUTATION_RUNTIME_TAB_INVALID");
  }
  if (tab?.active === true) {
    throw new Error("PR17_2_BACKGROUND_MUTATION_REQUIRES_INACTIVE_RUNTIME_TAB");
  }

  const debuggee = {tabId: storedId};
  let attached = false;
  let openedByProbe = false;
  let selectedModeBefore = null;
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
    if (before?.selectedModeProven === true && beforeMode !== "HIGH") {
      throw new Error(
        `PR17_2_BACKGROUND_MUTATION_INITIAL_MODE_MISMATCH:${beforeMode}`
      );
    }

    const picker = await _pr88SelectionPoint(debuggee, "picker");
    const pickerHighProven = (
      picker?.found === true &&
      picker?.candidateCount === 1 &&
      picker?.mode === "HIGH"
    );

    let slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot",
      "HIGH"
    );
    const sliderHighAlreadyProven = (
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.now === 2 &&
      slider?.currentMode === "HIGH"
    );

    let initialModeProofKind = null;
    if (before?.selectedModeProven === true && beforeMode === "HIGH") {
      initialModeProofKind = "selected_mode_control";
    } else if (sliderHighAlreadyProven) {
      initialModeProofKind = "exact_slider_value";
    } else if (pickerHighProven) {
      initialModeProofKind = "picker_mode_control";
    }

    if (initialModeProofKind === null) {
      throw new Error(
        `PR17_2_BACKGROUND_MUTATION_INITIAL_HIGH_NOT_PROVEN:` +
        `selected=${beforeMode || "unknown"};` +
        `picker=${picker?.mode || picker?.reason || "unknown"};` +
        `slider=${slider?.reason || "unknown"}`
      );
    }
    selectedModeBefore = "HIGH";

    if (slider?.found !== true) {
      if (!pickerHighProven) {
        throw new Error(
          `PR17_2_BACKGROUND_MUTATION_PICKER_NOT_PROVEN:${picker?.reason || "unknown"}`
        );
      }
      const opened = await _pr172BackgroundDomTriggerClick(debuggee, "HIGH");
      if (
        opened?.clicked !== true ||
        opened?.candidateCount !== 1 ||
        opened?.mode !== "HIGH"
      ) {
        throw new Error(
          `PR17_2_BACKGROUND_MUTATION_TRIGGER_CLICK_NOT_PROVEN:${opened?.reason || "unknown"}`
        );
      }
      openedByProbe = opened?.openBefore !== true;
      slider = await _pr172WaitForSliderSnapshot(debuggee, "HIGH", 3000);
    }

    if (
      slider?.found !== true ||
      slider?.candidateCount !== 1 ||
      slider?.min !== 0 ||
      slider?.max !== 2 ||
      slider?.stepCount !== 3 ||
      slider?.now !== 2 ||
      slider?.currentMode !== "HIGH"
    ) {
      throw new Error(
        `PR17_2_BACKGROUND_MUTATION_INITIAL_SLIDER_NOT_PROVEN:${slider?.reason || "unknown"}`
      );
    }

    const focused = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "focus",
      "HIGH"
    );
    if (
      focused?.found !== true ||
      focused?.focusProven !== true ||
      focused?.now !== 2
    ) {
      throw new Error("PR17_2_BACKGROUND_MUTATION_SLIDER_FOCUS_NOT_PROVEN");
    }

    await _pr172MutationDispatchHome(debuggee);
    const settled = await _pr172MutationWaitForInstant(debuggee, 3000);
    if (settled?.settled !== true) {
      throw new Error("PR17_2_BACKGROUND_MUTATION_DID_NOT_SETTLE_TO_INSTANT");
    }
    if (conversationWriteCount !== 0) {
      throw new Error("PR17_2_BACKGROUND_MUTATION_CONVERSATION_WRITE_OBSERVED");
    }

    const tabAfter = await chrome.tabs.get(storedId);
    if (tabActivatedDuringGate || tabAfter?.active === true) {
      throw new Error("PR17_2_BACKGROUND_MUTATION_TAB_ACTIVATION_OBSERVED");
    }

    result = {
      diagnosticOnly: true,
      backgroundReasoningMutation: true,
      runtimeTabPresent: true,
      tabWasActive: false,
      documentVisibleBefore,
      selectedModeBefore,
      selectedModeBeforeProven: true,
      initialModeProofKind,
      sliderFound: true,
      sliderMin: 0,
      sliderMax: 2,
      sliderNowBefore: 2,
      sliderFocusProven: true,
      homeDispatched: true,
      targetMode: "INSTANT",
      sliderNowAfter: settled.slider?.now ?? null,
      selectedModeAfter:
        settled.selected?.selectedModeProven === true
          ? settled.selected.selectedMode
          : settled.slider?.currentMode || null,
      selectedModeAfterProven: true,
      reasoningValueMutationAttempted: true,
      reasoningValueMutationProven: settled.slider?.now === 0,
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
    if (attached && openedByProbe && selectedModeBefore === "HIGH") {
      uiTriggerRestoreAttempted = true;
      try {
        const restored = await _pr172BackgroundDomTriggerClick(
          debuggee,
          "HIGH",
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
    throw new Error("PR17_2_BACKGROUND_MUTATION_RESULT_MISSING");
  }
  return result;
}

function _pr172MutationDiagnosticMatches(message) {
  return message?.characterizeBackgroundReasoningSliderHomeToInstant === true;
}

async function _pr172HandleMutationDiagnostic(message) {
  _pr172MutationRejectWriteBearingMessage(message);
  return _pr172CharacterizeBackgroundSliderHomeToInstant();
}

registerNativeTurnDiagnosticHandler(
  "reasoning-slider-background-mutation",
  _pr172MutationDiagnosticMatches,
  _pr172HandleMutationDiagnostic
);
