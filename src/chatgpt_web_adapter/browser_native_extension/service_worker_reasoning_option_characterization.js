// PR17.2 branch-only zero-write characterization for direct reasoning options.
//
// This surface observes only already-visible ChatGPT reasoning/model controls.
// It must not focus, click, type, submit, navigate, create/activate tabs, or
// select a reasoning mode. Remove before production merge after evidence is
// preserved by regressions and the production direct-selection path.

function _pr172RejectWriteBearingMessage(message) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.requiredModelMode != null
  ) {
    throw new Error("PR17_2_REASONING_OPTION_PROBE_MUST_BE_NO_WRITE");
  }
}

function _pr172TargetPolicy(value) {
  const normalized = typeof value === "string" ? value.trim().toUpperCase() : "";
  if (normalized === "ACTIVE" || normalized === "RUNTIME") return normalized;
  return "ACTIVE";
}

function _pr172ReasoningOptionSurfaceExpression() {
  return `(() => {
    const bounded = (value, max = 160) => {
      if (typeof value !== 'string') return null;
      const normalized = value.trim();
      return normalized ? normalized.slice(0, max) : null;
    };
    const normalize = (value) =>
      String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const classify = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (
        text === 'instant' ||
        text === 'мгновенно' ||
        text.startsWith('instant ') ||
        text.includes(' instant') ||
        text.startsWith('мгновенно ') ||
        text.includes(' мгновенно')
      ) return 'INSTANT';
      if (
        text === 'medium' ||
        text === 'средний' ||
        text.includes('thinking standard')
      ) return 'MEDIUM';
      if (
        text === 'extra high' ||
        text === 'очень высокий' ||
        text.includes('thinking heavy')
      ) return 'EXTRA_HIGH';
      if (
        text === 'high' ||
        text === 'высокий' ||
        text.includes('thinking extended')
      ) return 'HIGH';
      return null;
    };
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return (
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        style.opacity !== '0'
      );
    };
    const rectOf = (element) => {
      if (!(element instanceof Element)) return null;
      const rect = element.getBoundingClientRect();
      return {
        left: Math.round(rect.left * 100) / 100,
        top: Math.round(rect.top * 100) / 100,
        width: Math.round(rect.width * 100) / 100,
        height: Math.round(rect.height * 100) / 100,
        centerX: Math.round((rect.left + rect.width / 2) * 100) / 100,
        centerY: Math.round((rect.top + rect.height / 2) * 100) / 100
      };
    };
    const fields = (element) => [
      typeof element?.innerText === 'string' ? element.innerText.slice(0, 160) : '',
      element?.getAttribute?.('aria-label'),
      element?.getAttribute?.('title')
    ];
    const classifyElement = (element) => {
      const modes = Array.from(new Set(fields(element).map(classify).filter(Boolean)));
      return modes.length === 1 ? modes[0] : null;
    };
    const identity = (element) => {
      if (!(element instanceof Element)) return null;
      return {
        tagName: element.tagName.toLowerCase(),
        role: bounded(element.getAttribute('role')),
        dataTestid: bounded(element.getAttribute('data-testid')),
        ariaLabel: bounded(element.getAttribute('aria-label')),
        title: bounded(element.getAttribute('title')),
        type: bounded(element.getAttribute('type')),
        ariaChecked: bounded(element.getAttribute('aria-checked')),
        ariaSelected: bounded(element.getAttribute('aria-selected')),
        ariaCurrent: bounded(element.getAttribute('aria-current')),
        ariaExpanded: bounded(element.getAttribute('aria-expanded')),
        ariaHaspopup: bounded(element.getAttribute('aria-haspopup')),
        dataState: bounded(element.getAttribute('data-state')),
        disabled: element.disabled === true,
        ariaDisabled: bounded(element.getAttribute('aria-disabled'))
      };
    };

    const historicalComposer = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ].map((selector) => document.querySelector(selector))
      .find((element) => element && visible(element));
    const semanticCandidates = historicalComposer ? [] : Array.from(
      document.querySelectorAll(
        '[contenteditable="true"][role="textbox"][aria-multiline="true"]'
      )
    ).filter((candidate) =>
      visible(candidate) &&
      candidate.closest('main') &&
      candidate.closest('form')
    );
    const composer = historicalComposer ||
      (semanticCandidates.length === 1 ? semanticCandidates[0] : null);

    const composerRect = composer?.getBoundingClientRect?.() || null;
    const controls = [];
    if (composerRect) {
      for (const element of Array.from(
        document.querySelectorAll('button,[role="button"]')
      ).filter(visible)) {
        const mode = classifyElement(element);
        if (!mode) continue;
        const rect = element.getBoundingClientRect();
        const dx = Math.max(
          0,
          Math.max(composerRect.left - rect.right, rect.left - composerRect.right)
        );
        const dy = Math.max(
          0,
          Math.max(composerRect.top - rect.bottom, rect.top - composerRect.bottom)
        );
        const distancePx = Math.round(Math.hypot(dx, dy));
        if (distancePx > 800) continue;
        controls.push({ element, mode, distancePx });
      }
    }
    controls.sort((left, right) => left.distancePx - right.distancePx);
    const pickerControl = controls.length ? controls[0] : null;

    const visibleSurfaces = Array.from(document.querySelectorAll(
      '[role="menu"],[role="listbox"],[role="dialog"]'
    )).filter(visible);

    const surfaceActionables = [];
    for (let surfaceIndex = 0; surfaceIndex < visibleSurfaces.length; surfaceIndex += 1) {
      const surface = visibleSurfaces[surfaceIndex];
      const surfaceRole = bounded(surface.getAttribute('role'));
      const candidates = Array.from(surface.querySelectorAll(
        '[role="menuitem"],[role="option"],[role="radio"],button,[role="button"]'
      )).filter(visible);
      for (const element of candidates) {
        const parentRoles = [];
        let cursor = element.parentElement;
        for (let depth = 0; cursor && depth < 5; depth += 1, cursor = cursor.parentElement) {
          const role = bounded(cursor.getAttribute('role'));
          if (role) parentRoles.push(role);
          if (cursor === surface) break;
        }
        surfaceActionables.push({
          surfaceIndex,
          surfaceRole,
          semanticText: bounded(
            typeof element.innerText === 'string' ? element.innerText : '',
            120
          ),
          classifiedMode: classifyElement(element),
          parentRoles,
          ...identity(element),
          rect: rectOf(element)
        });
      }
    }

    const surfaces = visibleSurfaces.slice(0, 12).map((surface, index) => ({
      index,
      role: bounded(surface.getAttribute('role')),
      ariaLabel: bounded(surface.getAttribute('aria-label')),
      dataState: bounded(surface.getAttribute('data-state')),
      rect: rectOf(surface),
      actionableCount: surfaceActionables.filter(
        (item) => item.surfaceIndex === index
      ).length
    }));

    const actionables = Array.from(document.querySelectorAll(
      '[role="menuitem"],[role="option"],[role="radio"],button,[role="button"]'
    )).filter(visible);
    const options = [];
    for (const element of actionables) {
      const mode = classifyElement(element);
      if (!mode) continue;
      const rect = rectOf(element);
      const centerHit = rect
        ? document.elementFromPoint(rect.centerX, rect.centerY)
        : null;
      let distanceToPickerPx = null;
      if (pickerControl?.element) {
        const source = pickerControl.element.getBoundingClientRect();
        const target = element.getBoundingClientRect();
        distanceToPickerPx = Math.round(Math.hypot(
          (source.left + source.width / 2) - (target.left + target.width / 2),
          (source.top + source.height / 2) - (target.top + target.height / 2)
        ));
      }
      options.push({
        mode,
        ...identity(element),
        rect,
        distanceToPickerPx,
        insideMenu: Boolean(element.closest('[role="menu"]')),
        insideListbox: Boolean(element.closest('[role="listbox"]')),
        insideDialog: Boolean(element.closest('[role="dialog"]')),
        centerHitTagName:
          centerHit instanceof Element ? centerHit.tagName.toLowerCase() : null,
        centerHitIsSelfOrDescendant: Boolean(
          centerHit && (centerHit === element || element.contains(centerHit))
        )
      });
    }

    const counts = {};
    for (const option of options) {
      counts[option.mode] = (counts[option.mode] || 0) + 1;
    }

    return {
      documentVisibilityState: document.visibilityState || null,
      documentHidden: document.hidden === true,
      composerPresent: Boolean(composer),
      pickerControl: pickerControl ? {
        mode: pickerControl.mode,
        distancePx: pickerControl.distancePx,
        ...identity(pickerControl.element),
        rect: rectOf(pickerControl.element)
      } : null,
      pickerControlCandidateCount: controls.length,
      surfaceCount: surfaces.length,
      surfaces,
      surfaceActionableCount: surfaceActionables.length,
      surfaceActionables: surfaceActionables.slice(0, 48),
      optionCandidateCount: options.length,
      optionCountsByMode: counts,
      options: options.slice(0, 32)
    };
  })()`;
}

async function _pr172ResolveDiagnosticTab(policy) {
  if (policy === "RUNTIME") {
    const storedId = await storedRuntimeTabId();
    if (Number.isInteger(storedId)) {
      try {
        const tab = await chrome.tabs.get(storedId);
        if (isChatGPTUrl(tab?.url || "")) {
          return {
            tab,
            source: "stored_runtime_tab",
            runtimeTabPresent: true,
            candidateCount: 1,
            selectionState: "selected"
          };
        }
      } catch {}
    }
    return {
      tab: null,
      source: null,
      runtimeTabPresent: false,
      candidateCount: 0,
      selectionState: "runtime_tab_unavailable"
    };
  }

  const tabs = await chrome.tabs.query({});
  const chatgptTabs = tabs.filter(
    (tab) => Number.isInteger(tab?.id) && isChatGPTUrl(tab?.url || "")
  );
  const active = chatgptTabs.filter((tab) => tab?.active === true);
  if (active.length === 1) {
    return {
      tab: active[0],
      source: "unique_active_chatgpt_tab",
      runtimeTabPresent: false,
      candidateCount: chatgptTabs.length,
      selectionState: "selected"
    };
  }

  if (active.length > 1 && chrome.windows?.getLastFocused) {
    try {
      const lastFocused = await chrome.windows.getLastFocused();
      const candidates = active.filter(
        (tab) => tab?.windowId === lastFocused?.id
      );
      if (candidates.length === 1) {
        return {
          tab: candidates[0],
          source: "last_focused_window_active_chatgpt_tab",
          runtimeTabPresent: false,
          candidateCount: chatgptTabs.length,
          selectionState: "selected"
        };
      }
    } catch {}
  }

  return {
    tab: null,
    source: null,
    runtimeTabPresent: false,
    candidateCount: chatgptTabs.length,
    selectionState: chatgptTabs.length === 0
      ? "no_existing_chatgpt_tab"
      : "ambiguous_active_chatgpt_tabs"
  };
}

async function _pr172CharacterizeReasoningOptions(message) {
  const policy = _pr172TargetPolicy(message?.targetPolicy);
  const selection = await _pr172ResolveDiagnosticTab(policy);
  if (!selection.tab || !Number.isInteger(selection.tab.id)) {
    return {
      diagnosticOnly: true,
      targetPolicy: policy,
      diagnosticTabPresent: false,
      diagnosticTabSource: selection.source,
      diagnosticTabSelectionState: selection.selectionState,
      chatgptTabCandidateCount: selection.candidateCount,
      runtimeTabPresent: selection.runtimeTabPresent === true,
      tabWasActive: null,
      documentVisibilityState: null,
      documentHidden: null,
      composerPresent: false,
      pickerControl: null,
      pickerControlCandidateCount: 0,
      surfaceCount: 0,
      surfaces: [],
      surfaceActionableCount: 0,
      surfaceActionables: [],
      optionCandidateCount: 0,
      optionCountsByMode: {},
      options: [],
      writePerformed: false,
      textInsertionPerformed: false,
      focusPerformed: false,
      clickPerformed: false,
      optionSelectionAttempted: false,
      submitAttempted: false,
      navigationPerformed: false,
      tabCreated: false,
      tabActivated: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      rawDomExported: false,
      composerTextExported: false,
      debuggerAttachedAfter: null
    };
  }

  const tabId = selection.tab.id;
  const debuggee = { tabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let snapshot = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr172ReasoningOptionSurfaceExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    snapshot = result?.result?.value;
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === tabId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
  }

  if (!snapshot || typeof snapshot !== "object") {
    throw new Error("PR17_2_REASONING_OPTION_SNAPSHOT_MISSING");
  }

  return {
    diagnosticOnly: true,
    targetPolicy: policy,
    diagnosticTabPresent: true,
    diagnosticTabSource: selection.source,
    diagnosticTabSelectionState: selection.selectionState,
    chatgptTabCandidateCount: selection.candidateCount,
    runtimeTabPresent: selection.runtimeTabPresent === true,
    tabWasActive: selection.tab.active === true,
    documentVisibilityState: snapshot.documentVisibilityState || null,
    documentHidden: snapshot.documentHidden === true,
    composerPresent: snapshot.composerPresent === true,
    pickerControl: snapshot.pickerControl || null,
    pickerControlCandidateCount:
      Number(snapshot.pickerControlCandidateCount) || 0,
    surfaceCount: Number(snapshot.surfaceCount) || 0,
    surfaces: Array.isArray(snapshot.surfaces) ? snapshot.surfaces.slice(0, 12) : [],
    surfaceActionableCount: Number(snapshot.surfaceActionableCount) || 0,
    surfaceActionables: Array.isArray(snapshot.surfaceActionables)
      ? snapshot.surfaceActionables.slice(0, 48)
      : [],
    optionCandidateCount: Number(snapshot.optionCandidateCount) || 0,
    optionCountsByMode:
      snapshot.optionCountsByMode && typeof snapshot.optionCountsByMode === "object"
        ? snapshot.optionCountsByMode
        : {},
    options: Array.isArray(snapshot.options) ? snapshot.options.slice(0, 32) : [],
    writePerformed: false,
    textInsertionPerformed: false,
    focusPerformed: false,
    clickPerformed: false,
    optionSelectionAttempted: false,
    submitAttempted: false,
    navigationPerformed: false,
    tabCreated: false,
    tabActivated: false,
    automaticWriteRetry: false,
    fallbackTransport: null,
    rawDomExported: false,
    composerTextExported: false,
    debuggerAttachedAfter
  };
}


function _pr172BackgroundDomTriggerClickExpression(expectedMode) {
  return `(() => {
    const expectedMode=${JSON.stringify(expectedMode)};
    const normalize=(value)=>String(value||'').trim().toLowerCase().replace(/[\\s_\\-]+/g,' ');
    const effort=(value)=>{
      const text=normalize(value);
      if(!text) return null;
      if(/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) return 'INSTANT';
      if(/(^|\\b)(medium|средний)(\\b|$)/.test(text)) return 'MEDIUM';
      if(/(^|\\b)(high|высокий)(\\b|$)/.test(text)) return 'HIGH';
      return null;
    };
    const visible=(el)=>{
      if(!(el instanceof Element)) return false;
      const r=el.getBoundingClientRect();
      if(r.width<=0||r.height<=0) return false;
      const s=getComputedStyle(el);
      return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';
    };
    const historicalComposer=[
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ].map((selector)=>document.querySelector(selector))
      .find((element)=>element&&visible(element));
    const semanticCandidates=historicalComposer?[]:Array.from(
      document.querySelectorAll(
        '[contenteditable="true"][role="textbox"][aria-multiline="true"]'
      )
    ).filter((candidate)=>
      visible(candidate)&&candidate.closest('main')&&candidate.closest('form')
    );
    const composer=historicalComposer||
      (semanticCandidates.length===1?semanticCandidates[0]:null);
    if(!composer) return {clicked:false,reason:'composer_missing',candidateCount:0};
    const cr=composer.getBoundingClientRect();
    const candidates=[];
    for(const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
      const modes=Array.from(new Set([
        el.innerText,el.getAttribute('aria-label'),el.getAttribute('title')
      ].map(effort).filter(Boolean)));
      if(modes.length!==1) continue;
      const r=el.getBoundingClientRect();
      const dx=Math.max(0,Math.max(cr.left-r.right,r.left-cr.right));
      const dy=Math.max(0,Math.max(cr.top-r.bottom,r.top-cr.bottom));
      const distance=Math.hypot(dx,dy);
      if(distance<=800) candidates.push({el,mode:modes[0],distance});
    }
    candidates.sort((a,b)=>a.distance-b.distance);
    if(candidates.length!==1) return {
      clicked:false,
      reason:candidates.length?'trigger_ambiguous':'trigger_missing',
      candidateCount:candidates.length
    };
    const candidate=candidates[0];
    if(candidate.mode!==expectedMode) return {
      clicked:false,reason:'trigger_mode_mismatch',candidateCount:1,mode:candidate.mode
    };
    const target=candidate.el;
    const disabled=Boolean(
      target.disabled===true||
      target.getAttribute('aria-disabled')==='true'
    );
    const pointerEventsEnabled=getComputedStyle(target).pointerEvents!=='none';
    if(disabled||!pointerEventsEnabled) return {
      clicked:false,reason:'trigger_not_actionable',candidateCount:1,mode:candidate.mode
    };
    const openBefore=
      target.getAttribute('aria-expanded')==='true'||
      normalize(target.getAttribute('data-state'))==='open';
    target.click();
    return {
      clicked:true,reason:null,candidateCount:1,mode:candidate.mode,openBefore
    };
  })()`;
}

async function _pr172BackgroundDomTriggerClick(debuggee, expectedMode) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr172BackgroundDomTriggerClickExpression(expectedMode),
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object"
    ? value
    : {clicked:false, reason:"background_dom_trigger_probe_failed", candidateCount:0};
}

async function _pr172BackgroundResolvedSliderSnapshot(debuggee, action = "snapshot") {
  const primary = await _pr88InstantEffortSliderSnapshot(debuggee, action);
  if (primary?.found === true) return primary;
  if (
    primary?.reason !== "quick_picker_not_open" &&
    primary?.reason !== "composer_missing"
  ) {
    return primary;
  }
  return _pr88InstantEffortRelaxedSliderSnapshot(debuggee, action);
}


async function _pr172WaitForSliderSnapshot(debuggee, expectedMode, timeoutMs = 3000) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr172BackgroundResolvedSliderSnapshot(debuggee, "snapshot");
    if (
      last?.found === true &&
      last?.candidateCount === 1 &&
      last?.min === 0 &&
      last?.max === 2 &&
      last?.stepCount === 3 &&
      last?.currentMode === expectedMode
    ) {
      return last;
    }
    await sleep(100);
  }
  return last || {
    found: false,
    reason: "background_slider_timeout",
    candidateCount: 0
  };
}

async function _pr172CharacterizeBackgroundSliderFocus() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    return {
      diagnosticOnly: true,
      backgroundFocusCharacterization: true,
      runtimeTabPresent: false,
      tabWasActive: null,
      documentVisibleBefore: null,
      selectedModeBefore: null,
      selectedModeBeforeProven: false,
      pickerFound: false,
      pickerCandidateCount: 0,
      uiTriggerClickPerformed: false,
      sliderFound: false,
      sliderCandidateCount: 0,
      sliderMin: null,
      sliderMax: null,
      sliderNowBefore: null,
      sliderFocusAttempted: false,
      sliderFocusProven: false,
      sliderNowAfterFocus: null,
      selectedModeAfterFocus: null,
      selectedModeAfterFocusProven: false,
      selectedModeUnchanged: false,
      uiTriggerRestoreAttempted: false,
      uiTriggerRestoreProven: false,
      tabActivated: false,
      reasoningValueMutationAttempted: false,
      keyDispatchPerformed: false,
      mouseDispatchPerformed: false,
      conversationWriteAttempted: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(storedId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR17_2_BACKGROUND_FOCUS_RUNTIME_TAB_INVALID");
  }
  if (tab?.active === true) {
    throw new Error("PR17_2_BACKGROUND_FOCUS_REQUIRES_INACTIVE_RUNTIME_TAB");
  }

  const debuggee = { tabId: storedId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let openedByProbe = false;
  let selectedModeBefore = null;
  let selectedModeBeforeProven = false;
  let uiTriggerRestoreAttempted = false;
  let uiTriggerRestoreProven = false;
  let result = null;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");

    const visibility = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression:
        "(() => ({visible: document.visibilityState === 'visible' && document.hidden !== true}))()",
      returnByValue: true,
      awaitPromise: true
    });
    const documentVisibleBefore = visibility?.result?.value?.visible === true;

    const before = await _pr88InstantSelectedModeSnapshot(debuggee);
    selectedModeBefore = typeof before?.selectedMode === "string"
      ? before.selectedMode
      : null;
    selectedModeBeforeProven = before?.selectedModeProven === true;
    if (!selectedModeBeforeProven || selectedModeBefore === null) {
      throw new Error("PR17_2_BACKGROUND_FOCUS_INITIAL_MODE_NOT_PROVEN");
    }

    const picker = await _pr88SelectionPoint(debuggee, "picker");
    const pickerFound = (
      picker?.found === true &&
      picker?.candidateCount === 1 &&
      picker?.mode === selectedModeBefore
    );

    let slider = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "snapshot"
    );
    if (slider?.found !== true) {
      if (!pickerFound) {
        throw new Error(
          `PR17_2_BACKGROUND_FOCUS_PICKER_NOT_PROVEN:${picker?.reason || "unknown"}`
        );
      }
      const opened = await _pr172BackgroundDomTriggerClick(
        debuggee,
        selectedModeBefore
      );
      if (
        opened?.clicked !== true ||
        opened?.candidateCount !== 1 ||
        opened?.mode !== selectedModeBefore
      ) {
        throw new Error(
          `PR17_2_BACKGROUND_FOCUS_TRIGGER_CLICK_NOT_PROVEN:${opened?.reason || "unknown"}`
        );
      }
      openedByProbe = opened?.openBefore !== true;
      slider = await _pr172WaitForSliderSnapshot(
        debuggee,
        selectedModeBefore,
        3000
      );
    }

    const sliderFound = (
      slider?.found === true &&
      slider?.candidateCount === 1 &&
      slider?.min === 0 &&
      slider?.max === 2 &&
      slider?.stepCount === 3 &&
      slider?.currentMode === selectedModeBefore
    );
    if (!sliderFound) {
      throw new Error(
        `PR17_2_BACKGROUND_FOCUS_SLIDER_NOT_PROVEN:${slider?.reason || "unknown"}`
      );
    }

    const focused = await _pr172BackgroundResolvedSliderSnapshot(
      debuggee,
      "focus"
    );
    const after = await _pr88InstantSelectedModeSnapshot(debuggee);
    const selectedModeAfterFocus =
      typeof after?.selectedMode === "string" ? after.selectedMode : null;
    const selectedModeAfterFocusProven = after?.selectedModeProven === true;

    result = {
      diagnosticOnly: true,
      backgroundFocusCharacterization: true,
      runtimeTabPresent: true,
      tabWasActive: false,
      documentVisibleBefore,
      selectedModeBefore,
      selectedModeBeforeProven,
      pickerFound,
      pickerCandidateCount: Number(picker?.candidateCount) || 0,
      uiTriggerClickPerformed: openedByProbe,
      sliderFound,
      sliderCandidateCount: Number(slider?.candidateCount) || 0,
      sliderMin: Number.isFinite(slider?.min) ? slider.min : null,
      sliderMax: Number.isFinite(slider?.max) ? slider.max : null,
      sliderNowBefore: Number.isFinite(slider?.now) ? slider.now : null,
      sliderFocusAttempted: true,
      sliderFocusProven: focused?.focusProven === true,
      sliderNowAfterFocus: Number.isFinite(focused?.now) ? focused.now : null,
      selectedModeAfterFocus,
      selectedModeAfterFocusProven,
      selectedModeUnchanged: (
        selectedModeAfterFocusProven &&
        selectedModeAfterFocus === selectedModeBefore &&
        Number.isFinite(focused?.now) &&
        focused.now === slider.now
      ),
      tabActivated: false,
      reasoningValueMutationAttempted: false,
      keyDispatchPerformed: false,
      mouseDispatchPerformed: false,
      conversationWriteAttempted: false
    };
  } finally {
    if (attached && openedByProbe && selectedModeBeforeProven) {
      uiTriggerRestoreAttempted = true;
      try {
        const restored = await _pr88InstantEffortDomTriggerClick(
          debuggee,
          selectedModeBefore
        );
        uiTriggerRestoreProven = restored?.clicked === true;
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
    throw new Error("PR17_2_BACKGROUND_FOCUS_RESULT_MISSING");
  }
  return result;
}

function _pr172ReasoningOptionDiagnosticMatches(message) {
  return (
    message?.characterizeReasoningOptionSurface === true ||
    message?.characterizeBackgroundReasoningSliderFocus === true
  );
}

async function _pr172HandleReasoningOptionDiagnostic(message) {
  _pr172RejectWriteBearingMessage(message);
  if (message?.characterizeBackgroundReasoningSliderFocus === true) {
    return _pr172CharacterizeBackgroundSliderFocus();
  }
  return _pr172CharacterizeReasoningOptions(message);
}

registerNativeTurnDiagnosticHandler(
  "reasoning-option-characterization",
  _pr172ReasoningOptionDiagnosticMatches,
  _pr172HandleReasoningOptionDiagnostic
);
