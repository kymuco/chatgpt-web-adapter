// PR8.8 slider thumb-vs-track geometry, discrete ARIA semantics, label association,
// and logical Advanced-control dealiasing. Strictly zero-click / zero-write.

const PR88_REASONING_EFFORT_GEOMETRY_SCHEMA_VERSION = 1;
const _pr88EffortGeometryPriorExecuteNativeTurn = executeNativeTurn;

function _pr88EffortGeometryConflict(message) {
  return (
    message?.text != null ||
    message?.browserAuthorityLeaseId != null ||
    message?.canonicalCompleted === true ||
    message?.openQuickPicker === true ||
    message?.inspectAdvancedSurface === true ||
    message?.allowUiNavigation === true
  );
}

function _pr88EffortGeometryConversationId(value) {
  const id = typeof value === "string" ? value.trim() : "";
  return id && !/[\/?#]/.test(id) ? id : null;
}

function _pr88EffortGeometryExpression() {
  return `(() => {
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const effort = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) return 'INSTANT';
      if (/(^|\\b)(medium|средний)(\\b|$)/.test(text)) return 'MEDIUM';
      if (/(^|\\b)(high|высокий)(\\b|$)/.test(text)) return 'HIGH';
      return null;
    };
    const dimension = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (text === 'advanced' || text === 'расширенные' || text.startsWith('advanced ') || text.startsWith('расширенные ')) return 'ADVANCED';
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
    const ownText = (el) => Array.from(el.childNodes || []).filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent || '').join(' ');
    const fields = (el) => [ownText(el), el.getAttribute('aria-label'), el.getAttribute('title')];
    const controlFields = (el) => [typeof el.innerText === 'string' ? el.innerText.slice(0,160) : '', el.getAttribute('aria-label'), el.getAttribute('title')];
    const one = (values, fn) => {
      const found = Array.from(new Set(values.map(fn).filter(Boolean)));
      return found.length === 1 ? found[0] : null;
    };
    const num = (value) => { const x = Number(value); return Number.isFinite(x) ? x : null; };
    const center = (r) => ({x:r.left+r.width/2,y:r.top+r.height/2});
    const centerDistance = (a,b) => Math.hypot((a.x+a.width/2)-(b.x+b.width/2),(a.y+a.height/2)-(b.y+b.height/2));
    const overlapRatio = (a,b) => {
      const left=Math.max(a.x,b.x), right=Math.min(a.x+a.width,b.x+b.width);
      const top=Math.max(a.y,b.y), bottom=Math.min(a.y+a.height,b.y+b.height);
      const area=Math.max(0,right-left)*Math.max(0,bottom-top);
      return area / Math.max(1, Math.min(a.width*a.height,b.width*b.height));
    };
    const relation = (a,b) => a.contains(b) ? 'CONTAINS' : (b.contains(a) ? 'CONTAINED_BY' : 'PEER');

    const composer = ['#prompt-textarea','[contenteditable="true"][data-lexical-editor="true"]','textarea[placeholder]']
      .map((s) => document.querySelector(s)).find((el) => el && visible(el));
    let currentEffortControl = null;
    if (composer) {
      const cr = composer.getBoundingClientRect();
      const controls = [];
      for (const el of Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible)) {
        const mode = one(controlFields(el), effort);
        if (!mode) continue;
        const r = el.getBoundingClientRect();
        const dx=Math.max(0,Math.max(cr.left-r.right,r.left-cr.right));
        const dy=Math.max(0,Math.max(cr.top-r.bottom,r.top-cr.bottom));
        const d=Math.hypot(dx,dy);
        if (d <= 800) controls.push({el,mode,d});
      }
      controls.sort((a,b)=>a.d-b.d);
      if (controls.length === 1) currentEffortControl = {mode:controls[0].mode,rect:rect(controls[0].el),ariaExpanded:controls[0].el.getAttribute('aria-expanded'),dataState:normalize(controls[0].el.getAttribute('data-state'))||null};
    }

    const sliders = Array.from(document.querySelectorAll('[role="slider"],input[type="range"]')).filter(visible).map((el,index) => {
      const r=el.getBoundingClientRect();
      const min=num(el.getAttribute('aria-valuemin')) ?? num(el.min);
      const max=num(el.getAttribute('aria-valuemax')) ?? num(el.max);
      const now=num(el.getAttribute('aria-valuenow')) ?? num(el.value);
      const orientation=el.getAttribute('aria-orientation') || (r.width >= r.height ? 'horizontal':'vertical');
      const discrete=Number.isInteger(min)&&Number.isInteger(max)&&max>=min&&max-min<=15;
      return {el,index,r,min,max,now,orientation,discrete,stepCount:discrete?(max-min+1):null};
    });
    const effortRect=currentEffortControl?.rect || null;
    sliders.sort((a,b) => {
      const exactA = a.discrete && a.stepCount === 3 ? 0 : 1;
      const exactB = b.discrete && b.stepCount === 3 ? 0 : 1;
      if (exactA !== exactB) return exactA-exactB;
      if (!effortRect) return 0;
      return centerDistance(a.r,effortRect)-centerDistance(b.r,effortRect);
    });
    const primary = sliders[0] || null;

    let trackCandidates=[];
    let bestTrack=null;
    if (primary) {
      const thumb=primary.el, tr=primary.r, tc=center(tr);
      let root=thumb.parentElement;
      for (let hop=1; root && hop<=5; hop++, root=root.parentElement) {
        const nodes=[root,...Array.from(root.children || [])];
        for (const node of nodes) {
          if (!(node instanceof Element) || node===thumb || !visible(node)) continue;
          const rr=node.getBoundingClientRect();
          const horizontal=primary.orientation!=='vertical';
          const axisLength=horizontal?rr.width:rr.height;
          const crossLength=horizontal?rr.height:rr.width;
          const thumbAxis=horizontal?tr.width:tr.height;
          if (axisLength < Math.max(56, thumbAxis*2)) continue;
          const c=center(rr);
          const crossOffset=Math.abs((horizontal?c.y:c.x)-(horizontal?tc.y:tc.x));
          if (crossOffset > Math.max(32, (horizontal?tr.height:tr.width)*1.5)) continue;
          const axisContains=horizontal ? (tc.x>=rr.left-8 && tc.x<=rr.right+8) : (tc.y>=rr.top-8 && tc.y<=rr.bottom+8);
          if (!axisContains) continue;
          const mode=one(fields(node),effort), dim=one(controlFields(node),dimension);
          if (mode || dim || node.tagName==='BUTTON' || node.getAttribute('role')==='button') continue;
          const thinness=axisLength/Math.max(1,crossLength);
          const score=(hop*100)+(crossOffset*5)-Math.min(80,thinness*4)-Math.min(80,axisLength/4);
          trackCandidates.push({node,hop,score,record:{tag:node.tagName,role:node.getAttribute('role')||null,rect:rect(node),relationToThumb:relation(node,thumb),axisLengthPx:Math.round(axisLength),crossLengthPx:Math.round(crossLength),crossOffsetPx:Math.round(crossOffset),thumbCenterInsideAxis:true}});
        }
      }
      trackCandidates.sort((a,b)=>a.score-b.score);
      if (trackCandidates.length) bestTrack=trackCandidates[0];
    }

    const minimalLabels=Array.from(document.querySelectorAll('*')).filter(visible).map((el)=>({el,mode:one(fields(el),effort)})).filter((x)=>x.mode).filter((item,_,all)=>!all.some((other)=>other!==item&&item.el.contains(other.el)&&other.mode===item.mode));
    const labels=[];
    if (primary) {
      const tr=primary.r, trackRect=bestTrack?.node?.getBoundingClientRect() || null;
      for (const item of minimalLabels) {
        const lr=item.el.getBoundingClientRect();
        const d=centerDistance(lr,trackRect || tr);
        if (d > 240) continue;
        let normalizedPosition=null;
        if (trackRect) {
          const horizontal=primary.orientation!=='vertical';
          const axisStart=horizontal?trackRect.left:trackRect.top;
          const axisLength=Math.max(1,horizontal?trackRect.width:trackRect.height);
          const labelCenter=horizontal?(lr.left+lr.width/2):(lr.top+lr.height/2);
          normalizedPosition=Math.max(0,Math.min(1,(labelCenter-axisStart)/axisLength));
          normalizedPosition=Math.round(normalizedPosition*1000)/1000;
        }
        labels.push({mode:item.mode,tag:item.el.tagName,role:item.el.getAttribute('role')||null,rect:rect(item.el),distanceToTrackPx:Math.round(d),normalizedPosition});
      }
    }
    labels.sort((a,b)=>(a.normalizedPosition??9)-(b.normalizedPosition??9));
    const uniqueModes=Array.from(new Set(labels.map((x)=>x.mode)));
    const ariaRange = primary ? {min:primary.min,max:primary.max,now:primary.now,discrete:primary.discrete,stepCount:primary.stepCount,currentStepIndex:primary.discrete&&Number.isInteger(primary.now)?primary.now-primary.min:null} : null;
    let orderedStepMapping=[];
    if (primary && bestTrack && primary.discrete && uniqueModes.length===3) {
      const byMode=[];
      for (const mode of ['INSTANT','MEDIUM','HIGH']) {
        const candidates=labels.filter((x)=>x.mode===mode&&x.normalizedPosition!==null).sort((a,b)=>a.distanceToTrackPx-b.distanceToTrackPx);
        if (candidates.length) byMode.push(candidates[0]);
      }
      byMode.sort((a,b)=>a.normalizedPosition-b.normalizedPosition);
      if (byMode.length===3) orderedStepMapping=byMode.map((x,rank)=>({mode:x.mode,rank,ariaStepCandidate:primary.min+rank,normalizedPosition:x.normalizedPosition}));
    }
    const currentMode=currentEffortControl?.mode || null;
    const currentStepConsistent=Boolean(primary&&primary.discrete&&currentMode==='HIGH'&&primary.now===primary.max);
    const fullMappingProven=orderedStepMapping.length===3&&orderedStepMapping.map((x)=>x.mode).join(',')==='INSTANT,MEDIUM,HIGH'&&currentStepConsistent;

    const advancedNodes=Array.from(document.querySelectorAll('button,[role="button"],div')).filter(visible).map((el)=>({el,dimension:one(controlFields(el),dimension)})).filter((x)=>x.dimension==='ADVANCED').map((x,index)=>{
      const r=x.el.getBoundingClientRect();
      const actionable=x.el.tagName==='BUTTON'||x.el.getAttribute('role')==='button';
      return {index,el:x.el,r,record:{index,tag:x.el.tagName,role:x.el.getAttribute('role')||null,rect:rect(x.el),actionable,disabled:Boolean(x.el.disabled===true||x.el.getAttribute('aria-disabled')==='true'),pointerEventsEnabled:getComputedStyle(x.el).pointerEvents!=='none'}};
    });
    const parent=advancedNodes.map((_,i)=>i);
    const find=(i)=>parent[i]===i?i:(parent[i]=find(parent[i]));
    const unite=(a,b)=>{a=find(a);b=find(b);if(a!==b)parent[b]=a;};
    for(let i=0;i<advancedNodes.length;i++) for(let j=i+1;j<advancedNodes.length;j++) {
      const a=advancedNodes[i],b=advancedNodes[j];
      const equivalent=a.el.contains(b.el)||b.el.contains(a.el)||overlapRatio(a.r,b.r)>=0.85||centerDistance(a.r,b.r)<=4;
      if(equivalent) unite(i,j);
    }
    const groups=new Map();
    advancedNodes.forEach((item,i)=>{const root=find(i);if(!groups.has(root))groups.set(root,[]);groups.get(root).push(item);});
    const logicalGroups=Array.from(groups.values()).map((items,index)=>{
      const actionables=items.filter((x)=>x.record.actionable&&x.record.pointerEventsEnabled&&!x.record.disabled);
      actionables.sort((a,b)=>(a.r.width*a.r.height)-(b.r.width*b.r.height));
      const preferred=actionables[0] || null;
      return {index,candidateCount:items.length,candidates:items.map((x)=>x.record),actionableCandidateCount:actionables.length,preferredTarget:preferred?preferred.record:null};
    });

    return {
      currentEffortControl,
      sliderCandidateCount:sliders.length,
      primarySlider:primary?{tag:primary.el.tagName,role:primary.el.getAttribute('role')||null,rect:rect(primary.el),orientation:primary.orientation,ariaValueMin:primary.min,ariaValueMax:primary.max,ariaValueNow:primary.now,discrete:primary.discrete,stepCount:primary.stepCount}:null,
      thumbGeometryProven:Boolean(primary && Math.max(primary.r.width,primary.r.height)<=40),
      ariaRangeSemantics:ariaRange,
      trackCandidateCount:trackCandidates.length,
      trackCandidates:trackCandidates.slice(0,12).map((x)=>x.record),
      bestTrack:bestTrack?bestTrack.record:null,
      effortLabels:labels.slice(0,16),
      recognizedEffortModes:Array.from(new Set(labels.map((x)=>x.mode))).sort(),
      orderedStepMapping,
      currentStepConsistent,
      fullThreeStepMappingProven:fullMappingProven,
      advancedDomCandidateCount:advancedNodes.length,
      advancedLogicalControlCount:logicalGroups.length,
      advancedLogicalControls:logicalGroups.slice(0,8),
      advancedDealiased:Boolean(advancedNodes.length>1&&logicalGroups.length===1&&logicalGroups[0].preferredTarget),
      selectionControlClickPerformed:false,
      uiNavigationClickPerformed:false
    };
  })()`;
}

async function _pr88EffortGeometryProbe(message) {
  if (_pr88EffortGeometryConflict(message)) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_FLAG_CONFLICT");
  const conversationId=_pr88EffortGeometryConversationId(message?.conversationId);
  if (!conversationId) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_CONVERSATION_REQUIRED");
  const expectedTabId=Number.isInteger(message?.expectedRuntimeTabId)?message.expectedRuntimeTabId:null;
  const runtimeTabId=await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_RUNTIME_TAB_REQUIRED");
  if (expectedTabId!==null&&runtimeTabId!==expectedTabId) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_RUNTIME_TAB_CHANGED");
  const tab=await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url||"")||conversationIdFromUrl(tab?.url||"")!==conversationId) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_CONVERSATION_MISMATCH");
  const leasePresent=typeof _pr88StoredLeaseId==="function"?Boolean(await _pr88StoredLeaseId()):null;
  const debuggee={tabId:runtimeTabId};
  let attached=false;
  try {
    await chrome.debugger.attach(debuggee,"1.3");
    attached=true;
    const result=await chrome.debugger.sendCommand(debuggee,"Runtime.evaluate",{expression:_pr88EffortGeometryExpression(),returnByValue:true,awaitPromise:true});
    const topology=result?.result?.value;
    if (!topology||typeof topology!=="object") throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_RESULT_MISSING");
    return {
      reasoningEffortGeometrySupported:true,
      reasoningEffortGeometrySchemaVersion:PR88_REASONING_EFFORT_GEOMETRY_SCHEMA_VERSION,
      conversationId,runtimeTabId,runtimeTabIdAfter:runtimeTabId,leaseIdPresent:leasePresent,
      rawUrlExported:false,rawTextExported:false,rawHtmlExported:false,leaseIdExported:false,
      zeroProductWrites:true,conversationWriteCount:0,chatgptMutationCount:0,automaticRetry:false,
      topology
    };
  } finally {
    if (attached) { try { await chrome.debugger.detach(debuggee); } catch {} }
  }
}

executeNativeTurn = async function _executeNativeTurnWithReasoningEffortGeometry(message) {
  if (message?.characterizeReasoningEffortGeometrySupport === true) {
    if (_pr88EffortGeometryConflict(message)) throw new Error("PR8_8_REASONING_EFFORT_GEOMETRY_SUPPORT_FLAG_CONFLICT");
    return {
      reasoningEffortGeometrySupported:true,
      reasoningEffortGeometrySchemaVersion:PR88_REASONING_EFFORT_GEOMETRY_SCHEMA_VERSION,
      thumbTrackSeparationSupported:true,
      ariaDiscreteRangeSemanticsSupported:true,
      siblingTickAssociationSupported:true,
      advancedControlDealiasingSupported:true,
      retainedExistingTabProbeSupported:true,
      selectionControlClickForbidden:true,
      uiNavigationClickForbidden:true,
      zeroProductWrites:true,
      automaticRetry:false,
      rawTextRedactionSupported:true,
      leaseIdExported:false
    };
  }
  if (message?.characterizeReasoningEffortGeometry === true) return _pr88EffortGeometryProbe(message);
  return _pr88EffortGeometryPriorExecuteNativeTurn(message);
};
