// PR8.8 semantic reasoning-effort slider runtime for production Instant selection.
// Pure helper layer: observation, focus, bounded wait, and the standard Home key.
// No prompt insertion, submit, Advanced/model click, tab lifecycle action, or retry.

const PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION = 1;
const PR88_INSTANT_EFFORT_SELECTION_SETTLE_TIMEOUT_MS = 8000;
const PR88_INSTANT_EFFORT_SELECTION_POLL_MS = 100;

function _pr88InstantEffortSupportConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true ||
    message?.openQuickPicker === true ||
    message?.inspectAdvancedSurface === true ||
    message?.allowUiNavigation === true
  );
}

function _pr88InstantEffortSliderExpression(action) {
  return `(() => {
    const ACTION = ${JSON.stringify(action)};
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const effort = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) return 'INSTANT';
      if (/(^|\\b)(medium|средний)(\\b|$)/.test(text)) return 'MEDIUM';
      if (/(^|\\b)(high|высокий)(\\b|$)/.test(text)) return 'HIGH';
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
      return {x:Math.round(r.left),y:Math.round(r.top),width:Math.round(r.width),height:Math.round(r.height)};
    };
    const centerDistance = (a,b) => Math.hypot(
      (a.left+a.width/2)-(b.left+b.width/2),
      (a.top+a.height/2)-(b.top+b.height/2)
    );
    const fields = (el) => [
      typeof el.innerText === 'string' ? el.innerText.slice(0,160) : '',
      el.getAttribute('aria-label'),
      el.getAttribute('title')
    ];
    const oneMode = (el) => {
      const modes = Array.from(new Set(fields(el).map(effort).filter(Boolean)));
      return modes.length === 1 ? modes[0] : null;
    };
    const num = (value) => {
      if (value === null || value === undefined || value === '') return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };

    const composer = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ].map((selector) => document.querySelector(selector)).find((el) => el && visible(el));
    if (!composer) {
      return {found:false, reason:'composer_missing', candidateCount:0, currentControlCount:0};
    }

    const cr = composer.getBoundingClientRect();
    const controls = [];
    for (const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
      const mode = oneMode(el);
      if (!mode) continue;
      const r = el.getBoundingClientRect();
      const dx = Math.max(0, Math.max(cr.left-r.right, r.left-cr.right));
      const dy = Math.max(0, Math.max(cr.top-r.bottom, r.top-cr.bottom));
      const distance = Math.hypot(dx,dy);
      if (distance <= 800) controls.push({el,mode,distance,r});
    }
    controls.sort((a,b) => a.distance-b.distance);
    if (controls.length !== 1) {
      return {
        found:false,
        reason:controls.length ? 'current_effort_control_ambiguous' : 'current_effort_control_missing',
        candidateCount:0,
        currentControlCount:controls.length
      };
    }

    const control = controls[0];
    const controlOpen = (
      control.el.getAttribute('aria-expanded') === 'true' ||
      normalize(control.el.getAttribute('data-state')) === 'open'
    );
    if (!controlOpen) {
      return {
        found:false, reason:'quick_picker_not_open', candidateCount:0,
        currentControlCount:1, currentMode:control.mode, currentControlOpen:false
      };
    }

    const sliders = [];
    for (const el of Array.from(document.querySelectorAll('[role="slider"],input[type="range"]')).filter(visible)) {
      const r = el.getBoundingClientRect();
      const min = num(el.getAttribute('aria-valuemin')) ?? num(el.min);
      const max = num(el.getAttribute('aria-valuemax')) ?? num(el.max);
      const now = num(el.getAttribute('aria-valuenow')) ?? num(el.value);
      const exact = (
        Number.isInteger(min) && Number.isInteger(max) && Number.isInteger(now) &&
        min === 0 && max === 2 && now >= min && now <= max
      );
      if (!exact) continue;
      const distance = centerDistance(r, control.r);
      if (distance > 400) continue;
      sliders.push({el,r,min,max,now,distance});
    }
    sliders.sort((a,b) => a.distance-b.distance);
    if (sliders.length !== 1) {
      return {
        found:false,
        reason:sliders.length ? 'effort_slider_ambiguous' : 'effort_slider_missing',
        candidateCount:sliders.length,
        currentControlCount:1,
        currentMode:control.mode,
        currentControlOpen:true
      };
    }

    const slider = sliders[0];
    let focusProven = document.activeElement === slider.el;
    if (ACTION === 'focus') {
      try { slider.el.focus({preventScroll:true}); }
      catch { try { slider.el.focus(); } catch {} }
      focusProven = document.activeElement === slider.el;
    }

    return {
      found:true, reason:null, candidateCount:1, currentControlCount:1,
      currentMode:control.mode, currentControlOpen:true,
      currentControlRect:rect(control.el),
      min:slider.min, max:slider.max, now:slider.now, stepCount:3,
      orientation:slider.el.getAttribute('aria-orientation') || (slider.r.width >= slider.r.height ? 'horizontal' : 'vertical'),
      thumbRect:rect(slider.el),
      tabIndex:Number.isInteger(slider.el.tabIndex) ? slider.el.tabIndex : null,
      disabled:Boolean(slider.el.disabled === true || slider.el.getAttribute('aria-disabled') === 'true'),
      pointerEventsEnabled:getComputedStyle(slider.el).pointerEvents !== 'none',
      focusProven
    };
  })()`;
}

async function _pr88InstantEffortSliderSnapshot(debuggee, action = "snapshot") {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr88InstantEffortSliderExpression(action),
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object"
    ? value
    : {found:false, reason:"slider_probe_failed", candidateCount:0, currentControlCount:0};
}

