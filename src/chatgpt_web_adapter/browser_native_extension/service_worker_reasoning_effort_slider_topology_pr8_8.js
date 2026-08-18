// PR8.8 reasoning-effort slider topology and quick/advanced surface classifiers.
// Pure observation helpers: no clicks, writes, navigation, or storage mutation.

const PR88_REASONING_EFFORT_SLIDER_SCHEMA_VERSION = 1;

function _pr88EffortNormalize(value) {
  return typeof value === "string" ? value.trim().toLowerCase().replace(/[\s_\-]+/g, " ") : "";
}

function _pr88EffortMode(value) {
  const text = _pr88EffortNormalize(value);
  if (!text) return null;
  if (/(^|\b)(instant|мгновенно)(\b|$)/.test(text)) return "INSTANT";
  if (/(^|\b)(medium|средний)(\b|$)/.test(text)) return "MEDIUM";
  if (/(^|\b)(high|высокий)(\b|$)/.test(text)) return "HIGH";
  return null;
}

function _pr88ModelMode(value) {
  const text = _pr88EffortNormalize(value);
  if (!text) return null;
  if (text.includes("gpt 5.6 sol") || text.includes("gpt-5.6 sol")) return "GPT_5_6_SOL";
  if (text.includes("gpt 5.5") || text.includes("gpt-5.5")) return "GPT_5_5";
  if (/(^|\b)o3(\b|$)/.test(text)) return "O3";
  return null;
}

function _pr88Dimension(value) {
  const text = _pr88EffortNormalize(value);
  if (!text) return null;
  if (text === "advanced" || text === "расширенные") return "ADVANCED";
  if (text === "model" || text === "модель") return "MODEL";
  if (text === "effort" || text === "усилие") return "EFFORT";
  if (text === "back" || text === "назад") return "BACK";
  return null;
}

function _pr88EffortTopologyExpression(kind) {
  return `(() => {
    const KIND = ${JSON.stringify(kind)};
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const effort = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) return 'INSTANT';
      if (/(^|\\b)(medium|средний)(\\b|$)/.test(text)) return 'MEDIUM';
      if (/(^|\\b)(high|высокий)(\\b|$)/.test(text)) return 'HIGH';
      return null;
    };
    const model = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (text.includes('gpt 5.6 sol') || text.includes('gpt-5.6 sol')) return 'GPT_5_6_SOL';
      if (text.includes('gpt 5.5') || text.includes('gpt-5.5')) return 'GPT_5_5';
      if (/(^|\\b)o3(\\b|$)/.test(text)) return 'O3';
      return null;
    };
    const dimension = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (text === 'advanced' || text === 'расширенные' || text.startsWith('advanced ') || text.startsWith('расширенные ')) return 'ADVANCED';
      if (text === 'model' || text === 'модель' || text.startsWith('model ') || text.startsWith('модель ')) return 'MODEL';
      if (text === 'effort' || text === 'усилие' || text.startsWith('effort ') || text.startsWith('усилие ')) return 'EFFORT';
      if (text === 'back' || text === 'назад') return 'BACK';
      return null;
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
    const ownText = (el) => Array.from(el.childNodes || []).filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent || '').join(' ');
    const direct = (el) => [ownText(el), el.getAttribute('aria-label'), el.getAttribute('title')];
    const controlFields = (el) => [typeof el.innerText === 'string' ? el.innerText.slice(0, 160) : '', el.getAttribute('aria-label'), el.getAttribute('title')];
    const subtree = (el) => [typeof el.innerText === 'string' ? el.innerText.slice(0, 320) : '', el.textContent ? String(el.textContent).slice(0, 320) : ''];
    const one = (values, fn) => {
      const found = Array.from(new Set(values.map(fn).filter(Boolean)));
      return found.length === 1 ? found[0] : null;
    };
    const boundedState = (value) => {
      const text = normalize(value);
      return ['open','closed','selected','checked','unchecked','active','inactive','on','off'].includes(text) ? text : null;
    };
    const controlRecord = (el) => el ? ({
      tag: el.tagName,
      role: el.getAttribute('role') || null,
      rect: rect(el),
      effortMode: one(controlFields(el), effort),
      dimension: one(controlFields(el), dimension),
      ariaHaspopup: el.getAttribute('aria-haspopup') || null,
      ariaExpanded: el.getAttribute('aria-expanded') || null,
      dataState: boundedState(el.getAttribute('data-state')),
      disabled: Boolean(el.disabled === true || el.getAttribute('aria-disabled') === 'true'),
      pointerEventsEnabled: getComputedStyle(el).pointerEvents !== 'none',
      childElementCount: el.children ? el.children.length : 0
    }) : null;
    const composer = ['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','textarea[placeholder]']
      .map((s) => document.querySelector(s)).find((el) => el && visible(el));
    let currentEffortControl = null;
    let currentEffortCandidateCount = 0;
    if (composer) {
      const cr = composer.getBoundingClientRect();
      const candidates = [];
      for (const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
        const mode = one(controlFields(el), effort);
        if (!mode) continue;
        const r = el.getBoundingClientRect();
        const dx = Math.max(0, Math.max(cr.left - r.right, r.left - cr.right));
        const dy = Math.max(0, Math.max(cr.top - r.bottom, r.top - cr.bottom));
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance <= 800) candidates.push({el, mode, distance});
      }
      candidates.sort((a,b) => a.distance - b.distance);
      currentEffortCandidateCount = candidates.length;
      if (candidates.length) {
        currentEffortControl = {...controlRecord(candidates[0].el), effortMode: candidates[0].mode, nearestDistancePx: Math.round(candidates[0].distance)};
      }
    }
    const surfaceRoles = new Set(['menu','dialog','group','listbox','radiogroup']);
    const allSurfaces = Array.from(document.querySelectorAll('[role="menu"],[role="dialog"],[role="group"],[role="listbox"],[role="radiogroup"]')).filter(visible);
    if (KIND === 'quick') {
      const candidates = [];
      for (const surface of allSurfaces) {
        const descendants = [surface, ...Array.from(surface.querySelectorAll('*'))].filter(visible);
        const sliders = descendants.filter((el) => el.getAttribute('role') === 'slider' || (el.tagName === 'INPUT' && normalize(el.getAttribute('type')) === 'range'));
        const modeNodes = descendants.map((el) => ({el, mode: one([...direct(el), ...subtree(el)], effort)})).filter((x) => x.mode);
        const modes = Array.from(new Set(modeNodes.map((x) => x.mode))).sort();
        if (!sliders.length && modes.length < 2) continue;
        candidates.push({surface, descendants, sliders, modeNodes, modes});
      }
      candidates.sort((a,b) => (b.modes.length - a.modes.length) || (b.sliders.length - a.sliders.length));
      const selected = candidates[0] || null;
      const genericSurfaceCount = allSurfaces.length;
      if (!selected) return {surfaceFound:false, genericSurfaceCount, modeBearingSurfaceCount:0, sliderSurfaceCount:0, currentEffortControl, currentEffortCandidateCount};
      const sliders = selected.sliders.map((el, index) => {
        const r = el.getBoundingClientRect();
        const valueTextMode = effort(el.getAttribute('aria-valuetext')) || effort(el.getAttribute('aria-label'));
        const num = (v) => { const x = Number(v); return Number.isFinite(x) ? x : null; };
        return {
          index,
          tag: el.tagName,
          role: el.getAttribute('role') || null,
          rect: rect(el),
          orientation: el.getAttribute('aria-orientation') || (r.width >= r.height ? 'horizontal' : 'vertical'),
          ariaValueMin: num(el.getAttribute('aria-valuemin')),
          ariaValueMax: num(el.getAttribute('aria-valuemax')),
          ariaValueNow: num(el.getAttribute('aria-valuenow')),
          ariaValueTextMode: valueTextMode,
          nativeMin: num(el.min), nativeMax: num(el.max), nativeValue: num(el.value), nativeStep: num(el.step),
          disabled: Boolean(el.disabled === true || el.getAttribute('aria-disabled') === 'true')
        };
      });
      const minimal = selected.modeNodes.filter((item) => !selected.modeNodes.some((other) => other !== item && item.el.contains(other.el) && other.mode === item.mode));
      const marks = minimal.map((item) => {
        const rr = item.el.getBoundingClientRect();
        let nearestIndex = null, nearestDistance = null, normalizedPosition = null;
        sliders.forEach((slider) => {
          const sr = selected.sliders[slider.index].getBoundingClientRect();
          const horizontal = slider.orientation !== 'vertical';
          const pos = horizontal ? ((rr.left + rr.width/2 - sr.left) / Math.max(1, sr.width)) : ((rr.top + rr.height/2 - sr.top) / Math.max(1, sr.height));
          const clamped = Math.max(0, Math.min(1, pos));
          const dx = Math.max(0, Math.max(sr.left - rr.right, rr.left - sr.right));
          const dy = Math.max(0, Math.max(sr.top - rr.bottom, rr.top - sr.bottom));
          const distance = Math.round(Math.sqrt(dx*dx + dy*dy));
          if (nearestDistance === null || distance < nearestDistance) { nearestDistance = distance; nearestIndex = slider.index; normalizedPosition = Math.round(clamped * 1000) / 1000; }
        });
        return {mode:item.mode, tag:item.el.tagName, role:item.el.getAttribute('role') || null, rect:rect(item.el), nearestSliderIndex:nearestIndex, nearestSliderDistancePx:nearestDistance, normalizedPosition};
      });
      const primary = sliders.length ? sliders[0] : null;
      const mapping = marks.filter((m) => m.nearestSliderIndex === 0).sort((a,b) => (a.normalizedPosition ?? 0) - (b.normalizedPosition ?? 0)).map((m, rank) => ({mode:m.mode, rank, normalizedPosition:m.normalizedPosition}));
      const mappedModes = Array.from(new Set(mapping.map((m) => m.mode))).sort();
      const advanced = selected.descendants.filter((el) => ['BUTTON','DIV'].includes(el.tagName) || el.getAttribute('role') === 'button').map((el) => ({el, dimension:one(controlFields(el), dimension)})).filter((x) => x.dimension === 'ADVANCED');
      return {
        surfaceFound:true,
        genericSurfaceCount,
        modeBearingSurfaceCount:candidates.filter((x) => x.modes.length >= 2).length,
        sliderSurfaceCount:candidates.filter((x) => x.sliders.length > 0).length,
        selectedSurface:{tag:selected.surface.tagName, role:selected.surface.getAttribute('role') || null, rect:rect(selected.surface), recognizedEffortModes:selected.modes, visibleElementCount:selected.descendants.length},
        currentEffortControl, currentEffortCandidateCount,
        sliders, effortMarks:marks, discreteStepMapping:mapping,
        completeThreeStepMapping:['HIGH','INSTANT','MEDIUM'].every((m) => mappedModes.includes(m)),
        primarySlider:primary,
        advancedButtonCount:advanced.length,
        advancedButton:advanced.length === 1 ? controlRecord(advanced[0].el) : null
      };
    }
    const surfaces = [];
    for (const surface of allSurfaces) {
      const descendants = [surface, ...Array.from(surface.querySelectorAll('*'))].filter(visible);
      const dims = descendants.map((el) => ({el, dimension:one(controlFields(el), dimension)})).filter((x) => x.dimension);
      const dimSet = Array.from(new Set(dims.map((x) => x.dimension))).sort();
      if (!dimSet.includes('MODEL') || !dimSet.includes('EFFORT')) continue;
      surfaces.push({surface, descendants, dims, dimSet});
    }
    const selected = surfaces[0] || null;
    if (!selected) return {surfaceFound:false, candidateSurfaceCount:surfaces.length};
    const controls = selected.dims.map((x) => ({...controlRecord(x.el), dimension:x.dimension}));
    const modelControls = controls.filter((x) => x.dimension === 'MODEL');
    const effortControls = controls.filter((x) => x.dimension === 'EFFORT');
    const modelValues = Array.from(new Set(selected.descendants.flatMap((el) => [...direct(el), ...subtree(el)].map(model).filter(Boolean)))).sort();
    const effortValues = Array.from(new Set(selected.descendants.flatMap((el) => [...direct(el), ...subtree(el)].map(effort).filter(Boolean)))).sort();
    const separated = modelControls.length === 1 && effortControls.length === 1 && (modelControls[0].rect.x !== effortControls[0].rect.x || modelControls[0].rect.y !== effortControls[0].rect.y);
    return {
      surfaceFound:true,
      candidateSurfaceCount:surfaces.length,
      selectedSurface:{tag:selected.surface.tagName, role:selected.surface.getAttribute('role') || null, rect:rect(selected.surface), visibleElementCount:selected.descendants.length},
      dimensionControls:controls,
      modelControlCount:modelControls.length,
      effortControlCount:effortControls.length,
      backControlCount:controls.filter((x) => x.dimension === 'BACK').length,
      dimensionsSeparated:separated,
      visibleModelValues:modelValues,
      visibleEffortValues:effortValues
    };
  })()`;
}

async function _pr88EffortEvaluate(debuggee, kind) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr88EffortTopologyExpression(kind), returnByValue: true, awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object" ? value : {};
}
