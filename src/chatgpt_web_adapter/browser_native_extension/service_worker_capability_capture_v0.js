// Research-only observational capture. This file is NOT part of a shipped
// capability and must not be merged without separate live privacy/authority gates.
const CWA_CAPTURE_V0_OPERATION = "research_capture_translate_demo_v0";
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
      "let count=0;" +
      "const listener=e=>{if(e.target===source)count=Math.min(64,count+1)};" +
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
  let installed = false;
  const events = [];
  const start = performance.now();
  let lastInput = 0;
  let lastResult = false;
  let resultSince = null;
  let stable = false;
  let resolved = false;
  let routeValid = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    const setup = await _cwaCaptureV0Evaluate(debuggee, "install");
    if (setup?.ready !== true) {
      throw new Error("CAPTURE_V0_" + String(setup?.reason || "NOT_READY"));
    }
    installed = true;
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
        events.push({ phase: "result_candidate_seen", t_ms: Math.round(performance.now() - start) });
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
    if (attached) {
      if (installed) {
        try { await _cwaCaptureV0Evaluate(debuggee, "remove"); } catch {
          // Cleanup failure does not upgrade evidence/finality.
        }
      }
      try { await chrome.debugger.detach(debuggee); } catch {
        // Best effort; cannot override observational result.
      }
    }
  }
}

let _cwaCaptureV0Active = false;
async function _cwaOnNativeMessageWithCaptureV0(message, port, next) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
      message?.type !== CWA_CAPTURE_V0_OPERATION) {
    return next(message, port);
  }
  const requestId = message?.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (_cwaCaptureV0Active) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_translate_demo_v0_result",
      request_id: requestId,
      ok: false,
      error: "CAPTURE_V0_BUSY"
    });
    return;
  }
  _cwaCaptureV0Active = true;
  try {
    const result = await _cwaCaptureV0ObserveTranslate(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_translate_demo_v0_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_translate_demo_v0_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : "CAPTURE_V0_UNKNOWN_FAILURE"
    });
  } finally {
    _cwaCaptureV0Active = false;
  }
}
