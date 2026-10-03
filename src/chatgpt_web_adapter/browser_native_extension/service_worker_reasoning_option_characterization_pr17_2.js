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

function _pr172ReasoningOptionDiagnosticMatches(message) {
  return message?.characterizeReasoningOptionSurface === true;
}

async function _pr172HandleReasoningOptionDiagnostic(message) {
  _pr172RejectWriteBearingMessage(message);
  return _pr172CharacterizeReasoningOptions(message);
}

registerNativeTurnDiagnosticHandler(
  "reasoning-option-characterization",
  _pr172ReasoningOptionDiagnosticMatches,
  _pr172HandleReasoningOptionDiagnostic
);
