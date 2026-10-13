// PR11.7 shared UI-drift compatibility helpers.
//
// This module owns no turn dispatch, submit action, Browser Authority, retry,
// navigation, or canonical-finality semantics. It only broadens bounded DOM
// discovery used by already-governed consumers when historical selectors fail.
// Generic contenteditable elements are accepted only with structural composer
// evidence; an arbitrary visible editor is never enough.

const PR117_UI_COMPAT_SCHEMA = 1;

function _pr117ComposerResolverSource() {
  return `() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        style.opacity !== '0';
    };
    const writable = (element) => {
      if (!(element instanceof Element)) return false;
      if (element.getAttribute('aria-disabled') === 'true') return false;
      if (element.disabled === true || element.readOnly === true) return false;
      if (element.hasAttribute('contenteditable') &&
          element.getAttribute('contenteditable') !== 'true') return false;
      return true;
    };
    const currentEmptyComposerEvidence = (element) => {
      if (element.getAttribute('contenteditable') !== 'true') return false;
      if (element.getAttribute('role') !== 'textbox') return false;
      if (element.getAttribute('aria-multiline') !== 'true') return false;
      if (!element.closest('main') || !element.closest('form')) return false;

      // Current ChatGPT can expose an empty composer before a Send control exists.
      // Accept that shape only when it is the unique visible+writable multiline
      // contenteditable textbox inside main+form. This stays locale-neutral and
      // fails closed when a second editor could be confused with the composer.
      const peers = Array.from(document.querySelectorAll(
        '[contenteditable="true"][role="textbox"][aria-multiline="true"]'
      )).filter((candidate) =>
        visible(candidate) &&
        writable(candidate) &&
        candidate.closest('main') &&
        candidate.closest('form')
      );
      return peers.length === 1 && peers[0] === element;
    };
    const structuralGenericEvidence = (element) => {
      if (element.closest('[data-testid*="composer"]')) return true;
      const testId = String(element.getAttribute('data-testid') || '').toLowerCase();
      if (testId.includes('composer') || testId.includes('prompt')) return true;
      if (currentEmptyComposerEvidence(element)) return true;

      const form = element.closest('form');
      if (!form) return false;
      const scopedSubmitControls = form.querySelectorAll(
        'button[type="submit"],button[data-testid*="send"],button[data-testid*="submit"]'
      );
      return scopedSubmitControls.length > 0;
    };
    const score = (element) => {
      let value = 0;
      if (element.id === 'prompt-textarea') value += 1000;
      if (element.getAttribute('data-lexical-editor') === 'true') value += 900;
      if (element.matches('textarea[placeholder]')) value += 800;
      if (element.getAttribute('contenteditable') === 'true') value += 500;
      if (element.getAttribute('role') === 'textbox') value += 120;
      if (element.getAttribute('aria-multiline') === 'true') value += 100;
      if (element.closest('form')) value += 120;
      if (element.closest('[data-testid*="composer"]')) value += 120;
      return value;
    };

    const selectors = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]',
      '[contenteditable="true"]'
    ];
    const seen = new Set();
    const candidates = [];
    let order = 0;
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (seen.has(element)) continue;
        seen.add(element);
        if (!visible(element) || !writable(element)) continue;
        const genericOnly = (
          element.getAttribute('contenteditable') === 'true' &&
          element.id !== 'prompt-textarea' &&
          element.getAttribute('data-lexical-editor') !== 'true'
        );
        if (genericOnly && !structuralGenericEvidence(element)) continue;
        candidates.push({ element, score: score(element), order });
        order += 1;
      }
    }
    candidates.sort((left, right) =>
      right.score - left.score || right.order - left.order
    );
    return candidates[0]?.element || null;
  }`;
}

function _pr117ComposerReadinessExpression() {
  const resolver = _pr117ComposerResolverSource();
  return `(() => {
    const resolveComposer = ${resolver};
    const composer = resolveComposer();
    if (!composer) return { ready: false, reason: 'composer_missing' };

    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        style.opacity !== '0';
    };
    const stopSelectors = [
      '[data-testid="stop-button"]',
      '[data-testid="stop-generating-button"]',
      'button[aria-label*="Stop generating"]',
      'button[aria-label*="Остановить"]'
    ];
    const stopVisible = stopSelectors.some((selector) =>
      visible(document.querySelector(selector))
    );
    const busy = composer.getAttribute('aria-busy') === 'true' ||
      composer.getAttribute('contenteditable') === 'false' ||
      composer.disabled === true;
    return {
      ready: !stopVisible && !busy,
      reason: stopVisible
        ? 'generation_control_visible'
        : (busy ? 'composer_busy' : 'ready')
    };
  })()`;
}

async function _pr117QueryComposerReadiness(debuggee) {
  try {
    const historical = await _cwaBaseQueryComposerReadiness(debuggee);
    if (historical?.reason !== 'composer_missing') return historical;
  } catch {
    // Fall through to the bounded structural compatibility probe.
  }

  const result = await sendCommand(debuggee, 'Runtime.evaluate', {
    expression: _pr117ComposerReadinessExpression(),
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value || { ready: false, reason: 'unknown' };
}

async function _pr117LocateAndFocusComposer(debuggee) {
  try {
    return await locateAndFocusComposer(debuggee);
  } catch {
    // Historical AX/selector discovery failed; use the structural fallback only.
  }

  const resolver = _pr117ComposerResolverSource();
  const result = await sendCommand(debuggee, 'Runtime.evaluate', {
    expression: `(() => {
      const resolveComposer = ${resolver};
      const composer = resolveComposer();
      if (!composer) return false;
      composer.focus();
      return true;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  if (!result?.result?.value) throw new Error('CHATGPT_COMPOSER_NOT_FOUND');
  return 'pr11_7_structural_dom_fallback';
}

function _pr117RichComposerFocusExpression() {
  const resolver = _pr117ComposerResolverSource();
  return `(() => {
    const resolveComposer = ${resolver};
    const composer = resolveComposer();
    if (!composer) return false;
    composer.focus();
    return document.activeElement === composer;
  })()`;
}

async function _pr117FocusRichComposerWithProof(debuggee) {
  const result = await sendCommand(debuggee, 'Runtime.evaluate', {
    expression: _pr117RichComposerFocusExpression(),
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.result?.value !== true) {
    throw new Error('CWA_RICH_COMPOSER_FOCUS_NOT_PROVEN');
  }
  return 'pr11_7_structural_composer_focus_proven';
}

// Read-only observation: a rich editor may encode line breaks as distinct
// Lexical paragraphs. textContent concatenates paragraphs; innerText may add
// extra breaks. Prove exact logical text using a restricted DOM grammar.
function _pr117RichComposerTextObservationExpression(text) {
  const resolver = _pr117ComposerResolverSource();
  const expected = JSON.stringify(text);
  return `(() => {
    const resolveComposer = ${resolver};
    const composer = resolveComposer();
    const expected = ${expected};
    const comparable = (value) =>
      typeof value === 'string' ? value.replace(/\r\n/g, '\n') : null;
    const exact = (value) =>
      comparable(value) !== null && comparable(value) === comparable(expected);
    if (!composer) {
      return { passed: false, composerFound: false, focusMatches: false,
        directExact: false, renderedExact: false, structuredExact: false,
        structureSupported: false, paragraphCount: 0 };
    }
    const raw = typeof composer.textContent === 'string'
      ? composer.textContent : null;
    const rendered = typeof composer.innerText === 'string'
      ? composer.innerText : null;
    let structureSupported = true;
    const blocks = new Set(['P', 'DIV']);
    const inline = new Set(['SPAN', 'STRONG', 'EM', 'B', 'I', 'U', 'A']);
    const visit = (node) => {
      if (node?.nodeType === 3) return node.nodeValue ?? '';
      if (node?.nodeType !== 1) {
        structureSupported = false;
        return '';
      }
      const tag = String(node.tagName || '').toUpperCase();
      if (tag === 'BR') return '\n';
      if (!blocks.has(tag) && !inline.has(tag)) {
        structureSupported = false;
        return '';
      }
      const nodes = Array.from(node.childNodes || []);
      // Lexical empty paragraphs use a placeholder <br>, not a newline.
      if (blocks.has(tag) && nodes.length === 1 &&
          nodes[0]?.nodeType === 1 &&
          String(nodes[0].tagName || '').toUpperCase() === 'BR') {
        return '';
      }
      return childrenText(nodes);
    };
    const childrenText = (children) => {
      const nodes = Array.from(children || []);
      const count = nodes.filter((node) =>
        node?.nodeType === 1 &&
        blocks.has(String(node.tagName || '').toUpperCase())
      ).length;
      // Mixed block/inline siblings are ambiguous: never invent breaks.
      if (count && count !== nodes.length) {
        structureSupported = false;
        return '';
      }
      return nodes.map((node) => visit(node)).join(count ? '\n' : '');
    };
    const topLevelNodes = Array.from(composer.childNodes || []);
    if (!topLevelNodes.length) structureSupported = false;
    const structural = structureSupported ? childrenText(topLevelNodes) : '';
    const directExact = exact(raw);
    const renderedExact = exact(rendered);
    const structuredExact = structureSupported && exact(structural);
    return {
      passed: directExact || renderedExact || structuredExact,
      composerFound: true,
      focusMatches: document.activeElement === composer,
      directExact,
      renderedExact,
      structuredExact,
      structureSupported,
      paragraphCount: topLevelNodes.filter((node) =>
        node?.nodeType === 1 &&
        blocks.has(String(node.tagName || '').toUpperCase())
      ).length
    };
  })`;
}

function _pr117RichComposerTextProofExpression(text) {
  // Focus was proven immediately before Input.insertText. Losing focus after
  // insertion must not invalidate exact content proof or permit modified text.
  return `(${_pr117RichComposerTextObservationExpression(text)}).passed`;
}

async function _pr117RequireRichInsertedTextProof(debuggee, text) {
  const result = await sendCommand(debuggee, 'Runtime.evaluate', {
    expression: _pr117RichComposerTextProofExpression(text),
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.result?.value !== true) {
    // Fail before delegated protected submit: do not guess or reinsert text.
    throw new Error('CWA_RICH_COMPOSER_TEXT_NOT_INSERTED');
  }
  return true;
}

function _pr117StructuralSubmitButtonResolverSource() {
  // Shared DOM authority for the ordinary-text discovery point and rich-input's
  // atomic page-owned click. The discovery selector is NOT a CSS selector.
  const resolver = _pr117ComposerResolverSource();
  return `() => {
    const resolveComposer = ${resolver};
    const composer = resolveComposer();
    if (!composer) return null;
    const scope = composer.closest('form') ||
      composer.closest('[data-testid*="composer"]');
    if (!scope) return null;
    const usable = (button) => {
      if (!(button instanceof Element)) return false;
      const rect = button.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(button);
      const disabled = button.disabled === true ||
        button.getAttribute('aria-disabled') === 'true';
      return !disabled &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        style.opacity !== '0' &&
        style.pointerEvents !== 'none';
    };
    const all = Array.from(scope.querySelectorAll(
      'button[type="submit"],button[data-testid*="send"],button[data-testid*="submit"]'
    )).filter(usable);
    const semantic = all.filter((button) => {
      const testId = String(button.getAttribute('data-testid') || '').toLowerCase();
      return testId.includes('send') || testId.includes('submit');
    });
    if (semantic.length > 1) return null;
    const candidates = semantic.length === 1
      ? semantic
      : all.filter((button) => button.getAttribute('type') === 'submit');
    if (candidates.length !== 1) return null;
    return candidates[0];
  }`;
}

function _pr117StructuralSubmitPointExpression() {
  const buttonResolver = _pr117StructuralSubmitButtonResolverSource();
  return `(() => {
    const resolveButton = ${buttonResolver};
    const button = resolveButton();
    if (!button) return null;
    const rect = button.getBoundingClientRect();
    return {
      selector: 'pr11_7_structural_submit_control',
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2
    };
  })()`;
}

async function _pr117QuerySendButtonPoint(debuggee) {
  try {
    const historical = await querySendButtonPoint(debuggee);
    if (historical && Number.isFinite(historical.x) && Number.isFinite(historical.y)) {
      return historical;
    }
  } catch {
    // Fall through to the bounded structural submit-control probe.
  }

  const result = await sendCommand(debuggee, 'Runtime.evaluate', {
    expression: _pr117StructuralSubmitPointExpression(),
    returnByValue: true,
    awaitPromise: true
  });
  const point = result?.result?.value || null;
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
  return point;
}

async function _pr117WaitForSendButtonPoint(
  debuggee,
  timeoutMs = DEFAULT_SUBMIT_READY_TIMEOUT_MS
) {
  const startedAt = performance.now();
  while (elapsedMs(startedAt) < timeoutMs) {
    const point = await _pr117QuerySendButtonPoint(debuggee);
    if (point) return point;
    await sleep(100);
  }
  throw new Error('CHATGPT_SEND_BUTTON_NOT_READY');
}

// The historical waitForComposerReady() loop resolves queryComposerReadiness at
// call time. Install the compatibility query at that shared discovery seam so
// initial write preflight, completion readiness, and legacy consumers all receive
// the same bounded structural fallback. This changes observation only; it does
// not submit, type, navigate, retry, or grant write authority.
async function queryComposerReadiness(debuggee) {
  return _pr117QueryComposerReadiness(debuggee);
}
