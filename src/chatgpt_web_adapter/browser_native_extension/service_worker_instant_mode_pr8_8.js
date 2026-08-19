// PR8.8 Instant-mode observability and no-reasoning route characterization.
//
// This layer never selects a model and never changes ChatGPT settings. A
// read-only preflight may open the exact durable conversation in the dedicated
// background runtime tab, inspect the composer-local selected model control,
// and close that tab again before any product write. Ordinary product writes
// use the already-proven page-owned route. During those writes we retain only
// bounded, normalized model/reasoning metadata derived browser-locally from
// the conversation request/response. Prompt text, assistant text, raw DOM, raw
// request bodies, raw SSE, cookies, and auth material never leave this worker.

const PR88_INSTANT_MODE_SCHEMA_VERSION = 1;
const PR88_INSTANT_MODE_STORAGE_KEY = "browserAuthorityLastInstantModeV1";
const PR88_INSTANT_PROBE_TIMEOUT_MS = 15_000;
const PR88_INSTANT_MODE_SNAPSHOT_POLL_MS = 200;

const _pr88InstantPriorExecuteNativeTurn = executeNativeTurn;
const _pr88InstantPriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr88InstantPriorLocateAndFocusComposer = locateAndFocusComposer;
const _pr88InstantPriorExtractSafeStreamMetadata = extractSafeStreamMetadata;

let _pr88InstantContext = null;

function _pr88InstantLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88InstantConversationId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (
    !conversationId ||
    conversationId.includes("/") ||
    conversationId.includes("?") ||
    conversationId.includes("#")
  ) {
    return null;
  }
  return conversationId;
}

function _pr88InstantNormalize(value) {
  return typeof value === "string"
    ? value.trim().toLowerCase().replace(/[\s_\-]+/g, " ")
    : "";
}

function _pr88InstantSafeIdentifier(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > 96) return null;
  if (!/^[A-Za-z0-9._:+\-/ ]+$/.test(text)) return null;
  return text;
}

function _pr88InstantClassifyMode(value) {
  const text = _pr88InstantNormalize(value);
  if (!text) return null;
  if (
    text === "instant" ||
    text === "мгновенно" ||
    text.includes(" instant") ||
    text.startsWith("instant ") ||
    text.includes("-instant") ||
    text.includes("_instant")
  ) return "INSTANT";
  if (
    text === "medium" ||
    text === "средний" ||
    text.includes("thinking standard") ||
    text.includes("reasoning medium")
  ) return "MEDIUM";
  if (
    text === "extra high" ||
    text === "очень высокий" ||
    text.includes("thinking heavy") ||
    text.includes("reasoning extra high")
  ) return "EXTRA_HIGH";
  if (
    text === "high" ||
    text === "высокий" ||
    text.includes("thinking extended") ||
    text.includes("reasoning high")
  ) return "HIGH";
  if (
    text === "pro standard" ||
    text.includes("pro-standard") ||
    text.includes("pro_standard")
  ) return "PRO_STANDARD";
  if (
    text === "pro extended" ||
    text.includes("pro-extended") ||
    text.includes("pro_extended")
  ) return "PRO_EXTENDED";
  if (text === "thinking" || text.includes(" thinking")) return "REASONING_OTHER";
  if (text === "pro" || text.startsWith("pro ")) return "PRO_OTHER";
  return null;
}

function _pr88InstantReasoningState(value) {
  if (value === false) return "OFF";
  if (value === true) return "ON";
  const text = _pr88InstantNormalize(String(value ?? ""));
  if (!text) return null;
  if (["none", "off", "disabled", "false", "0", "instant"].includes(text)) {
    return "OFF";
  }
  if (["medium", "standard", "thinking", "on", "enabled", "true", "1"].includes(text)) {
    return "ON";
  }
  if (["high", "extended", "extra high", "heavy", "pro", "pro standard", "pro extended"].includes(text)) {
    return "ON";
  }
  return null;
}

function _pr88InstantNewHintAccumulator() {
  return {
    modelIdentifiers: new Set(),
    modelModes: new Set(),
    reasoningStates: new Set(),
    modelHintKeys: new Set(),
    reasoningHintKeys: new Set(),
    visitedNodes: 0
  };
}

function _pr88InstantCollectHints(value, out, depth = 0) {
  if (!value || typeof value !== "object" || depth > 8 || out.visitedNodes > 600) return;
  out.visitedNodes += 1;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 100)) {
      _pr88InstantCollectHints(item, out, depth + 1);
    }
    return;
  }

  for (const [rawKey, child] of Object.entries(value).slice(0, 160)) {
    const key = String(rawKey || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const modelKey = [
      "model", "modelslug", "modelid", "selectedmodel", "requestedmodel",
      "modelmode", "selectedmodelmode", "requestedmodelmode"
    ].includes(key);
    const reasoningKey = [
      "reasoningeffort", "reasoningmode", "reasoninglevel", "reasoning",
      "thinkingeffort", "thinkingmode", "thinkinglevel", "thinking"
    ].includes(key);

    if (modelKey && ["string", "number", "boolean"].includes(typeof child)) {
      out.modelHintKeys.add(rawKey);
      const safe = _pr88InstantSafeIdentifier(String(child));
      if (safe !== null) out.modelIdentifiers.add(safe);
      const mode = _pr88InstantClassifyMode(String(child));
      if (mode !== null) out.modelModes.add(mode);
    }
    if (reasoningKey && ["string", "number", "boolean"].includes(typeof child)) {
      out.reasoningHintKeys.add(rawKey);
      const state = _pr88InstantReasoningState(child);
      if (state !== null) out.reasoningStates.add(state);
      const mode = _pr88InstantClassifyMode(String(child));
      if (mode !== null) out.modelModes.add(mode);
    }

    const skipNestedContent = [
      "content", "parts", "text", "messages", "attachments", "files"
    ].includes(key);
    if (child && typeof child === "object" && !skipNestedContent) {
      _pr88InstantCollectHints(child, out, depth + 1);
    }
  }
}

function _pr88InstantParseRequestPostData(postData) {
  const out = _pr88InstantNewHintAccumulator();
  if (typeof postData !== "string" || !postData.trim()) return out;
  try {
    const payload = JSON.parse(postData);
    _pr88InstantCollectHints(payload, out);
  } catch {
    // Request metadata is optional observability only.
  }
  return out;
}

function _pr88InstantParseSseHints(body, base64Encoded) {
  const out = _pr88InstantNewHintAccumulator();
  if (base64Encoded || typeof body !== "string") return out;
  let parsedLines = 0;
  for (const rawLine of body.split(/\r?\n/)) {
    if (parsedLines >= 400) break;
    if (!rawLine.startsWith("data:")) continue;
    const payloadText = rawLine.slice(5).trim();
    if (!payloadText.startsWith("{") || payloadText.length > 1_000_000) continue;
    try {
      _pr88InstantCollectHints(JSON.parse(payloadText), out);
      parsedLines += 1;
    } catch {
      // Ignore partial or non-JSON SSE lines.
    }
  }
  return out;
}

function _pr88InstantMergeHints(target, source) {
  for (const value of source.modelIdentifiers) target.modelIdentifiers.add(value);
  for (const value of source.modelModes) target.modelModes.add(value);
  for (const value of source.reasoningStates) target.reasoningStates.add(value);
  for (const value of source.modelHintKeys) target.modelHintKeys.add(value);
  for (const value of source.reasoningHintKeys) target.reasoningHintKeys.add(value);
  target.visitedNodes += source.visitedNodes;
}

function _pr88InstantHintsRecord(hints) {
  return {
    modelIdentifiers: Array.from(hints.modelIdentifiers).sort().slice(0, 12),
    modelModes: Array.from(hints.modelModes).sort(),
    reasoningStates: Array.from(hints.reasoningStates).sort(),
    modelHintKeys: Array.from(hints.modelHintKeys).sort().slice(0, 20),
    reasoningHintKeys: Array.from(hints.reasoningHintKeys).sort().slice(0, 20)
  };
}

function _pr88InstantDeriveNetworkRoute(requestHints, responseHints) {
  const merged = _pr88InstantNewHintAccumulator();
  _pr88InstantMergeHints(merged, requestHints);
  _pr88InstantMergeHints(merged, responseHints);
  const modes = merged.modelModes;
  const reasoning = merged.reasoningStates;
  const reasoningModeObserved = Array.from(modes).some((mode) =>
    ["MEDIUM", "HIGH", "EXTRA_HIGH", "PRO_STANDARD", "PRO_EXTENDED", "REASONING_OTHER", "PRO_OTHER"].includes(mode)
  );
  const reasoningPositive = reasoning.has("ON") || reasoningModeObserved;
  const instantPositive = modes.has("INSTANT");
  const reasoningOff = reasoning.has("OFF");

  let status = "INCONCLUSIVE";
  if (reasoningPositive) status = "REASONING_ROUTE_OBSERVED";
  else if (instantPositive && !reasoningPositive) status = "INSTANT_MODEL_ROUTE_OBSERVED";
  else if (reasoningOff && !reasoningPositive) status = "NO_REASONING_EXPLICITLY_OBSERVED";

  return {
    status,
    instantModelRouteObserved: instantPositive,
    reasoningRouteObserved: reasoningPositive,
    reasoningOffObserved: reasoningOff,
    noReasoningRouteProven: (
      status === "INSTANT_MODEL_ROUTE_OBSERVED" ||
      status === "NO_REASONING_EXPLICITLY_OBSERVED"
    )
  };
}

function _pr88InstantModeSnapshotExpression() {
  return `(() => {
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const classify = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (text === 'instant' || text === 'мгновенно') return 'INSTANT';
      if (text === 'medium' || text === 'средний' || text === 'thinking standard') return 'MEDIUM';
      if (text === 'extra high' || text === 'очень высокий' || text === 'thinking heavy') return 'EXTRA_HIGH';
      if (text === 'high' || text === 'высокий' || text === 'thinking extended') return 'HIGH';
      if (text === 'pro standard') return 'PRO_STANDARD';
      if (text === 'pro extended') return 'PRO_EXTENDED';
      if (text === 'thinking') return 'REASONING_OTHER';
      if (text === 'pro') return 'PRO_OTHER';
      return null;
    };
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const selectors = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ];
    const composer = selectors.map((selector) => document.querySelector(selector)).find(Boolean);
    if (!composer || !visible(composer)) {
      return { composerReady: false, selectedMode: null, selectedModeProven: false, candidateCount: 0, proofKind: 'composer_missing' };
    }
    const composerRect = composer.getBoundingClientRect();
    const controls = Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
    const candidates = [];
    for (const control of controls) {
      const fields = [control.innerText, control.getAttribute('aria-label'), control.getAttribute('title')];
      const modes = Array.from(new Set(fields.map(classify).filter(Boolean)));
      if (modes.length !== 1) continue;
      const rect = control.getBoundingClientRect();
      const dx = Math.max(0, Math.max(composerRect.left - rect.right, rect.left - composerRect.right));
      const dy = Math.max(0, Math.max(composerRect.top - rect.bottom, rect.top - composerRect.bottom));
      const distance = Math.round(Math.sqrt(dx * dx + dy * dy));
      if (distance > 800) continue;
      candidates.push({ mode: modes[0], distance });
    }
    candidates.sort((a, b) => a.distance - b.distance);
    if (!candidates.length) {
      return { composerReady: true, selectedMode: null, selectedModeProven: false, candidateCount: 0, proofKind: 'no_mode_control' };
    }
    const nearest = candidates[0];
    const equallyNear = candidates.filter((candidate) => candidate.distance <= nearest.distance + 16);
    const uniqueModes = Array.from(new Set(equallyNear.map((candidate) => candidate.mode)));
    const proven = uniqueModes.length === 1;
    return {
      composerReady: true,
      selectedMode: proven ? uniqueModes[0] : null,
      selectedModeProven: proven,
      candidateCount: candidates.length,
      nearestDistancePx: nearest.distance,
      proofKind: proven ? 'nearest_composer_mode_control' : 'ambiguous_mode_controls'
    };
  })()`;
}

async function _pr88InstantSelectedModeSnapshot(debuggee) {
  try {
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr88InstantModeSnapshotExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (value && typeof value === "object") {
      return {
        composerReady: value.composerReady === true,
        selectedMode: typeof value.selectedMode === "string" ? value.selectedMode : null,
        selectedModeProven: value.selectedModeProven === true,
        candidateCount: Number.isInteger(value.candidateCount) ? value.candidateCount : 0,
        nearestDistancePx: Number.isFinite(value.nearestDistancePx) ? Math.max(0, Math.round(value.nearestDistancePx)) : null,
        proofKind: typeof value.proofKind === "string" ? value.proofKind : "unknown"
      };
    }
  } catch {
    // Read-only UI evidence is optional until the runner validates it.
  }
  return {
    composerReady: false,
    selectedMode: null,
    selectedModeProven: false,
    candidateCount: 0,
    nearestDistancePx: null,
    proofKind: "probe_failed"
  };
}

async function _pr88InstantWaitForSelectedMode(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr88InstantSelectedModeSnapshot(debuggee);
    if (last.selectedModeProven === true) return last;
    await sleep(PR88_INSTANT_MODE_SNAPSHOT_POLL_MS);
  }
  return last || await _pr88InstantSelectedModeSnapshot(debuggee);
}

locateAndFocusComposer = async function _locateAndFocusComposerWithInstantObservation(debuggee) {
  const context = _pr88InstantContext;
  if (context !== null && context.preWritePicker === null) {
    context.preWritePicker = await _pr88InstantSelectedModeSnapshot(debuggee);
  }
  return _pr88InstantPriorLocateAndFocusComposer(debuggee);
};

extractSafeStreamMetadata = function _extractSafeStreamMetadataWithInstantHints(body, base64Encoded) {
  const context = _pr88InstantContext;
  if (context !== null) {
    try {
      _pr88InstantMergeHints(
        context.responseHints,
        _pr88InstantParseSseHints(body, base64Encoded)
      );
    } catch {
      // Never perturb the existing safe stream metadata path.
    }
  }
  return _pr88InstantPriorExtractSafeStreamMetadata(body, base64Encoded);
};

executeOfficialPageTurn = async function _executeOfficialPageTurnWithInstantObservation(args) {
  const context = _pr88InstantContext;
  if (context === null) {
    return _pr88InstantPriorExecuteOfficialPageTurn(args);
  }

  let listenerInstalled = false;
  const observer = (source, method, params) => {
    try {
      if (source?.tabId !== args?.tabId || method !== "Network.requestWillBeSent") return;
      const request = params?.request;
      if (!isConversationWrite(request?.url || "", request?.method || "")) return;
      if (context.requestObserved) return;
      context.requestObserved = true;
      _pr88InstantMergeHints(
        context.requestHints,
        _pr88InstantParseRequestPostData(request?.postData)
      );
    } catch {
      // Observability cannot perturb the product write.
    }
  };
  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  try {
    return await _pr88InstantPriorExecuteOfficialPageTurn(args);
  } finally {
    if (listenerInstalled) {
      try { chrome.debugger.onEvent.removeListener(observer); } catch {}
    }
  }
};

function _pr88InstantQueryConflict(message) {
  return (
    message?.text != null ||
    message?.canonicalCompleted === true ||
    message?.browserAuthorityLeaseId != null ||
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.characterizeManualTemporaryGroundTruth === true ||
    message?.probeTemporaryRouteReopen === true
  );
}

async function _pr88InstantStoredRecord() {
  try {
    const stored = await chrome.storage.local.get(PR88_INSTANT_MODE_STORAGE_KEY);
    const value = stored?.[PR88_INSTANT_MODE_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

async function _pr88InstantCharacterizeRecord(message) {
  if (_pr88InstantQueryConflict(message) || message?.conversationId != null) {
    throw new Error("PR8_8_INSTANT_MODE_RECORD_FLAG_CONFLICT");
  }
  const expectedLeaseId = _pr88InstantLeaseId(message?.expectedBrowserAuthorityLeaseId);
  if (expectedLeaseId === null) {
    throw new Error("PR8_8_INSTANT_MODE_EXPECTED_LEASE_REQUIRED");
  }
  const record = await _pr88InstantStoredRecord();
  if (record === null) throw new Error("PR8_8_INSTANT_MODE_RECORD_NOT_AVAILABLE");
  if (_pr88InstantLeaseId(record.instantModeLeaseId) !== expectedLeaseId) {
    throw new Error("PR8_8_INSTANT_MODE_RECORD_LEASE_MISMATCH");
  }
  return {
    probeContext: "instant_mode_route_record",
    readOnly: true,
    instantModeSupported: true,
    ...record
  };
}

async function _pr88InstantCharacterizeSelectedMode(message) {
  if (_pr88InstantQueryConflict(message)) {
    throw new Error("PR8_8_INSTANT_SELECTED_MODE_FLAG_CONFLICT");
  }
  const conversationId = _pr88InstantConversationId(message?.conversationId);
  if (conversationId === null) {
    throw new Error("PR8_8_INSTANT_SELECTED_MODE_CONVERSATION_REQUIRED");
  }

  const initialRuntimeTabId = await storedRuntimeTabId();
  if (initialRuntimeTabId !== null) {
    throw new Error("PR8_8_INSTANT_SELECTED_MODE_REQUIRES_CLOSED_RUNTIME_TAB");
  }

  const activatedTabIds = new Set();
  const onActivated = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(onActivated);

  let tabId = null;
  let debuggee = null;
  let attached = false;
  let networkListener = null;
  let conversationWriteCount = 0;
  let snapshot = null;
  let tabWasActive = null;
  let tabActiveAfter = null;
  let probeTabClosed = false;
  let debuggerAttachedAfter = null;

  try {
    const tab = await ensureRuntimeTab(conversationId);
    tabId = Number.isInteger(tab?.id) ? tab.id : null;
    if (tabId === null) throw new Error("PR8_8_INSTANT_SELECTED_MODE_RUNTIME_TAB_MISSING");
    tabWasActive = Boolean(tab?.active);
    debuggee = { tabId };
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "Network.enable");

    networkListener = (source, method, params) => {
      if (source?.tabId !== tabId || method !== "Network.requestWillBeSent") return;
      const request = params?.request;
      if (isConversationWrite(request?.url || "", request?.method || "")) {
        conversationWriteCount += 1;
      }
    };
    chrome.debugger.onEvent.addListener(networkListener);

    await waitForComposerReady(debuggee, PR88_INSTANT_PROBE_TIMEOUT_MS);
    snapshot = await _pr88InstantWaitForSelectedMode(
      debuggee,
      Math.min(PR88_INSTANT_PROBE_TIMEOUT_MS, Number(message?.timeoutMs) || PR88_INSTANT_PROBE_TIMEOUT_MS)
    );
    const finalTab = await chrome.tabs.get(tabId);
    tabActiveAfter = Boolean(finalTab?.active);
    if (conversationIdFromUrl(finalTab?.url || "") !== conversationId) {
      throw new Error("PR8_8_INSTANT_SELECTED_MODE_CONVERSATION_CHANGED");
    }
    if (conversationWriteCount !== 0) {
      throw new Error(`PR8_8_INSTANT_SELECTED_MODE_UNEXPECTED_WRITE:${conversationWriteCount}`);
    }
  } finally {
    if (networkListener) {
      try { chrome.debugger.onEvent.removeListener(networkListener); } catch {}
    }
    if (attached && debuggee) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    if (debuggee) {
      try {
        const targets = await chrome.debugger.getTargets();
        debuggerAttachedAfter = Boolean(targets.find((target) => target.tabId === tabId)?.attached);
      } catch {
        debuggerAttachedAfter = null;
      }
    }
    if (Number.isInteger(tabId)) {
      try {
        await chrome.tabs.remove(tabId);
        probeTabClosed = true;
      } catch {
        probeTabClosed = false;
      }
    }
    chrome.tabs.onActivated.removeListener(onActivated);
  }

  let runtimeTabIdAfter = await storedRuntimeTabId();
  const settleStartedAt = performance.now();
  while (runtimeTabIdAfter !== null && performance.now() - settleStartedAt < 2000) {
    await sleep(50);
    runtimeTabIdAfter = await storedRuntimeTabId();
  }

  return {
    probeContext: "instant_selected_mode_exact_conversation_preflight",
    readOnly: true,
    instantModeSupported: true,
    instantModeSchemaVersion: PR88_INSTANT_MODE_SCHEMA_VERSION,
    conversationId,
    selectedMode: snapshot?.selectedMode || null,
    selectedModeProven: snapshot?.selectedModeProven === true,
    candidateCount: Number.isInteger(snapshot?.candidateCount) ? snapshot.candidateCount : 0,
    nearestDistancePx: Number.isFinite(snapshot?.nearestDistancePx) ? snapshot.nearestDistancePx : null,
    proofKind: snapshot?.proofKind || "unknown",
    conversationWriteCount,
    runtimeTabIdDuringProbe: tabId,
    runtimeTabIdAfter,
    probeTabClosed,
    tabWasActive,
    tabActiveAfter,
    tabActivatedDuringProbe: Number.isInteger(tabId) && activatedTabIds.has(tabId),
    foregroundActivationObserved: Boolean(
      tabWasActive === true ||
      tabActiveAfter === true ||
      (Number.isInteger(tabId) && activatedTabIds.has(tabId))
    ),
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _executeNativeTurnWithInstantModeObservation(message) {
  if (message?.characterizeInstantModeSupport === true) {
    if (_pr88InstantQueryConflict(message) || message?.conversationId != null) {
      throw new Error("PR8_8_INSTANT_MODE_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "instant_mode_support",
      readOnly: true,
      instantModeSupported: true,
      instantModeSchemaVersion: PR88_INSTANT_MODE_SCHEMA_VERSION,
      selectedModeProbeSupported: true,
      requestRouteObservationSupported: true,
      responseRouteObservationSupported: true
    };
  }

  if (message?.characterizeInstantSelectedMode === true) {
    return _pr88InstantCharacterizeSelectedMode(message);
  }

  if (message?.characterizeInstantModeRecord === true) {
    return _pr88InstantCharacterizeRecord(message);
  }

  const leaseId = _pr88InstantLeaseId(message?.browserAuthorityLeaseId);
  const requireInstant = message?.requiredModelMode === "INSTANT";
  const ordinaryProductWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  if (!ordinaryProductWrite || !requireInstant) {
    return _pr88InstantPriorExecuteNativeTurn(message);
  }

  const context = {
    leaseId,
    preWritePicker: null,
    requestObserved: false,
    requestHints: _pr88InstantNewHintAccumulator(),
    responseHints: _pr88InstantNewHintAccumulator()
  };
  _pr88InstantContext = context;

  try {
    const result = await _pr88InstantPriorExecuteNativeTurn(message);
    const networkRoute = _pr88InstantDeriveNetworkRoute(
      context.requestHints,
      context.responseHints
    );
    const preWritePicker = context.preWritePicker || {
      selectedMode: null,
      selectedModeProven: false,
      candidateCount: 0,
      nearestDistancePx: null,
      proofKind: "not_observed"
    };
    const record = {
      instantModeLeaseId: leaseId,
      instantModeSchemaVersion: PR88_INSTANT_MODE_SCHEMA_VERSION,
      requestedModelMode: "INSTANT",
      requireNoReasoningRoute: message?.requireNoReasoningRoute === true,
      selectedModeBeforeWrite: preWritePicker.selectedMode || null,
      selectedModeBeforeWriteProven: preWritePicker.selectedModeProven === true,
      selectedModeCandidateCount: Number.isInteger(preWritePicker.candidateCount) ? preWritePicker.candidateCount : 0,
      selectedModeNearestDistancePx: Number.isFinite(preWritePicker.nearestDistancePx) ? preWritePicker.nearestDistancePx : null,
      selectedModeProofKind: preWritePicker.proofKind || "unknown",
      conversationRequestObserved: context.requestObserved === true,
      requestEvidence: _pr88InstantHintsRecord(context.requestHints),
      responseEvidence: _pr88InstantHintsRecord(context.responseHints),
      networkRouteStatus: networkRoute.status,
      instantModelRouteObserved: networkRoute.instantModelRouteObserved,
      reasoningRouteObserved: networkRoute.reasoningRouteObserved,
      reasoningOffObserved: networkRoute.reasoningOffObserved,
      networkNoReasoningRouteProven: networkRoute.noReasoningRouteProven
    };

    try {
      await chrome.storage.local.set({ [PR88_INSTANT_MODE_STORAGE_KEY]: record });
    } catch {
      // Optional observability must not change successful product semantics.
    }

    return {
      ...result,
      instantModeSchemaVersion: PR88_INSTANT_MODE_SCHEMA_VERSION,
      requestedModelMode: "INSTANT",
      selectedModeBeforeWrite: record.selectedModeBeforeWrite,
      selectedModeBeforeWriteProven: record.selectedModeBeforeWriteProven,
      networkRouteStatus: record.networkRouteStatus,
      reasoningRouteObserved: record.reasoningRouteObserved,
      networkNoReasoningRouteProven: record.networkNoReasoningRouteProven
    };
  } finally {
    _pr88InstantContext = null;
  }
};
