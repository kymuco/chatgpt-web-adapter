// PR8.8 shipping hardening: activate the proven current-effort product control
// through the DOM button itself. This avoids background-tab pointer-actuation
// variance while preserving the same fail-closed, pre-input boundary.

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

_pr88InstantEffortOpenPickerWithFallback =
  async function _pr88InstantEffortOpenPickerViaProvenDomControl(
    debuggee,point,expectedMode
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
  };
