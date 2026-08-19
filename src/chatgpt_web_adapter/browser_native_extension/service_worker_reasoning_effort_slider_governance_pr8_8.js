// PR8.8 retained-tab reasoning-effort slider characterization.
// Zero product writes. Optional UI navigation is limited to opening the quick
// effort picker and opening Advanced; no slider/model/effort choice is clicked.

const _pr88EffortPriorExecuteNativeTurn = executeNativeTurn;

function _pr88EffortConversationId(value) {
  const id = typeof value === "string" ? value.trim() : "";
  return id && !/[\/?#]/.test(id) ? id : null;
}

function _pr88EffortConflict(message) {
  return message?.text != null || message?.browserAuthorityLeaseId != null || message?.canonicalCompleted === true;
}

async function _pr88EffortRawClick(debuggee, record) {
  const r = record?.rect;
  if (!r || !Number.isFinite(r.x) || !Number.isFinite(r.y) || !Number.isFinite(r.width) || !Number.isFinite(r.height)) {
    throw new Error("PR8_8_REASONING_EFFORT_CLICK_TARGET_REQUIRED");
  }
  const x = r.x + r.width / 2;
  const y = r.y + r.height / 2;
  for (const payload of [
    {type:"mouseMoved",x,y},
    {type:"mousePressed",x,y,button:"left",buttons:1,clickCount:1},
    {type:"mouseReleased",x,y,button:"left",buttons:0,clickCount:1}
  ]) {
    await chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", payload);
  }
}

async function _pr88EffortWait(debuggee, kind, predicate, timeoutMs = 2500) {
  const started = performance.now();
  let last = {};
  while (performance.now() - started < timeoutMs) {
    last = await _pr88EffortEvaluate(debuggee, kind);
    if (predicate(last)) return last;
    await sleep(100);
  }
  return last;
}

async function _pr88EffortProbe(message) {
  if (_pr88EffortConflict(message)) throw new Error("PR8_8_REASONING_EFFORT_FLAG_CONFLICT");
  const conversationId = _pr88EffortConversationId(message?.conversationId);
  if (!conversationId) throw new Error("PR8_8_REASONING_EFFORT_CONVERSATION_REQUIRED");
  const expectedTabId = Number.isInteger(message?.expectedRuntimeTabId) ? message.expectedRuntimeTabId : null;
  const openQuick = message?.openQuickPicker === true;
  const inspectAdvanced = message?.inspectAdvancedSurface === true;
  const allowNavigation = message?.allowUiNavigation === true;
  if ((openQuick || inspectAdvanced) && !allowNavigation) throw new Error("PR8_8_REASONING_EFFORT_UI_NAVIGATION_NOT_ACKNOWLEDGED");

  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) throw new Error("PR8_8_REASONING_EFFORT_RUNTIME_TAB_REQUIRED");
  if (expectedTabId !== null && runtimeTabId !== expectedTabId) throw new Error("PR8_8_REASONING_EFFORT_RUNTIME_TAB_CHANGED");
  const tabBefore = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tabBefore?.url || "") || conversationIdFromUrl(tabBefore?.url || "") !== conversationId) {
    throw new Error("PR8_8_REASONING_EFFORT_CONVERSATION_MISMATCH");
  }

  const leasePresent = typeof _pr88StoredLeaseId === "function" ? Boolean(await _pr88StoredLeaseId()) : null;
  const debuggee = {tabId: runtimeTabId};
  let attached = false;
  let conversationWriteCount = 0;
  let chatgptMutationCount = 0;
  let quickOpenClickPerformed = false;
  let advancedClickPerformed = false;
  const onEvent = (source, method, params) => {
    if (source?.tabId !== runtimeTabId || method !== "Network.requestWillBeSent") return;
    const req = params?.request;
    if (isConversationWrite(req?.url || "", req?.method || "")) conversationWriteCount += 1;
    try {
      const u = new URL(req?.url || "");
      const m = String(req?.method || "").toUpperCase();
      if (u.origin === CHATGPT_ORIGIN && ["POST","PUT","PATCH","DELETE"].includes(m) && !isConversationWrite(req?.url || "", req?.method || "")) chatgptMutationCount += 1;
    } catch {}
  };

  try {
    await chrome.debugger.attach(debuggee, "1.3");
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Network.enable");
    chrome.debugger.onEvent.addListener(onEvent);

    const beforeQuick = await _pr88EffortEvaluate(debuggee, "quick");
    let quick = beforeQuick;
    if (quick?.surfaceFound !== true && openQuick) {
      if (quick?.currentEffortCandidateCount !== 1 || !quick?.currentEffortControl) {
        throw new Error("PR8_8_REASONING_EFFORT_CURRENT_CONTROL_NOT_UNIQUE");
      }
      await _pr88EffortRawClick(debuggee, quick.currentEffortControl);
      quickOpenClickPerformed = true;
      quick = await _pr88EffortWait(debuggee, "quick", (x) => x?.surfaceFound === true && (x?.sliders?.length || x?.completeThreeStepMapping === true));
    }

    let advanced = null;
    if (inspectAdvanced) {
      if (quick?.surfaceFound !== true) throw new Error("PR8_8_REASONING_EFFORT_QUICK_SURFACE_REQUIRED");
      if (quick?.advancedButtonCount !== 1 || !quick?.advancedButton) throw new Error("PR8_8_REASONING_EFFORT_ADVANCED_CONTROL_NOT_UNIQUE");
      await _pr88EffortRawClick(debuggee, quick.advancedButton);
      advancedClickPerformed = true;
      advanced = await _pr88EffortWait(debuggee, "advanced", (x) => x?.surfaceFound === true && x?.modelControlCount === 1 && x?.effortControlCount === 1);
    }

    if (conversationWriteCount !== 0) throw new Error("PR8_8_REASONING_EFFORT_ZERO_WRITE_BOUNDARY_VIOLATED");
    const tabAfter = await chrome.tabs.get(runtimeTabId);
    if (!isChatGPTUrl(tabAfter?.url || "") || conversationIdFromUrl(tabAfter?.url || "") !== conversationId) {
      throw new Error("PR8_8_REASONING_EFFORT_ROUTE_CHANGED");
    }
    return {
      reasoningEffortSliderSupported: true,
      reasoningEffortSliderSchemaVersion: PR88_REASONING_EFFORT_SLIDER_SCHEMA_VERSION,
      conversationId,
      runtimeTabId,
      runtimeTabIdAfter: runtimeTabId,
      leaseIdPresent: leasePresent,
      rawUrlExported: false,
      rawTextExported: false,
      rawHtmlExported: false,
      leaseIdExported: false,
      zeroProductWrites: true,
      conversationWriteCount,
      chatgptMutationCount,
      uiNavigationAcknowledged: allowNavigation,
      quickOpenClickPerformed,
      advancedClickPerformed,
      selectionControlClickPerformed: false,
      quickTopology: quick,
      advancedTopology: advanced
    };
  } finally {
    try { chrome.debugger.onEvent.removeListener(onEvent); } catch {}
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

executeNativeTurn = async function _executeNativeTurnWithReasoningEffortSlider(message) {
  if (message?.characterizeReasoningEffortSliderSupport === true) {
    if (_pr88EffortConflict(message)) throw new Error("PR8_8_REASONING_EFFORT_SUPPORT_FLAG_CONFLICT");
    return {
      reasoningEffortSliderSupported: true,
      reasoningEffortSliderSchemaVersion: PR88_REASONING_EFFORT_SLIDER_SCHEMA_VERSION,
      retainedExistingTabProbeSupported: true,
      sliderTopologySupported: true,
      discreteStepMappingSupported: true,
      quickAdvancedDimensionSeparationSupported: true,
      uiNavigationOptInSupported: true,
      selectionControlClickForbidden: true,
      conversationWriteGuardSupported: true,
      rawTextRedactionSupported: true,
      leaseIdExported: false,
      zeroProductWrites: true,
      automaticRetry: false
    };
  }
  if (message?.characterizeReasoningEffortSliderTopology === true) return _pr88EffortProbe(message);
  return _pr88EffortPriorExecuteNativeTurn(message);
};
