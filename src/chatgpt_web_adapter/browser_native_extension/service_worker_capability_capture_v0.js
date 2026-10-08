// Research-only observational capture. This file is NOT part of a shipped
// capability and must not be merged without separate live privacy/authority gates.
const CWA_CAPTURE_V0_OPERATION = "research_capture_translate_demo_v0";
const CWA_CAPTURE_V0_SEMANTIC_OPERATION = "research_capture_translate_semantic_v0";
const CWA_CAPTURE_V0_ORIGIN = "https://translate.google.com";

function _cwaCaptureV0PageExpression(mode) {
  const prefix = "(() => {";
  const suffix = "})()";
  if (mode === "install") {
    return prefix +
      "const key='__cwaResearchCaptureV0';" +
      "if(window[key])return {ready:false,reason:'ALREADY_INSTALLED'};" +
      "const visible=e=>{const r=e.getBoundingClientRect();" +
      "const s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};" +
      "const fields=Array.from(document.querySelectorAll('textarea,[contenteditable=\"true\"][role=\"textbox\"]')).filter(visible);" +
      "fields.sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left);" +
      "const source=fields[0];if(!source)return {ready:false,reason:'SOURCE_MISSING'};" +
      "const value=source instanceof HTMLTextAreaElement?source.value:(source.textContent||'');" +
      "if(value.trim())return {ready:false,reason:'SOURCE_NOT_EMPTY'};" +
      "const results=Array.from(document.querySelectorAll('[jsname=\"W297wb\"],[jsname=\"jqKxS\"]')).filter(visible);" +
      "const leaves=results.filter(e=>!results.some(x=>x!==e&&e.contains(x)));" +
      "if(leaves.some(e=>Boolean((e.textContent||'').trim())))return {ready:false,reason:'RESULT_NOT_CLEARED'};" +
      "let count=0;" +
      "const listener=e=>{if(e.target===source)count=Math.min(65,count+1)};" +
      "document.addEventListener('input',listener,true);" +
      "window[key]={read:()=>count,stop:()=>document.removeEventListener('input',listener,true)};" +
      "return {ready:true,sourceRole:'textbox',sourceControl:'visible_leftmost_input'};" + suffix;
  }
  if (mode === "observe") {
    return prefix +
      "const key='__cwaResearchCaptureV0';" +
      "const state=window[key];if(!state)return {ready:false};" +
      "const visible=e=>{const r=e.getBoundingClientRect();" +
      "const s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};" +
      "const nodes=Array.from(document.querySelectorAll('[jsname=\"W297wb\"],[jsname=\"jqKxS\"]')).filter(visible);" +
      "const leaves=nodes.filter(e=>!nodes.some(x=>x!==e&&e.contains(x)));" +
      "const present=leaves.filter(e=>Boolean((e.textContent||'').trim()));" +
      "const url=new URL(location.href);" +
      "return {ready:true,inputEvents:state.read(),candidateCount:present.length," +
      "candidateIdentityResolved:present.length===1,originMatches:url.origin==='https://translate.google.com'," +
      "sourceRoute:url.searchParams.get('sl'),targetRoute:url.searchParams.get('tl')};" + suffix;
  }
  if (mode === "remove") {
    return prefix +
      "const key='__cwaResearchCaptureV0';const state=window[key];" +
      "if(state&&typeof state.stop==='function')state.stop();" +
      "delete window[key];return {removed:true};" + suffix;
  }
  throw new Error("CAPTURE_V0_INVALID_EVALUATION_MODE");
}

async function _cwaCaptureV0Evaluate(debuggee, mode) {
  const response = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression: _cwaCaptureV0PageExpression(mode),
    returnByValue: true,
    awaitPromise: true
  });
  if (response?.exceptionDetails) throw new Error("CAPTURE_V0_PAGE_EVALUATION_FAILED");
  return response?.result?.value;
}

async function _cwaCaptureV0ObserveTranslate(message) {
  const tabId = message?.tabId;
  const seconds = message?.captureSeconds;
  const source = message?.sourceLanguage;
  const target = message?.targetLanguage;
  if (!Number.isInteger(tabId) || tabId <= 0 ||
      !Number.isInteger(seconds) || seconds < 3 || seconds > 20 ||
      typeof source !== "string" || !/^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(source) ||
      typeof target !== "string" || !/^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(target)) {
    throw new Error("CAPTURE_V0_INVALID_REQUEST");
  }
  if (message?.consent !== "EXPLICIT_OBSERVE_ONLY") {
    throw new Error("CAPTURE_V0_EXPLICIT_CONSENT_REQUIRED");
  }
  const tab = await chrome.tabs.get(tabId);
  const initialUrl = new URL(tab?.url || "");
  if (initialUrl.origin !== CWA_CAPTURE_V0_ORIGIN ||
      initialUrl.searchParams.get("sl") !== source ||
      initialUrl.searchParams.get("tl") !== target) {
    throw new Error("CAPTURE_V0_TAB_ROUTE_MISMATCH");
  }

  const debuggee = { tabId };
  let attached = false;
  let installAttempted = false;
  const events = [];
  const start = performance.now();
  let lastInput = 0;
  let lastResult = false;
  let candidateEverSeen = false;
  let resultSince = null;
  let stable = false;
  let resolved = false;
  let routeValid = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    installAttempted = true;
    const setup = await _cwaCaptureV0Evaluate(debuggee, "install");
    if (setup?.ready !== true) {
      throw new Error("CAPTURE_V0_" + String(setup?.reason || "NOT_READY"));
    }
    events.push({ phase: "source_ready", t_ms: 0, role: "textbox" });
    const deadline = start + seconds * 1000;
    while (performance.now() < deadline) {
      const snapshot = await _cwaCaptureV0Evaluate(debuggee, "observe");
      if (snapshot?.ready !== true) throw new Error("CAPTURE_V0_OBSERVER_MISSING");
      routeValid =
        snapshot.originMatches === true &&
        snapshot.sourceRoute === source &&
        snapshot.targetRoute === target;
      if (!routeValid) throw new Error("CAPTURE_V0_ROUTE_DRIFT");
      const inputCount = snapshot.inputEvents;
      if (!Number.isInteger(inputCount) || inputCount < lastInput || inputCount > 64) {
        throw new Error("CAPTURE_V0_INPUT_COUNTER_INVALID");
      }
      if (inputCount > lastInput) {
        if (lastInput === 0) {
          events.push({ phase: "source_input_event", t_ms: Math.round(performance.now() - start) });
        }
        lastInput = inputCount;
      }
      const oneResult = inputCount > 0 &&
        snapshot.candidateIdentityResolved === true &&
        snapshot.candidateCount === 1;
      if (oneResult && !lastResult) {
        resultSince = performance.now();
        if (!candidateEverSeen) {
          events.push({ phase: "result_candidate_seen", t_ms: Math.round(performance.now() - start) });
          candidateEverSeen = true;
        }
      } else if (!oneResult) {
        resultSince = null;
        stable = false;
      }
      lastResult = oneResult;
      if (oneResult && resultSince !== null && performance.now() - resultSince >= 1200) {
        stable = true;
        resolved = true;
        events.push({ phase: "result_candidate_presence_stable", t_ms: Math.round(performance.now() - start) });
        break;
      }
      await sleep(150);
    }
    return {
      schema: "CWA_CAPTURE_V0_STRUCTURAL_TRACE",
      productId: "google-translate-web",
      captureMode: "EXPLICIT_OBSERVE_ONLY",
      observedTabId: tabId,
      sourceLanguage: source,
      targetLanguage: target,
      events,
      inputEventCount: lastInput,
      routeVerified: routeValid,
      candidatePresenceStable: stable,
      candidateIdentityResolved: resolved,
      canonicalCompletionProven: false,
      semanticFinalityProven: false,
      effectBoundary: "MANUAL_REFERENCE_ONLY_SOURCE_INPUT",
      automaticRetry: false,
      replayExecutable: false,
      rawContentRetained: false
    };
  } finally {
    let cleanupUnproven = false;
    if (attached) {
      if (installAttempted) {
        try {
          const removed = await _cwaCaptureV0Evaluate(debuggee, "remove");
          if (removed?.removed !== true) cleanupUnproven = true;
        } catch {
          cleanupUnproven = true;
        }
      }
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        cleanupUnproven = true;
      }
    }
    if (cleanupUnproven) throw new Error("CAPTURE_V0_CLEANUP_UNPROVEN");
  }
}

let _cwaCaptureV0Active = false;
async function _cwaOnNativeMessageWithCaptureV0(message, port, next) {
  const semantic = message?.type === CWA_CAPTURE_V0_SEMANTIC_OPERATION;
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
      (!semantic && message?.type !== CWA_CAPTURE_V0_OPERATION)) {
    return next(message, port);
  }
  const responseType = semantic
    ? "research_capture_translate_semantic_v0_result"
    : "research_capture_translate_demo_v0_result";
  const requestId = message?.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (_cwaCaptureV0Active) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: responseType,
      request_id: requestId,
      ok: false,
      error: "CAPTURE_V0_BUSY"
    });
    return;
  }
  _cwaCaptureV0Active = true;
  try {
    const result = semantic
      ? await _cwaCaptureV0SemanticTwoTabs(message)
      : await _cwaCaptureV0ObserveTranslate(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: responseType,
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: responseType,
      request_id: requestId,
      ok: false,
      error: semantic
        ? (error instanceof Error && error.message.startsWith("CAPTURE_C1_")
          ? error.message : "CAPTURE_C1_OBSERVATION_FAILED")
        : (error instanceof Error ? error.message : "CAPTURE_V0_UNKNOWN_FAILURE")
    });
  } finally {
    _cwaCaptureV0Active = false;
  }
}


// C1 research extension — separate two-document structural observation.
// There is no product write in this path. The product-specific candidate
// families are imported from the hand-written Translate reference; they are
// NOT learned from the original human demonstration.
function _cwaCaptureV0SemanticPageExpression(source, target) {
  const src = JSON.stringify(source);
  const dst = JSON.stringify(target);
  return "(() => {" +
    "const visible=e=>{const r=e.getBoundingClientRect();" +
      "const s=getComputedStyle(e);" +
      "return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};" +
    "const region=e=>{const w=document.documentElement.clientWidth;" +
      "if(!(w>0))return 'unknown';" +
      "const r=e.getBoundingClientRect();const x=(r.left+r.width/2)/w;" +
      "return x<1/3?'left':(x<2/3?'center':'right')};" +
    "const source=Array.from(document.querySelectorAll('textarea,[contenteditable=\\\"true\\\"][role=\\\"textbox\\\"]'))" +
      ".filter(e=>visible(e)&&e.getAttribute('aria-disabled')!=='true'&&!e.disabled);" +
    "const rawOutputs=Array.from(document.querySelectorAll('[jsname=\\\"W297wb\\\"],[jsname=\\\"jqKxS\\\"]'));" +
    "const outputs=rawOutputs.filter(visible);" +
    "const leaves=outputs.filter(e=>!outputs.some(x=>x!==e&&e.contains(x)));" +
    "const resultFamilyStages={rawFamily:rawOutputs.length,visibleFamily:outputs.length,visibleLeaves:leaves.length};" +
    "const pack=(nodes,slot)=>{" +
      "if(nodes.length>8)return {candidateCount:9,uniqueDescriptor:null};" +
      "if(nodes.length!==1)return {candidateCount:nodes.length,uniqueDescriptor:null};" +
      "const e=nodes[0];const tag=(e.tagName||'').toLowerCase();" +
      "const kind=slot==='source_input'?(tag==='textarea'?'textarea':'contenteditable'):" +
        "(tag==='span'?'span':tag==='div'?'div':'other');" +
      "return {candidateCount:1,uniqueDescriptor:{" +
        "role:slot==='source_input'?'textbox':'result_leaf',kind,region:region(e)," +
        "interactable:slot==='source_input'}}};" +
    "const u=new URL(location.href);" +
    "return {routeVerified:u.origin==='https://translate.google.com'&&" +
      "u.searchParams.get('sl')===" + src + "&&u.searchParams.get('tl')===" + dst + "," +
      "source_input:pack(source,'source_input')," +
      "translated_result:pack(leaves,'translated_result')," +
      "resultFamilyStages};" +
  "})()";
}

async function _cwaCaptureV0SemanticReadTab(tabId, source, target) {
  const tab = await chrome.tabs.get(tabId);
  let url;
  try { url = new URL(tab?.url || ""); } catch {
    throw new Error("CAPTURE_C1_TAB_ROUTE_MISMATCH");
  }
  if (url.origin !== CWA_CAPTURE_V0_ORIGIN ||
      url.searchParams.get("sl") !== source ||
      url.searchParams.get("tl") !== target) {
    throw new Error("CAPTURE_C1_TAB_ROUTE_MISMATCH");
  }
  const debuggee = { tabId };
  let attached = false;
  let detached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    const response = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
      expression: _cwaCaptureV0SemanticPageExpression(source, target),
      returnByValue: true,
      awaitPromise: true
    });
    if (response?.exceptionDetails || !response?.result?.value) {
      throw new Error("CAPTURE_C1_PAGE_EVALUATION_FAILED");
    }
    const snapshot = response.result.value;
    if (snapshot.routeVerified !== true) {
      throw new Error("CAPTURE_C1_ROUTE_DRIFT");
    }
    const after = await chrome.tabs.get(tabId);
    let afterUrl;
    try { afterUrl = new URL(after?.url || ""); } catch {
      throw new Error("CAPTURE_C1_ROUTE_DRIFT");
    }
    if (afterUrl.origin !== CWA_CAPTURE_V0_ORIGIN ||
        afterUrl.searchParams.get("sl") !== source ||
        afterUrl.searchParams.get("tl") !== target) {
      throw new Error("CAPTURE_C1_ROUTE_DRIFT");
    }
    // Copy only closed-enum structural fields. No page text, attribute names,
    // DOM selectors, raw URLs, node IDs or CDP response objects are exported.
    const rawStages = snapshot.resultFamilyStages;
    const names = ["rawFamily", "visibleFamily", "visibleLeaves"];
    if (!rawStages || typeof rawStages !== "object" ||
        names.some(name => !Number.isSafeInteger(rawStages[name]) ||
          rawStages[name] < 0 || rawStages[name] > 8) ||
        rawStages.rawFamily < rawStages.visibleFamily ||
        rawStages.visibleFamily < rawStages.visibleLeaves ||
        rawStages.visibleLeaves !== snapshot.translated_result?.candidateCount) {
      throw new Error("CAPTURE_C1_RESULT_STAGE_EVIDENCE_INVALID");
    }
    const sanitized = {
      routeVerified: true,
      // Closed, capped counts only. No DOM element/content/attribute value.
      resultFamilyStages: {
        rawFamily: rawStages.rawFamily,
        visibleFamily: rawStages.visibleFamily,
        visibleLeaves: rawStages.visibleLeaves
      }
    };
    for (const slot of ["source_input", "translated_result"]) {
      const value = snapshot[slot];
      const count = value?.candidateCount;
      if (!Number.isInteger(count) || count < 0 || count > 8) {
        throw new Error("CAPTURE_C1_CANDIDATE_COUNT_INVALID");
      }
      const desc = count === 1 ? value?.uniqueDescriptor : null;
      if (count === 1 && (!desc || typeof desc !== "object")) {
        throw new Error("CAPTURE_C1_UNIQUE_DESCRIPTOR_MISSING");
      }
      sanitized[slot] = {
        candidateCount: count,
        uniqueDescriptor: count === 1 ? {
          role: desc.role,
          kind: desc.kind,
          region: desc.region,
          interactable: desc.interactable
        } : null
      };
    }
    return sanitized;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
        detached = true;
      } catch {
        // The inability to prove detach fails the observation closed.
      }
      if (!detached) throw new Error("CAPTURE_C1_CLEANUP_UNPROVEN");
    }
  }
}

async function _cwaCaptureV0SemanticTwoTabs(message) {
  const ids = message?.tabIds;
  const source = message?.sourceLanguage;
  const target = message?.targetLanguage;
  if (!Array.isArray(ids) || ids.length !== 2 ||
      !ids.every(id=>Number.isSafeInteger(id)&&id>0) ||
      ids[0] === ids[1] ||
      typeof source !== "string" || !/^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(source) ||
      typeof target !== "string" || !/^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(target)) {
    throw new Error("CAPTURE_C1_INVALID_REQUEST");
  }
  if (message?.consent !== "EXPLICIT_TWO_TAB_OBSERVE_ONLY") {
    throw new Error("CAPTURE_C1_CONSENT_REQUIRED");
  }
  // Serial observation, never parallel debugger attachment. Distinct tabs
  // demonstrate separate documents, not separate renderer OS processes.
  const first = await _cwaCaptureV0SemanticReadTab(ids[0], source, target);
  const second = await _cwaCaptureV0SemanticReadTab(ids[1], source, target);
  return {
    schema: "CWA_CAPTURE_C1_TWO_DOCUMENT_STRUCTURE_V2",
    productId: "google-translate-web",
    captureMode: "EXPLICIT_TWO_TAB_OBSERVE_ONLY",
    sourceLanguage: source,
    targetLanguage: target,
    observations: [first, second],
    selectorProvenance: "HANDWRITTEN_REFERENCE_FAMILIES_NOT_LEARNED",
    semanticFinalityProven: false,
    canonicalCompletionProven: false,
    replayExecutable: false,
    newWriteAuthority: false,
    automaticRetry: false,
    rawContentRetained: false
  };
}
