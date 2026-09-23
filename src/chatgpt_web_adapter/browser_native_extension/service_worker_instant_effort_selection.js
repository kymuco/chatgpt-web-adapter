// PR15.18 explicit production owner for Instant reasoning-effort selection.
// Consolidates the former PR8.8 contract/key/selection/hardening/DOM/foreground/support
// chain without changing the fail-closed pre-input selection semantics.
//
// One owner now contains the full Instant-effort path. It does not reassign
// _pr88SelectionEnsureInstant or _pr88SelectionRecord at runtime.

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



async function _pr88InstantEffortWaitForSlider(debuggee, expectedMode, timeoutMs = 2500) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr88InstantEffortSliderSnapshot(debuggee, "snapshot");
    if (
      last?.found === true && last?.candidateCount === 1 &&
      last?.min === 0 && last?.max === 2 && Number.isInteger(last?.now) &&
      last?.stepCount === 3 && last?.currentControlOpen === true &&
      last?.currentMode === expectedMode && last?.disabled !== true &&
      last?.pointerEventsEnabled !== false
    ) return last;
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return last || {found:false, reason:"effort_slider_timeout", candidateCount:0};
}

async function _pr88InstantEffortDispatchHome(debuggee) {
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type:"rawKeyDown", key:"Home", code:"Home",
    windowsVirtualKeyCode:36, nativeVirtualKeyCode:36
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type:"keyUp", key:"Home", code:"Home",
    windowsVirtualKeyCode:36, nativeVirtualKeyCode:36
  });
}

async function _pr88InstantEffortWaitForSelected(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let selected = null;
  let slider = null;
  let sliderMinReached = false;
  let sliderObservedAfterHome = false;
  while (performance.now() - startedAt < timeoutMs) {
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    slider = await _pr88InstantEffortSliderSnapshot(debuggee, "snapshot");
    if (slider?.found === true) {
      sliderObservedAfterHome = true;
      if (slider?.min === 0 && slider?.now === slider?.min) sliderMinReached = true;
    }
    if (
      selected?.selectedModeProven === true &&
      selected?.selectedMode === "INSTANT" &&
      (sliderMinReached || slider?.found !== true)
    ) {
      return {selected, slider, sliderMinReached, sliderObservedAfterHome};
    }
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return {selected, slider, sliderMinReached, sliderObservedAfterHome};
}


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
      const r=el.getBoundingClientRect();
      if (r.width<=0||r.height<=0) return false;
      const s=getComputedStyle(el);
      return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';
    };
    const num=(value)=>{
      if(value===null||value===undefined||value==='') return null;
      const parsed=Number(value);
      return Number.isFinite(parsed)?parsed:null;
    };
    const fields=(el)=>[
      typeof el.innerText==='string'?el.innerText.slice(0,160):'',
      el.getAttribute('aria-label'),el.getAttribute('title')
    ];
    const oneMode=(el)=>{
      const modes=Array.from(new Set(fields(el).map(effort).filter(Boolean)));
      return modes.length===1?modes[0]:null;
    };
    const composer=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','textarea[placeholder]']
      .map((s)=>document.querySelector(s)).find((el)=>el&&visible(el));
    if(!composer) return {found:false,reason:'composer_missing',candidateCount:0,currentControlCount:0};
    const cr=composer.getBoundingClientRect();
    const controls=[];
    for(const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
      const mode=oneMode(el);
      if(!mode) continue;
      const r=el.getBoundingClientRect();
      const dx=Math.max(0,Math.max(cr.left-r.right,r.left-cr.right));
      const dy=Math.max(0,Math.max(cr.top-r.bottom,r.top-cr.bottom));
      const distance=Math.hypot(dx,dy);
      if(distance<=800) controls.push({el,mode,r,distance});
    }
    controls.sort((a,b)=>a.distance-b.distance);
    if(controls.length!==1) return {
      found:false,
      reason:controls.length?'current_effort_control_ambiguous':'current_effort_control_missing',
      candidateCount:0,currentControlCount:controls.length
    };
    const control=controls[0];
    const controlOpenObserved=
      control.el.getAttribute('aria-expanded')==='true'||
      normalize(control.el.getAttribute('data-state'))==='open';
    const sliders=[];
    for(const el of Array.from(document.querySelectorAll('[role="slider"],input[type="range"]')).filter(visible)) {
      const r=el.getBoundingClientRect();
      const min=num(el.getAttribute('aria-valuemin'))??num(el.min);
      const max=num(el.getAttribute('aria-valuemax'))??num(el.max);
      const now=num(el.getAttribute('aria-valuenow'))??num(el.value);
      if(!(Number.isInteger(min)&&Number.isInteger(max)&&Number.isInteger(now)&&min===0&&max===2&&now>=0&&now<=2)) continue;
      const distance=Math.hypot(
        (r.left+r.width/2)-(control.r.left+control.r.width/2),
        (r.top+r.height/2)-(control.r.top+control.r.height/2)
      );
      if(distance<=400) sliders.push({el,min,max,now,distance});
    }
    sliders.sort((a,b)=>a.distance-b.distance);
    if(sliders.length!==1) return {
      found:false,
      reason:controlOpenObserved?(sliders.length?'effort_slider_ambiguous':'effort_slider_missing'):'quick_picker_not_open',
      candidateCount:sliders.length,currentControlCount:1,currentMode:control.mode,
      currentControlOpen:controlOpenObserved
    };
    const slider=sliders[0];
    let focusProven=document.activeElement===slider.el;
    if(ACTION==='focus') {
      try { slider.el.focus({preventScroll:true}); } catch { try { slider.el.focus(); } catch {} }
      focusProven=document.activeElement===slider.el;
    }
    return {
      found:true,reason:null,candidateCount:1,currentControlCount:1,
      currentMode:control.mode,currentControlOpen:true,
      currentControlOpenObserved:controlOpenObserved,
      openProofKind:controlOpenObserved?'trigger_open_state':'visible_exact_slider',
      min:slider.min,max:slider.max,now:slider.now,stepCount:3,
      disabled:Boolean(slider.el.disabled===true||slider.el.getAttribute('aria-disabled')==='true'),
      pointerEventsEnabled:getComputedStyle(slider.el).pointerEvents!=='none',
      focusProven
    };
  })()`;
}

async function _pr88InstantEffortRelaxedSliderSnapshot(debuggee, action='snapshot') {
  const result=await chrome.debugger.sendCommand(debuggee,'Runtime.evaluate',{
    expression:_pr88InstantEffortRelaxedSliderExpression(action),
    returnByValue:true,awaitPromise:true
  });
  const value=result?.result?.value;
  return value&&typeof value==='object'
    ? value
    : {found:false,reason:'relaxed_slider_probe_failed',candidateCount:0,currentControlCount:0};
}

async function _pr88InstantEffortResolvedSliderSnapshot(debuggee, action='snapshot') {
  const primary=await _pr88InstantEffortSliderSnapshot(debuggee,action);
  if(primary?.found===true||primary?.reason!=='quick_picker_not_open') return primary;
  return _pr88InstantEffortRelaxedSliderSnapshot(debuggee,action);
}

function _pr88InstantEffortTriggerExpression(action) {
  return `(() => {
    const ACTION=${JSON.stringify(action)};
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
    if(candidates.length!==1) return {
      found:false,reason:candidates.length?'trigger_ambiguous':'trigger_missing',
      candidateCount:candidates.length
    };
    const target=candidates[0].el;
    if(ACTION==='focus') {
      try { target.focus({preventScroll:true}); } catch { try { target.focus(); } catch {} }
    }
    return {
      found:true,reason:null,candidateCount:1,mode:candidates[0].mode,
      open:target.getAttribute('aria-expanded')==='true'||normalize(target.getAttribute('data-state'))==='open',
      focusProven:document.activeElement===target
    };
  })()`;
}

async function _pr88InstantEffortTriggerSnapshot(debuggee,action='snapshot') {
  const result=await chrome.debugger.sendCommand(debuggee,'Runtime.evaluate',{
    expression:_pr88InstantEffortTriggerExpression(action),returnByValue:true,awaitPromise:true
  });
  const value=result?.result?.value;
  return value&&typeof value==='object'
    ? value
    : {found:false,reason:'trigger_probe_failed',candidateCount:0};
}

async function _pr88InstantEffortDispatchEnter(debuggee) {
  await chrome.debugger.sendCommand(debuggee,'Input.dispatchKeyEvent',{
    type:'rawKeyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13
  });
  await chrome.debugger.sendCommand(debuggee,'Input.dispatchKeyEvent',{
    type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13
  });
}

async function _pr88InstantEffortWaitForResolvedSlider(debuggee,expectedMode,timeoutMs=3000) {
  const startedAt=performance.now();
  let last=null;
  while(performance.now()-startedAt<timeoutMs) {
    last=await _pr88InstantEffortResolvedSliderSnapshot(debuggee,'snapshot');
    if(
      last?.found===true&&last?.candidateCount===1&&
      last?.min===0&&last?.max===2&&Number.isInteger(last?.now)&&last?.stepCount===3&&
      last?.currentMode===expectedMode&&last?.disabled!==true&&last?.pointerEventsEnabled!==false
    ) return last;
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return last||{found:false,reason:'effort_slider_timeout',candidateCount:0};
}

async function _pr88InstantEffortWaitForResolvedSelected(debuggee,timeoutMs) {
  const startedAt=performance.now();
  let selected=null,slider=null,sliderMinReached=false,sliderObservedAfterHome=false;
  while(performance.now()-startedAt<timeoutMs) {
    selected=await _pr88InstantSelectedModeSnapshot(debuggee);
    slider=await _pr88InstantEffortResolvedSliderSnapshot(debuggee,'snapshot');
    if(slider?.found===true) {
      sliderObservedAfterHome=true;
      if(slider?.min===0&&slider?.now===slider?.min) sliderMinReached=true;
    }
    if(
      selected?.selectedModeProven===true&&selected?.selectedMode==='INSTANT'&&
      (sliderMinReached||slider?.found!==true)
    ) return {selected,slider,sliderMinReached,sliderObservedAfterHome};
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return {selected,slider,sliderMinReached,sliderObservedAfterHome};
}


function _pr88InstantEffortDomTriggerClickExpression(expectedMode) {
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
    const composer=['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','textarea[placeholder]']
      .map((s)=>document.querySelector(s)).find((el)=>el&&visible(el));
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

async function _pr88InstantEffortDomTriggerClick(debuggee,expectedMode) {
  const result=await chrome.debugger.sendCommand(debuggee,'Runtime.evaluate',{
    expression:_pr88InstantEffortDomTriggerClickExpression(expectedMode),
    returnByValue:true,
    awaitPromise:true
  });
  const value=result?.result?.value;
  return value&&typeof value==='object'
    ? value
    : {clicked:false,reason:'dom_trigger_probe_failed',candidateCount:0};
}

async function _pr88InstantEffortOpenPickerWithFallback(
  debuggee, point, expectedMode
) {
    if(
      point?.found!==true||
      point?.candidateCount!==1||
      point?.mode!==expectedMode
    ) {
      throw new Error('PR8_8_INSTANT_EFFORT_DOM_TRIGGER_IDENTITY_NOT_PROVEN');
    }

    const already=await _pr88InstantEffortResolvedSliderSnapshot(debuggee,'snapshot');
    if(already?.found===true&&already?.candidateCount===1) return;

    const clicked=await _pr88InstantEffortDomTriggerClick(debuggee,expectedMode);
    if(
      clicked?.clicked!==true||
      clicked?.candidateCount!==1||
      clicked?.mode!==expectedMode
    ) {
      throw new Error(
        `PR8_8_INSTANT_EFFORT_DOM_TRIGGER_CLICK_NOT_PROVEN:${clicked?.reason||'unknown'}`
      );
    }

    const startedAt=performance.now();
    while(performance.now()-startedAt<3000) {
      const slider=await _pr88InstantEffortResolvedSliderSnapshot(debuggee,'snapshot');
      if(slider?.found===true&&slider?.candidateCount===1) return;
      const trigger=await _pr88InstantEffortTriggerSnapshot(debuggee,'snapshot');
      if(trigger?.found===true&&trigger?.mode===expectedMode&&trigger?.open===true) return;
      await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
    }

    const trigger=await _pr88InstantEffortTriggerSnapshot(debuggee,'focus');
    if(!(
      trigger?.found===true&&
      trigger?.candidateCount===1&&
      trigger?.mode===expectedMode&&
      trigger?.focusProven===true
    )) {
      throw new Error('PR8_8_INSTANT_EFFORT_TRIGGER_FOCUS_NOT_PROVEN');
    }
    if(trigger.open===true) return;
    await _pr88InstantEffortDispatchEnter(debuggee);
}


async function _pr88SelectionEnsureInstantCore(debuggee, context) {
  if (context.selectionChecked === true) return;
  context.selectionChecked = true;
  const startedAt = performance.now();

  const before = await _pr88InstantSelectedModeSnapshot(debuggee);
  context.selectedModeBeforeSelection = before?.selectedMode || null;
  context.selectedModeBeforeSelectionProven = before?.selectedModeProven === true;
  context.selectedModeBeforeSelectionProofKind = before?.proofKind || "unknown";
  context.selectedModeBeforeSelectionCandidateCount = Number.isInteger(before?.candidateCount)
    ? before.candidateCount : 0;

  Object.assign(context, {
    instantEffortSelectionSchemaVersion: PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION,
    selectionMechanism: null,
    instantEffortPickerClickPerformed: false,
    effortSliderCandidateCount: 0,
    effortSliderAriaValueMin: null,
    effortSliderAriaValueMax: null,
    effortSliderAriaValueNowBefore: null,
    effortSliderAriaValueNowAfter: null,
    effortSliderStepCount: null,
    effortSliderFocusProven: false,
    effortSliderHomeDispatched: false,
    effortSliderMinReachedProven: false,
    effortSliderObservedAfterHome: false,
    advancedControlClicked: false,
    modelControlClicked: false
  });

  if (before?.selectedModeProven !== true || typeof before?.selectedMode !== "string") {
    throw new Error("PR8_8_INSTANT_EFFORT_INITIAL_MODE_NOT_PROVEN");
  }
  if (before.selectedMode === "INSTANT") {
    context.selectionPerformed = false;
    context.selectionMechanism = "NO_SELECTION_REQUIRED";
    context.selectedModeAfterSelection = "INSTANT";
    context.selectedModeAfterSelectionProven = true;
    context.selectedModeAfterSelectionProofKind = before.proofKind || "unknown";
    context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
    context.selectionMutationElapsedMs = 0;
    context.selectionComplete = true;
    return;
  }

  context.selectionPerformed = true;
  context.selectionMechanism = "REASONING_EFFORT_SLIDER_HOME";
  _pr88SelectionInstallNetworkWindow(debuggee, context);
  const mutationStartedAt = performance.now();

  const picker = await _pr88SelectionPoint(debuggee, "picker");
  context.pickerCandidateCount = Number.isInteger(picker?.candidateCount) ? picker.candidateCount : 0;
  context.pickerNearestDistancePx = _pr88SelectionSafeInt(picker?.nearestDistancePx);
  context.pickerModeBeforeClick = typeof picker?.mode === "string" ? picker.mode : null;
  context.instantOptionCandidateCount = 0;
  if (picker?.found !== true || picker?.candidateCount !== 1 || picker?.mode !== before.selectedMode) {
    throw new Error(`PR8_8_INSTANT_EFFORT_PICKER_NOT_PROVEN:${picker?.reason || "identity_mismatch"}`);
  }

  let slider = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "snapshot");
  const alreadyOpen = (
    slider?.found === true && slider?.candidateCount === 1 &&
    slider?.min === 0 && slider?.max === 2 && slider?.stepCount === 3 &&
    slider?.currentControlOpen === true && slider?.currentMode === before.selectedMode
  );
  if (!alreadyOpen) {
    await _pr88InstantEffortOpenPickerWithFallback(debuggee, picker, before.selectedMode);
    context.instantEffortPickerClickPerformed = true;
    slider = await _pr88InstantEffortWaitForResolvedSlider(debuggee, before.selectedMode, 3000);
  }

  context.effortSliderCandidateCount = Number.isInteger(slider?.candidateCount) ? slider.candidateCount : 0;
  context.effortSliderAriaValueMin = Number.isFinite(slider?.min) ? slider.min : null;
  context.effortSliderAriaValueMax = Number.isFinite(slider?.max) ? slider.max : null;
  context.effortSliderAriaValueNowBefore = Number.isFinite(slider?.now) ? slider.now : null;
  context.effortSliderStepCount = Number.isInteger(slider?.stepCount) ? slider.stepCount : null;
  if (
    slider?.found !== true || slider?.candidateCount !== 1 ||
    slider?.min !== 0 || slider?.max !== 2 || slider?.stepCount !== 3
  ) {
    throw new Error(`PR8_8_INSTANT_EFFORT_SLIDER_CONTRACT_NOT_PROVEN:${slider?.reason || "range_mismatch"}`);
  }
  if (context.unexpectedConversationWriteBeforeSelectionComplete === true) {
    throw new Error("PR8_8_INSTANT_EFFORT_CONVERSATION_WRITE_BEFORE_SELECTION");
  }

  const focused = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "focus");
  context.effortSliderFocusProven = focused?.focusProven === true;
  if (
    focused?.found !== true || focused?.candidateCount !== 1 ||
    focused?.min !== 0 || focused?.max !== 2 ||
    focused?.stepCount !== 3 || focused?.focusProven !== true
  ) throw new Error("PR8_8_INSTANT_EFFORT_SLIDER_FOCUS_NOT_PROVEN");

  await _pr88InstantEffortDispatchHome(debuggee);
  context.effortSliderHomeDispatched = true;

  const settled = await _pr88InstantEffortWaitForResolvedSelected(
    debuggee, PR88_INSTANT_EFFORT_SELECTION_SETTLE_TIMEOUT_MS
  );
  const after = settled?.selected || null;
  const sliderAfter = settled?.slider || null;
  context.effortSliderMinReachedProven = settled?.sliderMinReached === true;
  context.effortSliderObservedAfterHome = settled?.sliderObservedAfterHome === true;
  context.effortSliderAriaValueNowAfter = Number.isFinite(sliderAfter?.now)
    ? sliderAfter.now : (context.effortSliderMinReachedProven ? 0 : null);
  context.selectedModeAfterSelection = after?.selectedMode || null;
  context.selectedModeAfterSelectionProven = after?.selectedModeProven === true;
  context.selectedModeAfterSelectionProofKind = after?.proofKind || "unknown";

  if (context.unexpectedConversationWriteBeforeSelectionComplete === true) {
    throw new Error("PR8_8_INSTANT_EFFORT_CONVERSATION_WRITE_BEFORE_SELECTION");
  }
  if (after?.selectedModeProven !== true || after?.selectedMode !== "INSTANT") {
    throw new Error("PR8_8_INSTANT_EFFORT_DID_NOT_SETTLE_TO_INSTANT");
  }
  if (settled?.sliderObservedAfterHome === true && settled?.sliderMinReached !== true) {
    throw new Error("PR8_8_INSTANT_EFFORT_SLIDER_MIN_NOT_REACHED");
  }

  context.selectionMutationElapsedMs = _pr88SelectionDurationMs(mutationStartedAt);
  context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
  context.selectionComplete = true;
}


async function _pr88InstantEffortDocumentVisible(debuggee) {
  try {
    const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
      expression: `(() => ({visible:document.visibilityState==='visible' && document.hidden!==true}))()`,
      returnByValue: true,
      awaitPromise: true
    });
    return result?.result?.value?.visible === true;
  } catch {
    return false;
  }
}

async function _pr88InstantEffortWaitForeground(debuggee, timeoutMs = 2500) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) return false;
  const startedAt = performance.now();
  while (performance.now() - startedAt < timeoutMs) {
    try {
      const tab = await chrome.tabs.get(tabId);
      if (tab?.active === true && await _pr88InstantEffortDocumentVisible(debuggee)) {
        return true;
      }
    } catch {}
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return false;
}

async function _pr88InstantEffortRestorePriorTab(state) {
  const result = {
    attempted: false,
    restored: state?.activated !== true,
    priorTabPresent: Number.isInteger(state?.priorActiveTabId)
  };
  if (state?.activated !== true || !Number.isInteger(state?.priorActiveTabId)) {
    return result;
  }
  result.attempted = true;
  try {
    const prior = await chrome.tabs.get(state.priorActiveTabId);
    if (!prior || prior.windowId !== state.windowId) return result;
    await chrome.tabs.update(state.priorActiveTabId, {active: true});
    const startedAt = performance.now();
    while (performance.now() - startedAt < 1500) {
      const current = await chrome.tabs.get(state.priorActiveTabId);
      if (current?.active === true) {
        result.restored = true;
        return result;
      }
      await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
    }
  } catch {}
  return result;
}

async function _pr88InstantEffortBeginTransientForeground(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) {
    throw new Error('PR8_8_INSTANT_EFFORT_RUNTIME_TAB_REQUIRED');
  }

  const runtimeTab = await chrome.tabs.get(tabId);
  const windowId = Number.isInteger(runtimeTab?.windowId) ? runtimeTab.windowId : null;
  if (windowId === null) {
    throw new Error('PR8_8_INSTANT_EFFORT_RUNTIME_WINDOW_REQUIRED');
  }

  let priorActiveTabId = null;
  try {
    const activeTabs = await chrome.tabs.query({active: true, windowId});
    const prior = activeTabs.find((tab) => Number.isInteger(tab?.id) && tab.id !== tabId);
    priorActiveTabId = Number.isInteger(prior?.id) ? prior.id : null;
  } catch {}

  const state = {
    tabId,
    windowId,
    activated: runtimeTab?.active !== true,
    priorActiveTabId,
    foregroundProven: false
  };

  try {
    if (state.activated) {
      await chrome.tabs.update(tabId, {active: true});
    }
    state.foregroundProven = await _pr88InstantEffortWaitForeground(debuggee, 2500);
    if (state.foregroundProven !== true) {
      throw new Error('PR8_8_INSTANT_EFFORT_FOREGROUND_NOT_PROVEN');
    }
    // Give the product surface one bounded paint/event-loop turn after visibility.
    await sleep(150);
    return state;
  } catch (error) {
    await _pr88InstantEffortRestorePriorTab(state);
    throw error;
  }
}

async function _pr88SelectionEnsureInstant(debuggee, context) {
    if (context?.selectionChecked === true) {
      return _pr88SelectionEnsureInstantCore(debuggee, context);
    }

    const before = await _pr88InstantSelectedModeSnapshot(debuggee);
    if (before?.selectedModeProven !== true || before?.selectedMode === 'INSTANT') {
      return _pr88SelectionEnsureInstantCore(debuggee, context);
    }

    const foreground = await _pr88InstantEffortBeginTransientForeground(debuggee);
    context.instantEffortTransientForegroundRequested = true;
    context.instantEffortTransientForegroundActivated = foreground.activated === true;
    context.instantEffortTransientForegroundProven = foreground.foregroundProven === true;
    context.instantEffortPriorActiveTabPresent = Number.isInteger(foreground.priorActiveTabId);

    try {
      return await _pr88SelectionEnsureInstantCore(debuggee, context);
    } finally {
      const restored = await _pr88InstantEffortRestorePriorTab(foreground);
      context.instantEffortForegroundRestoreAttempted = restored.attempted === true;
      context.instantEffortForegroundRestoreProven = restored.restored === true;
    }
}


function _pr88InstantEffortSupportDiagnosticMatches(message) {
  return message?.characterizeInstantEffortSelectionSupport === true;
}

async function _pr88HandleInstantEffortSupportDiagnostic(message) {
  if (_pr88InstantEffortSupportConflict(message)) {
    throw new Error("PR8_8_INSTANT_EFFORT_SUPPORT_FLAG_CONFLICT");
  }
  return {
    instantEffortSelectionSupported: true,
    instantEffortSelectionSchemaVersion:
      PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION,
    productionInstantWorkingPathSupported: true,
    quickPickerOnly: true,
    exactDiscreteRangeRequired: true,
    semanticHomeKeySelectionSupported: true,
    selectedInstantProofRequired: true,
    preInputFailureBoundaryPreserved: true,
    advancedPickerClickForbidden: true,
    modelControlClickForbidden: true,
    automaticRetry: false
  };
}

registerNativeTurnDiagnosticHandler(
  "instant-effort-support",
  _pr88InstantEffortSupportDiagnosticMatches,
  _pr88HandleInstantEffortSupportDiagnostic
);
