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
    const structuralGenericEvidence = (element) => {
      if (element.closest('[data-testid*="composer"]')) return true;
      const testId = String(element.getAttribute('data-testid') || '').toLowerCase();
      if (testId.includes('composer') || testId.includes('prompt')) return true;

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
    const historical = await queryComposerReadiness(debuggee);
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

function _pr117StructuralSubmitPointExpression() {
  const resolver = _pr117ComposerResolverSource();
  return `(() => {
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
    const button = candidates[0];
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
