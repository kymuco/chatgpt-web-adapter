// PR8.8 fresh-tab Instant selection repair and pre-submit materialization characterization.
//
// Loaded after service_worker_instant_mode_pr8_8.js and before the existing
// provisioning-observability wrapper captures executeNativeTurn.
//
// The layer performs one bounded product-UI model-picker action only for leased
// characterization turns that explicitly require INSTANT. The action happens
// after the proven runtime tab exists and before any prompt text is inserted.
// It never changes generic product-runtime defaults or Temporary semantics.
//
// Only bounded selection/network metadata is persisted. No prompt text,
// assistant text, raw DOM, raw request/response payloads, cookies, or auth data
// leave the worker.

const PR88_INSTANT_SELECTION_SCHEMA_VERSION = 1;
const PR88_INSTANT_SELECTION_STORAGE_KEY = "browserAuthorityLastInstantSelectionV1";
const PR88_INSTANT_SELECTION_OPTION_TIMEOUT_MS = 8000;
const PR88_INSTANT_SELECTION_SETTLE_TIMEOUT_MS = 8000;
const PR88_INSTANT_SELECTION_POLL_MS = 100;

const _pr88SelectionPriorExecuteNativeTurn = executeNativeTurn;
const _pr88SelectionPriorLocateAndFocusComposer = locateAndFocusComposer;

let _pr88SelectionContext = null;

function _pr88SelectionLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88SelectionDurationMs(startedAt, endedAt = performance.now()) {
  return Math.max(0, Math.round(endedAt - startedAt));
}

function _pr88SelectionSafeInt(value) {
  return Number.isFinite(value) ? Math.max(0, Math.round(Number(value))) : null;
}

function _pr88SelectionQueryConflict(message) {
  return (
    message?.text != null ||
    message?.conversationId != null ||
    message?.canonicalCompleted === true ||
    message?.browserAuthorityLeaseId != null ||
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.characterizeManualTemporaryGroundTruth === true ||
    message?.probeTemporaryRouteReopen === true
  );
}

function _pr88SelectionPointExpression(kind) {
  return `(() => {
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const classify = (value) => {
      const text = normalize(value);
      if (!text) return null;
      if (
        text === 'instant' ||
        text === 'мгновенно' ||
        text.startsWith('instant ') ||
        text.includes(' instant') ||
        text.startsWith('мгновенно ') ||
        text.includes(' мгновенно')
      ) return 'INSTANT';
      if (text === 'medium' || text === 'средний' || text.includes('thinking standard')) return 'MEDIUM';
      if (text === 'extra high' || text === 'очень высокий' || text.includes('thinking heavy')) return 'EXTRA_HIGH';
      if (text === 'high' || text === 'высокий' || text.includes('thinking extended')) return 'HIGH';
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
    const center = (el) => {
      const rect = el.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      };
    };
    const fields = (el) => [
      el.innerText,
      el.getAttribute('aria-label'),
      el.getAttribute('title')
    ];

    if (${JSON.stringify(kind)} === 'picker') {
      const composer = [
        '#prompt-textarea',
        '[contenteditable="true"][data-lexical-editor="true"]',
        'textarea[placeholder]'
      ].map((selector) => document.querySelector(selector)).find(Boolean);
      if (!composer || !visible(composer)) {
        return { found: false, reason: 'composer_missing', candidateCount: 0 };
      }
      const composerRect = composer.getBoundingClientRect();
      const controls = Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
      const candidates = [];
      for (const control of controls) {
        const modes = Array.from(new Set(fields(control).map(classify).filter(Boolean)));
        if (modes.length !== 1) continue;
        const rect = control.getBoundingClientRect();
        const dx = Math.max(0, Math.max(composerRect.left - rect.right, rect.left - composerRect.right));
        const dy = Math.max(0, Math.max(composerRect.top - rect.bottom, rect.top - composerRect.bottom));
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > 800) continue;
        candidates.push({ element: control, mode: modes[0], distance });
      }
      candidates.sort((a, b) => a.distance - b.distance);
      if (!candidates.length) {
        return { found: false, reason: 'picker_missing', candidateCount: 0 };
      }
      const nearest = candidates[0];
      const point = center(nearest.element);
      return {
        found: true,
        mode: nearest.mode,
        x: point.x,
        y: point.y,
        candidateCount: candidates.length,
        nearestDistancePx: Math.round(nearest.distance)
      };
    }

    const actionables = Array.from(document.querySelectorAll(
      '[role="menuitem"],[role="option"],[role="radio"],button,[role="button"]'
    )).filter(visible);
    const instantCandidates = [];
    for (const element of actionables) {
      const modes = Array.from(new Set(fields(element).map(classify).filter(Boolean)));
      if (modes.length !== 1 || modes[0] !== 'INSTANT') continue;
      const point = center(element);
      instantCandidates.push({ element, x: point.x, y: point.y });
    }
    if (instantCandidates.length !== 1) {
      return {
        found: false,
        reason: instantCandidates.length ? 'instant_option_ambiguous' : 'instant_option_missing',
        candidateCount: instantCandidates.length
      };
    }
    return {
      found: true,
      x: instantCandidates[0].x,
      y: instantCandidates[0].y,
      candidateCount: 1
    };
  })()`;
}

async function _pr88SelectionPoint(debuggee, kind) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr88SelectionPointExpression(kind),
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object"
    ? value
    : { found: false, reason: "point_probe_failed", candidateCount: 0 };
}

async function _pr88SelectionRawClick(debuggee, point) {
  if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) {
    throw new Error("PR8_8_INSTANT_SELECTION_CLICK_POINT_REQUIRED");
  }
  // Intentionally bypass sendCommand(): the proven submit hotfix treats generic
  // mouse release as possible send-button activity. Picker clicks are unrelated
  // product UI and must not enter that fallback ladder.
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: point.x,
    y: point.y
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: point.x,
    y: point.y,
    button: "left",
    buttons: 1,
    clickCount: 1
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: point.x,
    y: point.y,
    button: "left",
    buttons: 0,
    clickCount: 1
  });
}

async function _pr88SelectionWaitForInstantOption(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr88SelectionPoint(debuggee, "instant_option");
    if (last?.found === true) return last;
    await sleep(PR88_INSTANT_SELECTION_POLL_MS);
  }
  return last || { found: false, reason: "instant_option_timeout", candidateCount: 0 };
}

async function _pr88SelectionWaitForInstantSelected(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr88InstantSelectedModeSnapshot(debuggee);
    if (
      last?.selectedModeProven === true &&
      last?.selectedMode === "INSTANT"
    ) {
      return last;
    }
    await sleep(PR88_INSTANT_SELECTION_POLL_MS);
  }
  return last || await _pr88InstantSelectedModeSnapshot(debuggee);
}

function _pr88SelectionNetworkClass(url, method) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return "INVALID_URL";
  }
  if (parsed.origin !== CHATGPT_ORIGIN) return "OTHER_ORIGIN";
  if (isConversationWrite(url, method)) return "CONVERSATION_WRITE";
  const normalizedMethod = String(method || "").toUpperCase();
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(normalizedMethod);
  if (!mutating) return "CHATGPT_READ";
  const path = parsed.pathname.toLowerCase();
  if (
    path.includes("setting") ||
    path.includes("preference") ||
    path.includes("model") ||
    path.includes("config")
  ) {
    return "CHATGPT_SETTING_LIKE_MUTATION";
  }
  return "CHATGPT_MUTATION_OTHER";
}

function _pr88SelectionInstallNetworkWindow(debuggee, context) {
  const listener = (source, method, params) => {
    if (source?.tabId !== debuggee.tabId || method !== "Network.requestWillBeSent") return;
    const request = params?.request;
    const requestClass = _pr88SelectionNetworkClass(
      request?.url || "",
      request?.method || ""
    );

    if (requestClass === "CONVERSATION_WRITE") {
      context.conversationWriteBoundaryObserved = true;
      if (context.selectionComplete !== true) {
        context.unexpectedConversationWriteBeforeSelectionComplete = true;
        context.conversationWriteCountDuringSelection += 1;
      }
      try { chrome.debugger.onEvent.removeListener(listener); } catch {}
      context.networkListener = null;
      return;
    }

    context.networkRequestCountDuringSelection += 1;
    context.requestClasses.add(requestClass);
    if (requestClass !== "OTHER_ORIGIN" && requestClass !== "INVALID_URL") {
      context.chatgptRequestCountDuringSelection += 1;
    }
    if (
      requestClass === "CHATGPT_SETTING_LIKE_MUTATION" ||
      requestClass === "CHATGPT_MUTATION_OTHER"
    ) {
      context.chatgptMutatingNonConversationRequestCount += 1;
    }
    if (requestClass === "CHATGPT_SETTING_LIKE_MUTATION") {
      context.settingLikeMutationObserved = true;
    }
  };
  chrome.debugger.onEvent.addListener(listener);
  context.networkListener = listener;
}

async function _pr88SelectionEnsureInstant(debuggee, context) {
  if (context.selectionChecked === true) return;
  context.selectionChecked = true;
  const startedAt = performance.now();

  const before = await _pr88InstantSelectedModeSnapshot(debuggee);
  context.selectedModeBeforeSelection = before?.selectedMode || null;
  context.selectedModeBeforeSelectionProven = before?.selectedModeProven === true;
  context.selectedModeBeforeSelectionProofKind = before?.proofKind || "unknown";
  context.selectedModeBeforeSelectionCandidateCount = Number.isInteger(before?.candidateCount)
    ? before.candidateCount
    : 0;

  if (before?.selectedModeProven !== true || typeof before?.selectedMode !== "string") {
    throw new Error("PR8_8_INSTANT_SELECTION_INITIAL_MODE_NOT_PROVEN");
  }

  if (before.selectedMode === "INSTANT") {
    context.selectionPerformed = false;
    context.selectedModeAfterSelection = "INSTANT";
    context.selectedModeAfterSelectionProven = true;
    context.selectedModeAfterSelectionProofKind = before.proofKind || "unknown";
    context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
    context.selectionMutationElapsedMs = 0;
    context.selectionComplete = true;
    return;
  }

  context.selectionPerformed = true;
  _pr88SelectionInstallNetworkWindow(debuggee, context);

  const mutationStartedAt = performance.now();
  const picker = await _pr88SelectionPoint(debuggee, "picker");
  context.pickerCandidateCount = Number.isInteger(picker?.candidateCount)
    ? picker.candidateCount
    : 0;
  context.pickerNearestDistancePx = _pr88SelectionSafeInt(picker?.nearestDistancePx);
  context.pickerModeBeforeClick = typeof picker?.mode === "string" ? picker.mode : null;
  if (picker?.found !== true) {
    throw new Error(`PR8_8_INSTANT_SELECTION_PICKER_NOT_FOUND:${picker?.reason || "unknown"}`);
  }
  await _pr88SelectionRawClick(debuggee, picker);

  const option = await _pr88SelectionWaitForInstantOption(
    debuggee,
    PR88_INSTANT_SELECTION_OPTION_TIMEOUT_MS
  );
  context.instantOptionCandidateCount = Number.isInteger(option?.candidateCount)
    ? option.candidateCount
    : 0;
  if (option?.found !== true) {
    throw new Error(`PR8_8_INSTANT_SELECTION_OPTION_NOT_FOUND:${option?.reason || "unknown"}`);
  }
  await _pr88SelectionRawClick(debuggee, option);

  const after = await _pr88SelectionWaitForInstantSelected(
    debuggee,
    PR88_INSTANT_SELECTION_SETTLE_TIMEOUT_MS
  );
  context.selectedModeAfterSelection = after?.selectedMode || null;
  context.selectedModeAfterSelectionProven = after?.selectedModeProven === true;
  context.selectedModeAfterSelectionProofKind = after?.proofKind || "unknown";
  if (
    after?.selectedModeProven !== true ||
    after?.selectedMode !== "INSTANT"
  ) {
    throw new Error("PR8_8_INSTANT_SELECTION_DID_NOT_SETTLE_TO_INSTANT");
  }

  context.selectionMutationElapsedMs = _pr88SelectionDurationMs(mutationStartedAt);
  context.selectionElapsedMs = _pr88SelectionDurationMs(startedAt);
  context.selectionComplete = true;
  // Keep the network window open until the actual conversation POST. This
  // captures any asynchronous model-selection persistence without adding an
  // artificial sleep to the latency measurement.
}

locateAndFocusComposer = async function _locateAndFocusComposerWithInstantSelectionRepair(debuggee) {
  const context = _pr88SelectionContext;
  if (context !== null) {
    await _pr88SelectionEnsureInstant(debuggee, context);
  }
  // The prior wrapper is the existing Instant observer. Calling it only after
  // selection means its preWritePicker snapshot must see the repaired state.
  return _pr88SelectionPriorLocateAndFocusComposer(debuggee);
};

async function _pr88SelectionStoredRecord() {
  try {
    const stored = await chrome.storage.local.get(PR88_INSTANT_SELECTION_STORAGE_KEY);
    const value = stored?.[PR88_INSTANT_SELECTION_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

async function _pr88SelectionCharacterizeRecord(message) {
  if (_pr88SelectionQueryConflict(message)) {
    throw new Error("PR8_8_INSTANT_SELECTION_RECORD_FLAG_CONFLICT");
  }
  const expectedLeaseId = _pr88SelectionLeaseId(message?.expectedBrowserAuthorityLeaseId);
  if (expectedLeaseId === null) {
    throw new Error("PR8_8_INSTANT_SELECTION_EXPECTED_LEASE_REQUIRED");
  }
  const record = await _pr88SelectionStoredRecord();
  if (record === null) {
    throw new Error("PR8_8_INSTANT_SELECTION_RECORD_NOT_AVAILABLE");
  }
  if (_pr88SelectionLeaseId(record.instantSelectionLeaseId) !== expectedLeaseId) {
    throw new Error("PR8_8_INSTANT_SELECTION_RECORD_LEASE_MISMATCH");
  }
  return {
    probeContext: "instant_selection_repair_record",
    readOnly: true,
    instantSelectionRepairSupported: true,
    ...record
  };
}

function _pr88SelectionRecord(context) {
  let materializationStatus = "NO_SELECTION_REQUIRED";
  if (context.selectionPerformed === true) {
    if (context.unexpectedConversationWriteBeforeSelectionComplete === true) {
      materializationStatus = "UNEXPECTED_CONVERSATION_WRITE_DURING_SELECTION";
    } else if (context.settingLikeMutationObserved === true) {
      materializationStatus = "SETTING_LIKE_BACKEND_MUTATION_OBSERVED";
    } else if (context.chatgptMutatingNonConversationRequestCount > 0) {
      materializationStatus = "OTHER_CHATGPT_MUTATION_OBSERVED";
    } else if (context.chatgptRequestCountDuringSelection > 0) {
      materializationStatus = "NO_CHATGPT_MUTATION_OBSERVED";
    } else {
      materializationStatus = "NO_NETWORK_ACTIVITY_OBSERVED";
    }
  }

  return {
    instantSelectionLeaseId: context.leaseId,
    instantSelectionSchemaVersion: PR88_INSTANT_SELECTION_SCHEMA_VERSION,
    requestedModelMode: "INSTANT",
    selectedModeBeforeSelection: context.selectedModeBeforeSelection,
    selectedModeBeforeSelectionProven: context.selectedModeBeforeSelectionProven,
    selectedModeBeforeSelectionProofKind: context.selectedModeBeforeSelectionProofKind,
    selectedModeBeforeSelectionCandidateCount: context.selectedModeBeforeSelectionCandidateCount,
    selectionPerformed: context.selectionPerformed === true,
    selectionElapsedMs: _pr88SelectionSafeInt(context.selectionElapsedMs),
    selectionMutationElapsedMs: _pr88SelectionSafeInt(context.selectionMutationElapsedMs),
    pickerModeBeforeClick: context.pickerModeBeforeClick,
    pickerCandidateCount: context.pickerCandidateCount,
    pickerNearestDistancePx: context.pickerNearestDistancePx,
    instantOptionCandidateCount: context.instantOptionCandidateCount,
    selectedModeAfterSelection: context.selectedModeAfterSelection,
    selectedModeAfterSelectionProven: context.selectedModeAfterSelectionProven,
    selectedModeAfterSelectionProofKind: context.selectedModeAfterSelectionProofKind,
    selectionComplete: context.selectionComplete === true,
    conversationWriteBoundaryObserved: context.conversationWriteBoundaryObserved === true,
    unexpectedConversationWriteBeforeSelectionComplete:
      context.unexpectedConversationWriteBeforeSelectionComplete === true,
    conversationWriteCountDuringSelection: context.conversationWriteCountDuringSelection,
    networkRequestCountDuringSelection: context.networkRequestCountDuringSelection,
    chatgptRequestCountDuringSelection: context.chatgptRequestCountDuringSelection,
    chatgptMutatingNonConversationRequestCount:
      context.chatgptMutatingNonConversationRequestCount,
    settingLikeMutationObserved: context.settingLikeMutationObserved === true,
    requestClasses: Array.from(context.requestClasses).sort(),
    modelSelectionMaterializationStatus: materializationStatus
  };
}

executeNativeTurn = async function _executeNativeTurnWithInstantSelectionRepair(message) {
  if (message?.characterizeInstantSelectionRepairSupport === true) {
    if (_pr88SelectionQueryConflict(message)) {
      throw new Error("PR8_8_INSTANT_SELECTION_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "instant_selection_repair_support",
      readOnly: true,
      instantSelectionRepairSupported: true,
      instantSelectionSchemaVersion: PR88_INSTANT_SELECTION_SCHEMA_VERSION,
      productUiSelectionSupported: true,
      preSubmitNetworkClassificationSupported: true,
      conversationWriteBoundarySupported: true
    };
  }

  if (message?.characterizeInstantSelectionRecord === true) {
    return _pr88SelectionCharacterizeRecord(message);
  }

  const leaseId = _pr88SelectionLeaseId(message?.browserAuthorityLeaseId);
  const ordinaryProductWrite = (
    typeof message?.text === "string" &&
    Boolean(message.text.trim()) &&
    leaseId !== null
  );
  const requireInstant = message?.requiredModelMode === "INSTANT";

  if (!ordinaryProductWrite || !requireInstant) {
    return _pr88SelectionPriorExecuteNativeTurn(message);
  }

  const context = {
    leaseId,
    selectionChecked: false,
    selectionComplete: false,
    selectionPerformed: false,
    selectedModeBeforeSelection: null,
    selectedModeBeforeSelectionProven: false,
    selectedModeBeforeSelectionProofKind: null,
    selectedModeBeforeSelectionCandidateCount: 0,
    selectionElapsedMs: null,
    selectionMutationElapsedMs: null,
    pickerModeBeforeClick: null,
    pickerCandidateCount: 0,
    pickerNearestDistancePx: null,
    instantOptionCandidateCount: 0,
    selectedModeAfterSelection: null,
    selectedModeAfterSelectionProven: false,
    selectedModeAfterSelectionProofKind: null,
    conversationWriteBoundaryObserved: false,
    unexpectedConversationWriteBeforeSelectionComplete: false,
    conversationWriteCountDuringSelection: 0,
    networkRequestCountDuringSelection: 0,
    chatgptRequestCountDuringSelection: 0,
    chatgptMutatingNonConversationRequestCount: 0,
    settingLikeMutationObserved: false,
    requestClasses: new Set(),
    networkListener: null
  };
  _pr88SelectionContext = context;

  try {
    const result = await _pr88SelectionPriorExecuteNativeTurn(message);
    const record = _pr88SelectionRecord(context);
    try {
      await chrome.storage.local.set({
        [PR88_INSTANT_SELECTION_STORAGE_KEY]: record
      });
    } catch {
      // Optional observability must not change successful product semantics.
    }
    return {
      ...result,
      instantSelectionSchemaVersion: PR88_INSTANT_SELECTION_SCHEMA_VERSION,
      instantSelectionPerformed: record.selectionPerformed,
      selectedModeBeforeSelection: record.selectedModeBeforeSelection,
      selectedModeAfterSelection: record.selectedModeAfterSelection,
      modelSelectionMaterializationStatus: record.modelSelectionMaterializationStatus
    };
  } finally {
    if (context.networkListener) {
      try { chrome.debugger.onEvent.removeListener(context.networkListener); } catch {}
      context.networkListener = null;
    }
    _pr88SelectionContext = null;
  }
};
