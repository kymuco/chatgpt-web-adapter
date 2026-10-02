// PR17.1 branch-only no-write ChatGPT composer/submit drift characterization.
//
// This diagnostic exists only to characterize the current live ChatGPT composer
// subtree after a product UI rollout. It must not type, focus, click, submit,
// navigate, retry, or grant write authority. Preserve evidence in tests/docs and
// remove this diagnostic surface before production merge.

function _pr171RejectWriteBearingMessage(message) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.requiredModelMode != null
  ) {
    throw new Error("PR17_1_COMPOSER_SUBMIT_PROBE_MUST_BE_NO_WRITE");
  }
}

function _pr171ComposerSubmitSurfaceExpression() {
  return `(() => {
    const bounded = (value, max = 160) => {
      if (typeof value !== 'string') return null;
      const normalized = value.trim();
      return normalized ? normalized.slice(0, max) : null;
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
    const identity = (element) => {
      if (!(element instanceof Element)) return null;
      return {
        tagName: element.tagName.toLowerCase(),
        role: bounded(element.getAttribute('role')),
        dataTestid: bounded(element.getAttribute('data-testid')),
        ariaLabel: bounded(element.getAttribute('aria-label')),
        type: bounded(element.getAttribute('type')),
        id: bounded(element.id),
        contentEditable: bounded(element.getAttribute('contenteditable')),
        ariaMultiline: bounded(element.getAttribute('aria-multiline')),
        dataLexicalEditor: bounded(element.getAttribute('data-lexical-editor')),
        nearestMainPresent: Boolean(element.closest?.('main')),
        nearestFormPresent: Boolean(element.closest?.('form'))
      };
    };

    const legacyComposerSelectors = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ];
    const legacySubmitSelectors = [
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Отправить сообщение"]'
    ];

    const composerElements = [];
    const seenComposers = new Set();
    const addComposer = (element, source) => {
      if (!(element instanceof Element) || seenComposers.has(element) || !visible(element)) return;
      seenComposers.add(element);
      composerElements.push({ element, source });
    };

    for (const selector of legacyComposerSelectors) {
      for (const element of document.querySelectorAll(selector)) addComposer(element, selector);
    }
    for (const element of document.querySelectorAll(
      '[role="textbox"], textarea, [contenteditable="true"]'
    )) {
      addComposer(element, 'semantic-fallback');
    }

    const selectedComposer =
      composerElements.find((item) => item.source !== 'semantic-fallback')?.element ||
      composerElements.at(-1)?.element ||
      null;

    const nearestForm = selectedComposer?.closest?.('form') || null;
    let scope = nearestForm;
    let scopeKind = nearestForm ? 'form' : null;
    if (!scope && selectedComposer instanceof Element) {
      let cursor = selectedComposer.parentElement;
      for (let depth = 0; cursor && depth < 7; depth += 1, cursor = cursor.parentElement) {
        const controlCount = cursor.querySelectorAll(
          'button, [role="button"], input[type="submit"]'
        ).length;
        if (controlCount > 0) {
          scope = cursor;
          scopeKind = 'ancestor-with-controls';
          break;
        }
      }
    }

    const legacyMatch = (element) =>
      legacySubmitSelectors.find((selector) => {
        try { return element.matches(selector); } catch { return false; }
      }) || null;

    const controlSnapshot = (element) => {
      const rect = rectOf(element);
      const style = getComputedStyle(element);
      const centerHit = rect
        ? document.elementFromPoint(rect.centerX, rect.centerY)
        : null;
      return {
        ...identity(element),
        rect,
        disabled: element.disabled === true,
        ariaDisabled: bounded(element.getAttribute('aria-disabled')),
        pointerEvents: bounded(style.pointerEvents),
        legacySelector: legacyMatch(element),
        insideNearestForm: Boolean(nearestForm && nearestForm.contains(element)),
        insideDerivedScope: Boolean(scope && scope.contains(element)),
        centerHit: identity(centerHit),
        centerHitIsSelfOrDescendant: Boolean(
          centerHit && (centerHit === element || element.contains(centerHit))
        ),
        centerHitContainsControl: Boolean(
          centerHit instanceof Element && centerHit.contains(element)
        )
      };
    };

    const controlsRoot = scope || document;
    const scopedControls = Array.from(
      controlsRoot.querySelectorAll('button, [role="button"], input[type="submit"]')
    )
      .filter(visible)
      .slice(-48)
      .map(controlSnapshot);

    const legacyControls = [];
    const seenLegacyControls = new Set();
    for (const selector of legacySubmitSelectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (!visible(element) || seenLegacyControls.has(element)) continue;
        seenLegacyControls.add(element);
        legacyControls.push(controlSnapshot(element));
      }
    }

    const oldResolverSelected =
      legacyControls.find((item) => (
        item.disabled !== true &&
        item.ariaDisabled !== 'true' &&
        item.pointerEvents !== 'none'
      )) || null;

    return {
      composerCandidates: composerElements.slice(-16).map(({ element, source }) => ({
        ...identity(element),
        source,
        rect: rectOf(element),
        activeElement: document.activeElement === element
      })),
      selectedComposer: selectedComposer ? {
        ...identity(selectedComposer),
        rect: rectOf(selectedComposer),
        legacySelector: legacyComposerSelectors.find((selector) => {
          try { return selectedComposer.matches(selector); } catch { return false; }
        }) || null
      } : null,
      derivedScope: scope ? {
        kind: scopeKind,
        ...identity(scope),
        rect: rectOf(scope)
      } : null,
      scopedControls,
      legacyControls,
      oldResolverSelected,
      composerCandidateCount: composerElements.length,
      scopedControlCount: scopedControls.length,
      legacyControlCount: legacyControls.length
    };
  })()`;
}

async function _pr171ResolveDiagnosticTab() {
  const storedId = await storedRuntimeTabId();
  if (Number.isInteger(storedId)) {
    try {
      const storedTab = await chrome.tabs.get(storedId);
      if (isChatGPTUrl(storedTab?.url || '')) {
        return {
          tab: storedTab,
          runtimeTabPresent: true,
          diagnosticTabSource: 'stored_runtime_tab',
          chatgptTabCandidateCount: 1,
          selectionState: 'selected'
        };
      }
    } catch {
      // Stale stored id is not diagnostic authority; continue to read-only discovery.
    }
  }

  const tabs = await chrome.tabs.query({});
  const chatgptTabs = tabs.filter(
    (tab) => Number.isInteger(tab?.id) && isChatGPTUrl(tab?.url || '')
  );
  if (chatgptTabs.length === 1) {
    return {
      tab: chatgptTabs[0],
      runtimeTabPresent: false,
      diagnosticTabSource: 'unique_existing_chatgpt_tab',
      chatgptTabCandidateCount: 1,
      selectionState: 'selected'
    };
  }

  const activeChatgptTabs = chatgptTabs.filter((tab) => tab?.active === true);
  if (activeChatgptTabs.length === 1) {
    return {
      tab: activeChatgptTabs[0],
      runtimeTabPresent: false,
      diagnosticTabSource: 'unique_active_chatgpt_tab',
      chatgptTabCandidateCount: chatgptTabs.length,
      selectionState: 'selected'
    };
  }

  return {
    tab: null,
    runtimeTabPresent: false,
    diagnosticTabSource: null,
    chatgptTabCandidateCount: chatgptTabs.length,
    selectionState: chatgptTabs.length === 0
      ? 'no_existing_chatgpt_tab'
      : 'ambiguous_existing_chatgpt_tabs'
  };
}

async function _pr171CharacterizeComposerSubmitSurface() {
  const selection = await _pr171ResolveDiagnosticTab();
  if (!selection.tab || !Number.isInteger(selection.tab.id)) {
    return {
      diagnosticOnly: true,
      runtimeTabPresent: selection.runtimeTabPresent === true,
      diagnosticTabPresent: false,
      diagnosticTabSource: selection.diagnosticTabSource,
      diagnosticTabSelectionState: selection.selectionState,
      chatgptTabCandidateCount: selection.chatgptTabCandidateCount,
      composerCandidateCount: 0,
      scopedControlCount: 0,
      legacyControlCount: 0,
      composerCandidates: [],
      selectedComposer: null,
      derivedScope: null,
      scopedControls: [],
      legacyControls: [],
      oldResolverSelected: null,
      rawDomExported: false,
      composerTextExported: false,
      writePerformed: false,
      textInsertionPerformed: false,
      focusPerformed: false,
      clickPerformed: false,
      submitAttempted: false,
      navigationPerformed: false,
      tabCreated: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      debuggerAttachedAfter: null
    };
  }

  const diagnosticTabId = selection.tab.id;
  const debuggee = { tabId: diagnosticTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let snapshot = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, 'Runtime.enable');
    const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
      expression: _pr171ComposerSubmitSurfaceExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (!value || typeof value !== 'object') {
      throw new Error('PR17_1_COMPOSER_SUBMIT_RESULT_MISSING');
    }
    snapshot = value;
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === diagnosticTabId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
  }

  if (!snapshot) throw new Error('PR17_1_COMPOSER_SUBMIT_NO_SNAPSHOT');

  return {
    diagnosticOnly: true,
    runtimeTabPresent: selection.runtimeTabPresent === true,
    diagnosticTabPresent: true,
    diagnosticTabSource: selection.diagnosticTabSource,
    diagnosticTabSelectionState: selection.selectionState,
    chatgptTabCandidateCount: selection.chatgptTabCandidateCount,
    composerCandidateCount: Number(snapshot.composerCandidateCount) || 0,
    scopedControlCount: Number(snapshot.scopedControlCount) || 0,
    legacyControlCount: Number(snapshot.legacyControlCount) || 0,
    composerCandidates: Array.isArray(snapshot.composerCandidates)
      ? snapshot.composerCandidates.slice(0, 16)
      : [],
    selectedComposer: snapshot.selectedComposer || null,
    derivedScope: snapshot.derivedScope || null,
    scopedControls: Array.isArray(snapshot.scopedControls)
      ? snapshot.scopedControls.slice(0, 48)
      : [],
    legacyControls: Array.isArray(snapshot.legacyControls)
      ? snapshot.legacyControls.slice(0, 16)
      : [],
    oldResolverSelected: snapshot.oldResolverSelected || null,
    rawDomExported: false,
    composerTextExported: false,
    writePerformed: false,
    textInsertionPerformed: false,
    focusPerformed: false,
    clickPerformed: false,
    submitAttempted: false,
    navigationPerformed: false,
    tabCreated: false,
    automaticWriteRetry: false,
    fallbackTransport: null,
    debuggerAttachedAfter
  };
}

function _pr171ComposerSubmitDiagnosticMatches(message) {
  return message?.characterizeChatGPTComposerSubmitSurface === true;
}

async function _pr171HandleComposerSubmitDiagnostic(message) {
  _pr171RejectWriteBearingMessage(message);
  return _pr171CharacterizeComposerSubmitSurface();
}

registerNativeTurnDiagnosticHandler(
  "chatgpt-composer-submit-characterization",
  _pr171ComposerSubmitDiagnosticMatches,
  _pr171HandleComposerSubmitDiagnostic
);
