// PR8.8 production hardening for current-effort picker actuation.
// Adds two bounded compatibility behaviors before any prompt insertion:
// 1) a unique visible exact 0..2 semantic slider is itself proof that the quick
//    effort surface materialized even if aria-expanded/data-state lags;
// 2) if the pointer click leaves the unique trigger provably closed, focus the
//    same trigger and dispatch Enter once, then let the existing slider wait run.

const _pr88InstantEffortPriorSliderSnapshot = _pr88InstantEffortSliderSnapshot;
const _pr88InstantEffortPriorRawClick = _pr88SelectionRawClick;

function _pr88InstantEffortRelaxedSliderExpression(action) {
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
    const fields = (el) => [
      typeof el.innerText === 'string' ? el.innerText.slice(0,160) : '',
      el.getAttribute('aria-label'), el.getAttribute('title')
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
    ].map((s) => document.querySelector(s)).find((el) => el && visible(el));
    if (!composer) return {found:false, reason:'composer_missing', candidateCount:0, currentControlCount:0};
    const cr = composer.getBoundingClientRect();
    const controls = [];
    for (const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
      const mode = oneMode(el);
      if (!mode) continue;
      const r = el.getBoundingClientRect();
      const dx = Math.max(0, Math.max(cr.left-r.right, r.left-cr.right));
      const dy = Math.max(0, Math.max(cr.top-r.bottom, r.top-cr.bottom));
      const distance = Math.hypot(dx,dy);
      if (distance <= 800) controls.push({el,mode,r,distance});
    }
    controls.sort((a,b) => a.distance-b.distance);
    if (controls.length !== 1) return {
      found:false,
      reason:controls.length ? 'current_effort_control_ambiguous' : 'current_effort_control_missing',
      candidateCount:0,
      currentControlCount:controls.length
    };
    const control = controls[0];
    const controlOpenObserved = control.el.getAttribute('aria-expanded') === 'true' || normalize(control.el.getAttribute('data-state')) === 'open';
    const sliders = [];
    for (const el of Array.from(document.querySelectorAll('[role="slider"],input[type="range"]')).filter(visible)) {
      const r = el.getBoundingClientRect();
      const min = num(el.getAttribute('aria-valuemin')) ?? num(el.min);
      const max = num(el.getAttribute('aria-valuemax')) ?? num(el.max);
      const now = num(el.getAttribute('aria-valuenow')) ?? num(el.value);
      if (!(Number.isInteger(min) && Number.isInteger(max) && Number.isInteger(now) && min === 0 && max === 2 && now >= 0 && now <= 2)) continue;
      const distance = Math.hypot((r.left+r.width/2)-(control.r.left+control.r.width/2),(r.top+r.height/2)-(control.r.top+control.r.height/2));
      if (distance <= 400) sliders.push({el,r,min,max,now,distance});
    }
    sliders.sort((a,b) => a.distance-b.distance);
    if (sliders.length !== 1) return {
      found:false,
      reason:controlOpenObserved ? (sliders.length ? 'effort_slider_ambiguous' : 'effort_slider_missing') : 'quick_picker_not_open',
      candidateCount:sliders.length,
      currentControlCount:1,
      currentMode:control.mode,
      currentControlOpen:controlOpenObserved
    };
    const slider = sliders[0];
    let focusProven = document.activeElement === slider.el;
    if (ACTION === 'focus') {
      try { slider.el.focus({preventScroll:true}); } catch { try { slider.el.focus(); } catch {} }
      focusProven = document.activeElement === slider.el;
    }
    return {
      found:true,
      reason:null,
      candidateCount:1,
      currentControlCount:1,
      currentMode:control.mode,
      currentControlOpen:true,
      currentControlOpenObserved:controlOpenObserved,
      openProofKind:controlOpenObserved ? 'trigger_open_state' : 'visible_exact_slider',
      min:slider.min,
      max:slider.max,
      now:slider.now,
      stepCount:3,
      disabled:Boolean(slider.el.disabled === true || slider.el.getAttribute('aria-disabled') === 'true'),
      pointerEventsEnabled:getComputedStyle(slider.el).pointerEvents !== 'none',
      focusProven
    };
  })()`;
}

async function _pr88InstantEffortSliderSnapshot(debuggee, action = 'snapshot') {
  const primary = await _pr88InstantEffortPriorSliderSnapshot(debuggee, action);
  if (primary?.found === true || primary?.reason !== 'quick_picker_not_open') return primary;
  const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
    expression: _pr88InstantEffortRelaxedSliderExpression(action),
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === 'object' ? value : primary;
}

function _pr88InstantEffortTriggerExpression(action) {
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
      const r=el.getBoundingClientRect();
      if (r.width<=0||r.height<=0) return false;
      const s=getComputedStyle(el);
      return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';
    };
    const composer=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','textarea[placeholder]']
      .map((s)=>document.querySelector(s)).find((el)=>el&&visible(el));
    if(!composer) return {found:false,reason:'composer_missing',candidateCount:0};
    const cr=composer.getBoundingClientRect();
    const candidates=[];
    for(const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
      const modes=Array.from(new Set([el.innerText,el.getAttribute('aria-label'),el.getAttribute('title')].map(effort).filter(Boolean)));
      if(modes.length!==1) continue;
      const r=el.getBoundingClientRect();
      const dx=Math.max(0,Math.max(cr.left-r.right,r.left-cr.right));
      const dy=Math.max(0,Math.max(cr.top-r.bottom,r.top-cr.bottom));
      const distance=Math.hypot(dx,dy);
      if(distance<=800) candidates.push({el,mode:modes[0],distance});
    }
    candidates.sort((a,b)=>a.distance-b.distance);
    if(candidates.length!==1) return {found:false,reason:candidates.length?'trigger_ambiguous':'trigger_missing',candidateCount:candidates.length};
    const target=candidates[0].el;
    if(ACTION==='focus') {
      try { target.focus({preventScroll:true}); } catch { try { target.focus(); } catch {} }
    }
    return {
      found:true,
      reason:null,
      candidateCount:1,
      mode:candidates[0].mode,
      open:target.getAttribute('aria-expanded')==='true'||normalize(target.getAttribute('data-state'))==='open',
      focusProven:document.activeElement===target
    };
  })()`;
}

async function _pr88InstantEffortTriggerSnapshot(debuggee, action = 'snapshot') {
  const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
    expression:_pr88InstantEffortTriggerExpression(action), returnByValue:true, awaitPromise:true
  });
  const value=result?.result?.value;
  return value&&typeof value==='object'?value:{found:false,reason:'trigger_probe_failed',candidateCount:0};
}

async function _pr88InstantEffortDispatchEnter(debuggee) {
  await chrome.debugger.sendCommand(debuggee, 'Input.dispatchKeyEvent', {
    type:'rawKeyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, nativeVirtualKeyCode:13
  });
  await chrome.debugger.sendCommand(debuggee, 'Input.dispatchKeyEvent', {
    type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, nativeVirtualKeyCode:13
  });
}

_pr88SelectionRawClick = async function _pr88SelectionRawClickWithEffortTriggerFallback(debuggee, point) {
  await _pr88InstantEffortPriorRawClick(debuggee, point);
  if (point?.candidateCount !== 1 || typeof point?.mode !== 'string') return;

  const startedAt=performance.now();
  let trigger=null;
  while(performance.now()-startedAt<3000) {
    const slider=await _pr88InstantEffortSliderSnapshot(debuggee,'snapshot');
    if(slider?.found===true&&slider?.candidateCount===1) return;
    trigger=await _pr88InstantEffortTriggerSnapshot(debuggee,'snapshot');
    if(trigger?.found===true&&trigger?.mode===point.mode&&trigger?.open===true) return;
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }

  trigger=await _pr88InstantEffortTriggerSnapshot(debuggee,'focus');
  if(!(trigger?.found===true&&trigger?.candidateCount===1&&trigger?.mode===point.mode&&trigger?.focusProven===true)) {
    throw new Error('PR8_8_INSTANT_EFFORT_TRIGGER_FOCUS_NOT_PROVEN');
  }
  if(trigger.open===true) return;
  await _pr88InstantEffortDispatchEnter(debuggee);
};
