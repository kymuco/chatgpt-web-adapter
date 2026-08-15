importScripts("service_worker_temporary_chat_ax_semantics.js");

// PR8.7 live characterization #3:
// Current ChatGPT does not expose Temporary mode through DOM selected attrs or
// AX pressed/checked/selected state. Characterize the documented active-mode UI
// through bounded page-level semantic notice signals while keeping raw text,
// DOM, accessible names, and product payloads browser-local.
//
// PR8.7 live evidence later showed that a post-turn Temporary-looking document
// title can coexist with a conversation that is visible in ordinary history.
// Therefore title/URL/notice observations are UI mode markers only. They MUST
// NOT be promoted into selected-state proof or product Temporary semantics.

const _pr87SemanticPriorTemporaryControlSnapshot = _pr87TemporaryControlSnapshot;
const _pr87SemanticPriorClickPoint = _pr87ClickPoint;

function _pr87SemanticNoticeExpression() {
  return `(() => {
    const normalize = (value) => typeof value === 'string'
      ? value.trim().toLowerCase().replace(/\\s+/g, ' ')
      : '';

    const categoryPatterns = {
      temporary: ['temporary', 'временн'],
      history: ['history', 'истори'],
      memory: ['memory', 'memories', 'памят'],
      training: ['training', 'train our', 'improve our models', 'обуч', 'улучшать модели'],
      saved: ['not saved', "won't be saved", 'не сохраня', 'сохран'],
      privacy: ['privacy', 'private', 'приват', 'конфиденц']
    };

    const categoriesFor = (text) => {
      const normalized = normalize(text);
      if (!normalized) return [];
      return Object.entries(categoryPatterns)
        .filter(([, patterns]) => patterns.some((pattern) => normalized.includes(pattern)))
        .map(([name]) => name);
    };

    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };

    const isTooltipRelated = (element) => {
      if (!(element instanceof Element)) return false;
      return Boolean(element.closest('[role="tooltip"],[data-radix-popper-content-wrapper]'));
    };

    const isActionControl = (element) => {
      if (!(element instanceof Element)) return false;
      const role = normalize(element.getAttribute('role'));
      return element.matches('button,[role="button"],[role="switch"],[role="checkbox"]') ||
        ['button', 'switch', 'checkbox'].includes(role);
    };

    const semanticCandidates = [];
    const root = document.querySelector('main') || document.body;
    if (root) {
      for (const element of Array.from(root.querySelectorAll('div,p,section,aside,span,[role="status"],[role="alert"],[role="note"]'))) {
        if (!isVisible(element) || isTooltipRelated(element) || isActionControl(element)) continue;
        const text = element.innerText || element.textContent || '';
        if (typeof text !== 'string' || text.length < 4 || text.length > 1200) continue;
        const categories = categoriesFor(text);
        const categorySet = new Set(categories);
        const semanticPair = (
          categorySet.has('temporary') &&
          ['history', 'memory', 'training', 'saved', 'privacy'].some((name) => categorySet.has(name))
        ) || (
          categorySet.has('history') &&
          ['memory', 'training', 'saved'].some((name) => categorySet.has(name))
        );
        if (!semanticPair) continue;

        const childHasSameSignal = Array.from(element.children || []).some((child) => {
          if (!isVisible(child) || isTooltipRelated(child) || isActionControl(child)) return false;
          const childCategories = new Set(categoriesFor(child.innerText || child.textContent || ''));
          return (
            childCategories.has('temporary') &&
            ['history', 'memory', 'training', 'saved', 'privacy'].some((name) => childCategories.has(name))
          ) || (
            childCategories.has('history') &&
            ['memory', 'training', 'saved'].some((name) => childCategories.has(name))
          );
        });
        if (childHasSameSignal) continue;

        const role = normalize(element.getAttribute('role')) || element.tagName.toLowerCase();
        semanticCandidates.push({ categories: Array.from(categorySet).sort(), role });
      }
    }

    const categoryUnion = Array.from(new Set(
      semanticCandidates.flatMap((item) => item.categories)
    )).sort();
    const roles = Array.from(new Set(
      semanticCandidates
        .map((item) => item.role)
        .filter((value) => value && /^[a-z0-9_-]+$/.test(value))
    )).sort();

    const titleHasTemporary = (() => {
      const title = normalize(document.title);
      return title.includes('temporary') || title.includes('временн');
    })();
    const url = new URL(location.href);
    const urlHasTemporary = normalize(url.pathname + ' ' + url.search + ' ' + url.hash)
      .includes('temporary');

    const noticeObserved = semanticCandidates.length > 0;
    const modeMarkerObserved = Boolean(titleHasTemporary || urlHasTemporary || noticeObserved);
    const modeMarkerSignals = [];
    if (titleHasTemporary) modeMarkerSignals.push('semantic:document-title-temporary');
    if (urlHasTemporary) modeMarkerSignals.push('semantic:url-temporary');
    if (noticeObserved) modeMarkerSignals.push('semantic:product-notice');

    const stateSignals = [
      'semantic-candidate-count:' + semanticCandidates.length,
      ...categoryUnion.map((name) => 'semantic-category:' + name),
      ...roles.map((role) => 'semantic-role:' + role),
      'semantic-title-temporary:' + (titleHasTemporary ? 'true' : 'false'),
      'semantic-url-temporary:' + (urlHasTemporary ? 'true' : 'false')
    ];

    return {
      candidateCount: semanticCandidates.length,
      categories: categoryUnion,
      roles,
      titleHasTemporary,
      urlHasTemporary,
      noticeObserved,
      modeMarkerObserved,
      modeMarkerSignals,
      selectionProven: false,
      proofSignals: [],
      stateSignals
    };
  })()`;
}

async function _pr87SemanticNoticeSnapshot(debuggee) {
  try {
    const result = await _pr87RawSendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr87SemanticNoticeExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (value && typeof value === "object") return value;
  } catch {
    // Fall through to a bounded failure marker.
  }
  return {
    candidateCount: 0,
    categories: [],
    roles: [],
    titleHasTemporary: false,
    urlHasTemporary: false,
    noticeObserved: false,
    modeMarkerObserved: false,
    modeMarkerSignals: [],
    selectionProven: false,
    proofSignals: [],
    stateSignals: ["semantic-probe-failed"]
  };
}

_pr87ClickPoint = async function _pr87ClickPointWithTooltipDismissal(debuggee, point) {
  await _pr87SemanticPriorClickPoint(debuggee, point);
  try {
    await _pr87RawSendCommand(debuggee, "Input.dispatchMouseEvent", {
      type: "mouseMoved",
      x: 1,
      y: 1
    });
  } catch {
    // Pointer dismissal is characterization hygiene, not a write prerequisite.
  }
  await sleep(900);
};

_pr87TemporaryControlSnapshot = async function _pr87TemporaryControlSnapshotWithSemanticNotice(debuggee) {
  const base = await _pr87SemanticPriorTemporaryControlSnapshot(debuggee);
  const semantic = await _pr87SemanticNoticeSnapshot(debuggee);

  const semanticStateSignals = Array.isArray(semantic?.stateSignals)
    ? semantic.stateSignals.filter((value) => typeof value === "string")
    : [];
  if (base?.axSnapshot && Array.isArray(base.axSnapshot.stateSignals)) {
    base.axSnapshot.stateSignals = Array.from(new Set([
      ...base.axSnapshot.stateSignals,
      ...semanticStateSignals
    ])).sort();
  }

  const selected = typeof base?.selected === "boolean" ? base.selected : null;
  const proofSignals = Array.isArray(base?.proofSignals) ? [...base.proofSignals] : [];
  const stateSignals = Array.isArray(base?.stateSignals) ? [...base.stateSignals] : [];
  stateSignals.push(...semanticStateSignals);

  const modeMarkerSignals = Array.isArray(semantic?.modeMarkerSignals)
    ? semantic.modeMarkerSignals.filter((value) => typeof value === "string")
    : [];

  return {
    ...base,
    selected,
    proofSignals: Array.from(new Set(proofSignals)),
    stateSignals: Array.from(new Set(stateSignals)),
    modeMarkerObserved: semantic?.modeMarkerObserved === true,
    modeMarkerSignals: Array.from(new Set(modeMarkerSignals)),
    semanticSnapshot: semantic
  };
};
