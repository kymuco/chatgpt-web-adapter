// PR8.8 model-picker trigger identity, click-actuation, and per-poll menu timeline.
//
// Loaded after the in-failure popup-subtree layer. This layer adds no new product
// mutation and does not broaden the Instant selector. It observes the existing
// picker point/click and existing 100 ms Instant-option polling loop, persists
// bounded evidence under the same private Browser Authority lease, and rethrows
// the exact original error object unchanged.
//
// No prompt/response text, raw DOM/HTML, raw URL, cookies, auth material, or
// response bodies are exported. No retry, navigation, tab create/close, debugger
// attach, prompt insertion, or submit is introduced.

const PR88_PICKER_TRIGGER_TIMELINE_SCHEMA_VERSION = 1;
const PR88_PICKER_TRIGGER_TIMELINE_STORAGE_KEY =
  "browserAuthorityLastPickerTriggerTimelineV1";
const PR88_PICKER_TRIGGER_MAX_SAMPLES = 96;

const _pr88TriggerPriorExecuteNativeTurn = executeNativeTurn;
const _pr88TriggerPriorSelectionPoint = _pr88SelectionPoint;
const _pr88TriggerPriorRawClick = _pr88SelectionRawClick;
const _pr88TriggerPriorLocateAndFocusComposer = locateAndFocusComposer;

let _pr88TriggerTimelineContext = null;

function _pr88TriggerLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88TriggerSafeInt(value) {
  return Number.isFinite(value) ? Math.max(0, Math.round(Number(value))) : null;
}

function _pr88TriggerSamePoint(a, b) {
  return (
    Number.isFinite(a?.x) &&
    Number.isFinite(a?.y) &&
    Number.isFinite(b?.x) &&
    Number.isFinite(b?.y) &&
    Math.abs(Number(a.x) - Number(b.x)) <= 1 &&
    Math.abs(Number(a.y) - Number(b.y)) <= 1
  );
}

function _pr88TriggerIdentityExpression(point, pickerMode) {
  const safePoint = {
    x: Number.isFinite(point?.x) ? Number(point.x) : null,
    y: Number.isFinite(point?.y) ? Number(point.y) : null
  };
  const safeMode = typeof pickerMode === "string" ? pickerMode : null;
  return `(() => {
    const point = ${JSON.stringify(safePoint)};
    const expectedMode = ${JSON.stringify(safeMode)};
    const normalize = (value) =>
      String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const modes = (value) => {
      const text = normalize(value);
      if (!text) return [];
      const out = [];
      if (/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) out.push('INSTANT');
      if (/(^|\\b)(medium|средний)(\\b|$)/.test(text) || text.includes('thinking standard')) out.push('MEDIUM');
      if (text.includes('extra high') || text.includes('очень высокий') || text.includes('thinking heavy')) out.push('EXTRA_HIGH');
      else if (/(^|\\b)(high|высокий)(\\b|$)/.test(text) || text.includes('thinking extended')) out.push('HIGH');
      if (text.includes('pro standard')) out.push('PRO_STANDARD');
      if (text.includes('pro extended')) out.push('PRO_EXTENDED');
      if (text === 'thinking') out.push('REASONING_OTHER');
      if (text === 'pro') out.push('PRO_OTHER');
      return Array.from(new Set(out));
    };
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return false;
      const s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
    };
    const rect = (el) => {
      const r = el.getBoundingClientRect();
      return {x: Math.round(r.left), y: Math.round(r.top), width: Math.round(r.width), height: Math.round(r.height)};
    };
    const center = (el) => {
      const r = el.getBoundingClientRect();
      return {x: r.left + r.width / 2, y: r.top + r.height / 2};
    };
    const directModes = (el) =>
      Array.from(new Set([
        el.innerText,
        el.getAttribute('aria-label'),
        el.getAttribute('title')
      ].flatMap(modes)));
    const subtreeModes = (el) =>
      Array.from(new Set([
        ...modes(typeof el.innerText === 'string' ? el.innerText.slice(0, 320) : ''),
        ...modes(el.textContent ? String(el.textContent).slice(0, 320) : '')
      ]));
    const boundedState = (value) => {
      const text = normalize(value);
      return ['open','closed','selected','checked','unchecked','active','inactive','on','off'].includes(text) ? text : null;
    };
    const controlRecord = (el) => {
      if (!(el instanceof Element)) return null;
      const style = getComputedStyle(el);
      return {
        tag: el.tagName,
        role: el.getAttribute('role') || null,
        directModes: directModes(el),
        subtreeModes: subtreeModes(el),
        ariaHaspopup: el.getAttribute('aria-haspopup') || null,
        ariaExpanded: el.getAttribute('aria-expanded') || null,
        dataState: boundedState(el.getAttribute('data-state')),
        disabled: Boolean(el.disabled === true || el.getAttribute('aria-disabled') === 'true'),
        pointerEventsEnabled: style.pointerEvents !== 'none',
        childElementCount: el.children ? el.children.length : 0,
        rect: rect(el)
      };
    };

    let candidate = null;
    if (Number.isFinite(point.x) && Number.isFinite(point.y)) {
      let best = null;
      for (const control of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
        const found = directModes(control);
        if (found.length !== 1) continue;
        if (expectedMode && found[0] !== expectedMode) continue;
        const c = center(control);
        const distance = Math.hypot(c.x - point.x, c.y - point.y);
        if (best === null || distance < best.distance) best = {element: control, distance};
      }
      if (best && best.distance <= 24) candidate = best.element;
    }

    let trigger = null;
    let triggerHops = null;
    if (candidate) {
      let current = candidate;
      let hops = 0;
      while (current && hops <= 8) {
        const popup = normalize(current.getAttribute('aria-haspopup'));
        const expanded = current.getAttribute('aria-expanded');
        const state = boundedState(current.getAttribute('data-state'));
        if (popup === 'menu' || popup === 'listbox' || expanded !== null || state === 'open' || state === 'closed') {
          trigger = current;
          triggerHops = hops;
          break;
        }
        current = current.parentElement;
        hops += 1;
      }
    }

    const genericSurfaces = Array.from(document.querySelectorAll(
      '[role="menu"],[role="listbox"],[role="dialog"],[role="radiogroup"],[role="group"],[role="tree"]'
    )).filter(visible);
    const genericMenuSurfaceCount = genericSurfaces.filter((el) => el.getAttribute('role') === 'menu').length;
    const candidateRecord = controlRecord(candidate);
    const triggerRecord = controlRecord(trigger);
    const triggerOpenSignal = Boolean(
      triggerRecord &&
      (triggerRecord.ariaExpanded === 'true' || triggerRecord.dataState === 'open')
    );
    return {
      pickerCandidateFound: candidateRecord !== null,
      pickerCandidate: candidateRecord,
      nearestMenuTriggerFound: triggerRecord !== null,
      nearestMenuTriggerHops: triggerHops,
      nearestMenuTrigger: triggerRecord,
      triggerOpenSignal,
      genericPopupSurfaceCount: genericSurfaces.length,
      genericMenuSurfaceCount
    };
  })()`;
}


async function _pr88TriggerEvaluate(debuggee, expression) {
  try {
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

async function _pr88TriggerIdentitySnapshot(debuggee, context) {
  return _pr88TriggerEvaluate(
    debuggee,
    _pr88TriggerIdentityExpression(context?.pickerPoint, context?.pickerMode)
  );
}

async function _pr88TriggerModePopupSnapshot(debuggee) {
  try {
    if (typeof _pr88PopupDomExpression === "function") {
      return await _pr88TriggerEvaluate(debuggee, _pr88PopupDomExpression());
    }
  } catch {}
  return {};
}

function _pr88TriggerControlState(record) {
  const source = record && typeof record === "object" ? record : {};
  return {
    ariaExpanded:
      typeof source.ariaExpanded === "string" ? source.ariaExpanded : null,
    dataState: typeof source.dataState === "string" ? source.dataState : null,
    ariaHaspopup:
      typeof source.ariaHaspopup === "string" ? source.ariaHaspopup : null
  };
}

function _pr88TriggerStateChanged(a, b) {
  return Boolean(
    a &&
    b &&
    (
      a.ariaExpanded !== b.ariaExpanded ||
      a.dataState !== b.dataState ||
      a.ariaHaspopup !== b.ariaHaspopup
    )
  );
}

function _pr88TriggerEnsureContext(point, pickerMode) {
  let selection = null;
  try {
    if (typeof _pr88SelectionContext !== "undefined") {
      selection = _pr88SelectionContext;
    }
  } catch {}
  const leaseId = _pr88TriggerLeaseId(selection?.leaseId);
  if (leaseId === null) return null;
  if (
    _pr88TriggerTimelineContext === null ||
    _pr88TriggerTimelineContext.leaseId !== leaseId
  ) {
    _pr88TriggerTimelineContext = {
      leaseId,
      startedAt: performance.now(),
      pickerPoint: {
        x: Number.isFinite(point?.x) ? Number(point.x) : null,
        y: Number.isFinite(point?.y) ? Number(point.y) : null
      },
      pickerMode: typeof pickerMode === "string" ? pickerMode : null,
      awaitingPickerClick: true,
      clickDispatchCompleted: false,
      pickerClickElapsedMs: null,
      pollSampleCount: 0,
      samples: [],
      samplesTruncated: false,
      preClickState: null,
      bestSeen: {
        recognizedModes: new Set(),
        maxModeBearingPopupSurfaceCount: 0,
        maxKnownModeDescendantCount: 0,
        firstModeBearingPopupSeenMs: null,
        lastModeBearingPopupSeenMs: null,
        firstTriggerOpenSignalMs: null,
        triggerStateTransitionObserved: false,
        falseOpenGenericOnlyObserved: false,
        bestSelectedSurface: null
      }
    };
  }
  return _pr88TriggerTimelineContext;
}

async function _pr88TriggerAppendSample(
  debuggee,
  phase,
  optionResult = null,
  pollIndex = null
) {
  const context = _pr88TriggerTimelineContext;
  if (context === null) return null;

  const identity = await _pr88TriggerIdentitySnapshot(debuggee, context);
  const popup = await _pr88TriggerModePopupSnapshot(debuggee);
  const elapsedMs = Math.max(
    0,
    Math.round(performance.now() - context.startedAt)
  );

  const candidateState = _pr88TriggerControlState(identity?.pickerCandidate);
  const triggerState = _pr88TriggerControlState(identity?.nearestMenuTrigger);
  const effectiveState =
    identity?.nearestMenuTriggerFound === true ? triggerState : candidateState;
  if (phase === "PRE_CLICK") {
    context.preClickState = effectiveState;
  } else if (
    context.preClickState !== null &&
    _pr88TriggerStateChanged(context.preClickState, effectiveState)
  ) {
    context.bestSeen.triggerStateTransitionObserved = true;
  }

  const modeBearingCount = Number.isInteger(popup?.candidateSurfaceCount)
    ? popup.candidateSurfaceCount
    : 0;
  const selectedSurface =
    popup?.selectedSurface && typeof popup.selectedSurface === "object"
      ? popup.selectedSurface
      : null;
  const knownCount = Number.isInteger(selectedSurface?.knownModeDescendantCount)
    ? selectedSurface.knownModeDescendantCount
    : 0;
  const recognizedModes = Array.isArray(popup?.recognizedModes)
    ? popup.recognizedModes.filter((item) => typeof item === "string").slice(0, 16)
    : [];
  const genericCount = Number.isInteger(identity?.genericPopupSurfaceCount)
    ? identity.genericPopupSurfaceCount
    : 0;
  const falseOpenGenericOnly = genericCount > 0 && modeBearingCount === 0;

  if (modeBearingCount > 0) {
    if (context.bestSeen.firstModeBearingPopupSeenMs === null) {
      context.bestSeen.firstModeBearingPopupSeenMs = elapsedMs;
    }
    context.bestSeen.lastModeBearingPopupSeenMs = elapsedMs;
  }
  if (
    identity?.triggerOpenSignal === true &&
    context.bestSeen.firstTriggerOpenSignalMs === null
  ) {
    context.bestSeen.firstTriggerOpenSignalMs = elapsedMs;
  }
  if (falseOpenGenericOnly) {
    context.bestSeen.falseOpenGenericOnlyObserved = true;
  }
  context.bestSeen.maxModeBearingPopupSurfaceCount = Math.max(
    context.bestSeen.maxModeBearingPopupSurfaceCount,
    modeBearingCount
  );
  context.bestSeen.maxKnownModeDescendantCount = Math.max(
    context.bestSeen.maxKnownModeDescendantCount,
    knownCount
  );
  if (
    selectedSurface &&
    (
      context.bestSeen.bestSelectedSurface === null ||
      knownCount >
        (context.bestSeen.bestSelectedSurface.knownModeDescendantCount || 0)
    )
  ) {
    context.bestSeen.bestSelectedSurface = selectedSurface;
  }
  for (const mode of recognizedModes) {
    context.bestSeen.recognizedModes.add(mode);
  }

  const sample = {
    phase,
    pollIndex: Number.isInteger(pollIndex) ? pollIndex : null,
    elapsedMs,
    optionFound: optionResult?.found === true,
    optionCandidateCount: Number.isInteger(optionResult?.candidateCount)
      ? optionResult.candidateCount
      : 0,
    pickerCandidateFound: identity?.pickerCandidateFound === true,
    pickerCandidate:
      identity?.pickerCandidate && typeof identity.pickerCandidate === "object"
        ? identity.pickerCandidate
        : null,
    nearestMenuTriggerFound: identity?.nearestMenuTriggerFound === true,
    nearestMenuTriggerHops: Number.isInteger(identity?.nearestMenuTriggerHops)
      ? identity.nearestMenuTriggerHops
      : null,
    nearestMenuTrigger:
      identity?.nearestMenuTrigger &&
      typeof identity.nearestMenuTrigger === "object"
        ? identity.nearestMenuTrigger
        : null,
    triggerOpenSignal: identity?.triggerOpenSignal === true,
    genericPopupSurfaceCount: genericCount,
    genericMenuSurfaceCount: Number.isInteger(identity?.genericMenuSurfaceCount)
      ? identity.genericMenuSurfaceCount
      : 0,
    modeBearingPopupSurfaceCount: modeBearingCount,
    recognizedModes,
    maxKnownModeDescendantCount: knownCount,
    modePickerMaterialized: modeBearingCount > 0,
    falseOpenGenericOnly,
    selectedModeSurface: selectedSurface
  };
  if (context.samples.length < PR88_PICKER_TRIGGER_MAX_SAMPLES) {
    context.samples.push(sample);
  } else {
    context.samplesTruncated = true;
  }
  return sample;
}

