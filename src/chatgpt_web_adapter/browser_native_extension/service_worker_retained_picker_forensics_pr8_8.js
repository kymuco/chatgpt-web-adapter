// PR8.8 retained failed-picker forensics and zero-write reconciliation evidence.
//
// Loaded after the Instant selection repair. This layer adds only read-only
// characterization RPCs. It never clicks the picker, changes model state,
// inserts prompt text, submits a conversation request, or closes the runtime
// tab. Optional runtime-tab reconciliation close remains a separate Python-side
// action using the existing lease+tab fenced release_runtime_tab API.

const PR88_RETAINED_PICKER_FORENSICS_SCHEMA_VERSION = 1;
const PR88_FORENSICS_MAX_DOM_CANDIDATES = 80;
const PR88_FORENSICS_MAX_AX_CANDIDATES = 80;
const PR88_FORENSICS_MAX_POPUPS = 24;
const _pr88ForensicsPriorExecuteNativeTurn = executeNativeTurn;

function _pr88ForensicsConversationId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (!conversationId || conversationId.includes("/") || conversationId.includes("?") || conversationId.includes("#")) {
    return null;
  }
  return conversationId;
}

function _pr88ForensicsNormalize(value) {
  return typeof value === "string"
    ? value.trim().toLowerCase().replace(/[\s_\-]+/g, " ")
    : "";
}

function _pr88ForensicsModes(value) {
  const text = _pr88ForensicsNormalize(value);
  if (!text) return [];
  const modes = [];
  const has = (pattern) => pattern.test(text);
  if (has(/(^|\b)(instant|мгновенно)(\b|$)/)) modes.push("INSTANT");
  if (has(/(^|\b)(medium|средний)(\b|$)/) || text.includes("thinking standard")) modes.push("MEDIUM");
  if (text.includes("extra high") || text.includes("очень высокий") || text.includes("thinking heavy")) modes.push("EXTRA_HIGH");
  else if (has(/(^|\b)(high|высокий)(\b|$)/) || text.includes("thinking extended")) modes.push("HIGH");
  if (text.includes("pro standard")) modes.push("PRO_STANDARD");
  if (text.includes("pro extended")) modes.push("PRO_EXTENDED");
  if (text === "thinking") modes.push("REASONING_OTHER");
  if (text === "pro") modes.push("PRO_OTHER");
  return Array.from(new Set(modes));
}

function _pr88ForensicsQueryConflict(message) {
  return (
    message?.text != null ||
    message?.canonicalCompleted === true ||
    message?.browserAuthorityLeaseId != null ||
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.characterizeManualTemporaryGroundTruth === true ||
    message?.probeTemporaryRouteReopen === true ||
    message?.characterizeInstantSelectedMode === true ||
    message?.characterizeInstantModeRecord === true ||
    message?.characterizeInstantSelectionRecord === true
  );
}

function _pr88ForensicsDomExpression() {
  return `(() => {
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const modes = (value) => {
      const text = normalize(value);
      if (!text) return [];
      const out = [];
      const has = (re) => re.test(text);
      if (has(/(^|\\b)(instant|мгновенно)(\\b|$)/)) out.push('INSTANT');
      if (has(/(^|\\b)(medium|средний)(\\b|$)/) || text.includes('thinking standard')) out.push('MEDIUM');
      if (text.includes('extra high') || text.includes('очень высокий') || text.includes('thinking heavy')) out.push('EXTRA_HIGH');
      else if (has(/(^|\\b)(high|высокий)(\\b|$)/) || text.includes('thinking extended')) out.push('HIGH');
      if (text.includes('pro standard')) out.push('PRO_STANDARD');
      if (text.includes('pro extended')) out.push('PRO_EXTENDED');
      if (text === 'thinking') out.push('REASONING_OTHER');
      if (text === 'pro') out.push('PRO_OTHER');
      return Array.from(new Set(out));
    };
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const boundedState = (value) => {
      const text = normalize(value);
      return ['open','closed','selected','checked','unchecked','active','inactive','on','off'].includes(text) ? text : null;
    };
    const ownText = (el) => Array.from(el.childNodes || [])
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent || '')
      .join(' ');
    const directFields = (el) => [
      ownText(el),
      el.getAttribute('aria-label'),
      el.getAttribute('title'),
      el.getAttribute('data-testid')
    ];
    const subtreeFields = (el) => [
      typeof el.innerText === 'string' ? el.innerText.slice(0, 320) : '',
      el.textContent ? String(el.textContent).slice(0, 320) : ''
    ];
    const rectRecord = (el) => {
      const r = el.getBoundingClientRect();
      return {
        x: Math.round(r.left), y: Math.round(r.top),
        width: Math.round(r.width), height: Math.round(r.height)
      };
    };
    const parentRoles = (el) => {
      const out = [];
      let current = el.parentElement;
      while (current && out.length < 5) {
        const role = current.getAttribute('role');
        if (role) out.push(role);
        current = current.parentElement;
      }
      return out;
    };
    const composer = [
      '#prompt-textarea',
      '[contenteditable="true"][data-lexical-editor="true"]',
      'textarea[placeholder]'
    ].map((selector) => document.querySelector(selector)).find((el) => el && visible(el));
    const composerReady = Boolean(composer);
    const composerRect = composer ? composer.getBoundingClientRect() : null;

    let pickerControl = null;
    if (composer) {
      const controls = Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
      const candidates = [];
      for (const control of controls) {
        const found = Array.from(new Set(directFields(control).flatMap(modes)));
        if (found.length !== 1) continue;
        const r = control.getBoundingClientRect();
        const dx = Math.max(0, Math.max(composerRect.left - r.right, r.left - composerRect.right));
        const dy = Math.max(0, Math.max(composerRect.top - r.bottom, r.top - composerRect.bottom));
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > 800) continue;
        candidates.push({ control, mode: found[0], distance });
      }
      candidates.sort((a, b) => a.distance - b.distance);
      if (candidates.length) {
        const nearest = candidates[0];
        pickerControl = {
          tag: nearest.control.tagName,
          role: nearest.control.getAttribute('role') || null,
          mode: nearest.mode,
          candidateCount: candidates.length,
          nearestDistancePx: Math.round(nearest.distance),
          rect: rectRecord(nearest.control),
          ariaExpanded: nearest.control.getAttribute('aria-expanded') || null,
          ariaHaspopup: nearest.control.getAttribute('aria-haspopup') || null,
          dataState: boundedState(nearest.control.getAttribute('data-state'))
        };
      }
    }

    const actionableRoles = new Set([
      'menuitem','menuitemradio','menuitemcheckbox','option','radio','button',
      'tab','treeitem','listitem','combobox'
    ]);
    const popupRoles = new Set(['menu','listbox','dialog','radiogroup','group','tree']);
    const domCandidates = [];
    const popupSurfaces = [];
    const all = Array.from(document.querySelectorAll('*'));
    for (const el of all) {
      if (!visible(el)) continue;
      const role = el.getAttribute('role') || null;
      const directModes = Array.from(new Set(directFields(el).flatMap(modes)));
      const subtreeModes = Array.from(new Set(subtreeFields(el).flatMap(modes)));
      const combinedModes = Array.from(new Set([...directModes, ...subtreeModes]));
      const tag = el.tagName;
      const actionable = tag === 'BUTTON' || (role && actionableRoles.has(role));
      const popup = role && popupRoles.has(role);

      if (popup && popupSurfaces.length < ${PR88_FORENSICS_MAX_POPUPS}) {
        popupSurfaces.push({
          tag,
          role,
          rect: rectRecord(el),
          ariaLabelMode: Array.from(new Set(modes(el.getAttribute('aria-label')))),
          descendantKnownModeCount: Array.from(el.querySelectorAll('*')).filter((child) => {
            if (!visible(child)) return false;
            return Array.from(new Set([
              ...directFields(child).flatMap(modes),
              ...subtreeFields(child).flatMap(modes)
            ])).length > 0;
          }).length
        });
      }

      if (domCandidates.length >= ${PR88_FORENSICS_MAX_DOM_CANDIDATES}) continue;
      if (!combinedModes.length && !actionable) continue;
      if (!combinedModes.length && role && !actionableRoles.has(role)) continue;

      const style = getComputedStyle(el);
      domCandidates.push({
        tag,
        role,
        modes: combinedModes,
        directModes,
        subtreeModes,
        modeEvidence: directModes.length ? 'DIRECT' : (subtreeModes.length ? 'SUBTREE' : 'NONE'),
        ariaChecked: el.getAttribute('aria-checked'),
        ariaSelected: el.getAttribute('aria-selected'),
        ariaExpanded: el.getAttribute('aria-expanded'),
        ariaHaspopup: el.getAttribute('aria-haspopup'),
        dataState: boundedState(el.getAttribute('data-state')),
        tabIndex: Number.isInteger(el.tabIndex) ? el.tabIndex : null,
        disabled: Boolean(el.disabled === true || el.getAttribute('aria-disabled') === 'true'),
        pointerEventsEnabled: style.pointerEvents !== 'none',
        rect: rectRecord(el),
        parentRoles: parentRoles(el),
        childElementCount: el.children ? el.children.length : 0,
        descendantActionableCount: Array.from(el.querySelectorAll('button,[role="button"],[role="menuitem"],[role="menuitemradio"],[role="option"],[role="radio"]')).filter(visible).length
      });
    }

    const recognizedModes = Array.from(new Set(domCandidates.flatMap((item) => item.modes))).sort();
    const instantDomCandidates = domCandidates.filter((item) => item.modes.includes('INSTANT'));
    const popupSurfaceOpen = popupSurfaces.length > 0 || Boolean(
      pickerControl && (pickerControl.ariaExpanded === 'true' || pickerControl.dataState === 'open')
    );
    return {
      composerReady,
      pickerControl,
      popupSurfaceOpen,
      popupSurfaces,
      domCandidates,
      recognizedModes,
      instantDomCandidateCount: instantDomCandidates.length,
      scannedVisibleElementCount: all.filter(visible).length
    };
  })()`;
}

function _pr88ForensicsAxProperty(node, name) {
  const properties = Array.isArray(node?.properties) ? node.properties : [];
  const entry = properties.find((item) => item?.name === name);
  const value = entry?.value?.value;
  if (["string", "number", "boolean"].includes(typeof value)) return value;
  return null;
}

function _pr88ForensicsAxMode(node) {
  const nameModes = _pr88ForensicsModes(node?.name?.value);
  if (nameModes.length === 1) return { mode: nameModes[0], evidence: "NAME" };
  const descModes = _pr88ForensicsModes(node?.description?.value);
  if (descModes.length === 1) return { mode: descModes[0], evidence: "DESCRIPTION" };
  return { mode: null, evidence: "NONE" };
}

function _pr88ForensicsAxTopology(axTree) {
  const nodes = Array.isArray(axTree?.nodes) ? axTree.nodes : [];
  const byId = new Map(nodes.map((node) => [node.nodeId, node]));
  const interestingRoles = new Set([
    "menu", "menuitem", "menuitemradio", "menuitemcheckbox", "listbox", "option",
    "radio", "radiogroup", "button", "dialog", "group", "combobox", "tab", "treeitem"
  ]);
  const candidates = [];
  for (const node of nodes) {
    if (candidates.length >= PR88_FORENSICS_MAX_AX_CANDIDATES) break;
    const role = typeof node?.role?.value === "string" ? node.role.value : null;
    const modeRecord = _pr88ForensicsAxMode(node);
    if (modeRecord.mode === null && !interestingRoles.has(role || "")) continue;
    const parent = node?.parentId ? byId.get(node.parentId) : null;
    const parentRole = typeof parent?.role?.value === "string" ? parent.role.value : null;
    candidates.push({
      role,
      mode: modeRecord.mode,
      modeEvidence: modeRecord.evidence,
      ignored: node?.ignored === true,
      parentRole,
      checked: _pr88ForensicsAxProperty(node, "checked"),
      selected: _pr88ForensicsAxProperty(node, "selected"),
      expanded: _pr88ForensicsAxProperty(node, "expanded"),
      focusable: _pr88ForensicsAxProperty(node, "focusable"),
      disabled: _pr88ForensicsAxProperty(node, "disabled"),
      backendDOMNodeIdPresent: Number.isInteger(node?.backendDOMNodeId),
      childCount: Array.isArray(node?.childIds) ? node.childIds.length : 0
    });
  }
  const recognizedModes = Array.from(new Set(candidates.map((item) => item.mode).filter(Boolean))).sort();
  return {
    candidateCount: candidates.length,
    instantCandidateCount: candidates.filter((item) => item.mode === "INSTANT").length,
    recognizedModes,
    candidates
  };
}

async function _pr88ForensicsStoredLeaseIdSafe() {
  try {
    if (typeof _pr88StoredLeaseId === "function") return await _pr88StoredLeaseId();
  } catch {}
  return null;
}

async function _pr88ForensicsProbe(message) {
  if (_pr88ForensicsQueryConflict(message)) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_FLAG_CONFLICT");
  }
  const conversationId = _pr88ForensicsConversationId(message?.conversationId);
  if (conversationId === null) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_CONVERSATION_REQUIRED");
  }
  const expectedTabId = Number.isInteger(message?.expectedRuntimeTabId)
    ? message.expectedRuntimeTabId
    : null;
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_RUNTIME_TAB_REQUIRED");
  }
  if (expectedTabId !== null && runtimeTabId !== expectedTabId) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_RUNTIME_TAB_CHANGED");
  }

  const tabBefore = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tabBefore?.url || "")) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_TAB_NOT_CHATGPT");
  }
  if (conversationIdFromUrl(tabBefore?.url || "") !== conversationId) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_CONVERSATION_MISMATCH");
  }

  let debuggerAttachedBefore = null;
  try {
    const targets = await chrome.debugger.getTargets();
    debuggerAttachedBefore = Boolean(targets.find((target) => target.tabId === runtimeTabId)?.attached);
  } catch {
    debuggerAttachedBefore = null;
  }
  if (debuggerAttachedBefore === true) {
    throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_DEBUGGER_ALREADY_ATTACHED");
  }

  const activatedTabIds = new Set();
  const onActivated = (info) => {
    if (Number.isInteger(info?.tabId)) activatedTabIds.add(info.tabId);
  };
  chrome.tabs.onActivated.addListener(onActivated);

  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let networkListener = null;
  let conversationWriteCount = 0;
  let dom = null;
  let ax = null;
  let tabActiveAfter = null;
  let debuggerAttachedAfter = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "Network.enable");
    try { await chrome.debugger.sendCommand(debuggee, "Accessibility.enable"); } catch {}

    networkListener = (source, method, params) => {
      if (source?.tabId !== runtimeTabId || method !== "Network.requestWillBeSent") return;
      const request = params?.request;
      if (isConversationWrite(request?.url || "", request?.method || "")) {
        conversationWriteCount += 1;
      }
    };
    chrome.debugger.onEvent.addListener(networkListener);

    const domResult = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr88ForensicsDomExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    dom = domResult?.result?.value || null;

    let axTree = null;
    try {
      axTree = await chrome.debugger.sendCommand(debuggee, "Accessibility.getFullAXTree", { depth: 12 });
    } catch {
      axTree = { nodes: [] };
    }
    ax = _pr88ForensicsAxTopology(axTree);

    const tabAfter = await chrome.tabs.get(runtimeTabId);
    tabActiveAfter = Boolean(tabAfter?.active);
    if (conversationIdFromUrl(tabAfter?.url || "") !== conversationId) {
      throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_CONVERSATION_CHANGED");
    }
    if (conversationWriteCount !== 0) {
      throw new Error(`PR8_8_RETAINED_PICKER_FORENSICS_UNEXPECTED_WRITE:${conversationWriteCount}`);
    }
  } finally {
    if (networkListener) {
      try { chrome.debugger.onEvent.removeListener(networkListener); } catch {}
    }
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(targets.find((target) => target.tabId === runtimeTabId)?.attached);
    } catch {
      debuggerAttachedAfter = null;
    }
    chrome.tabs.onActivated.removeListener(onActivated);
  }

  const runtimeTabIdAfter = await storedRuntimeTabId();
  const leaseId = await _pr88ForensicsStoredLeaseIdSafe();
  return {
    probeContext: "retained_failed_picker_surface_forensics",
    readOnly: true,
    zeroProductWrites: true,
    retainedPickerForensicsSupported: true,
    retainedPickerForensicsSchemaVersion: PR88_RETAINED_PICKER_FORENSICS_SCHEMA_VERSION,
    conversationId,
    expectedRuntimeTabId: expectedTabId,
    runtimeTabId,
    runtimeTabIdAfter,
    runtimeTabRetained: runtimeTabIdAfter === runtimeTabId,
    browserAuthorityLeaseId: leaseId,
    leaseIdPresent: leaseId !== null,
    tabWasActive: Boolean(tabBefore?.active),
    tabActiveAfter,
    tabActivatedDuringProbe: activatedTabIds.has(runtimeTabId),
    foregroundActivationObserved: Boolean(tabBefore?.active || tabActiveAfter === true || activatedTabIds.has(runtimeTabId)),
    debuggerAttachedBefore,
    debuggerAttachedAfter,
    conversationWriteCount,
    domTopology: dom,
    accessibilityTopology: ax,
    pickerSurfaceOpen: dom?.popupSurfaceOpen === true,
    instantDomCandidateCount: Number.isInteger(dom?.instantDomCandidateCount) ? dom.instantDomCandidateCount : 0,
    instantAxCandidateCount: Number.isInteger(ax?.instantCandidateCount) ? ax.instantCandidateCount : 0,
    recognizedModes: Array.from(new Set([
      ...(Array.isArray(dom?.recognizedModes) ? dom.recognizedModes : []),
      ...(Array.isArray(ax?.recognizedModes) ? ax.recognizedModes : [])
    ])).sort()
  };
}

executeNativeTurn = async function _executeNativeTurnWithRetainedPickerForensics(message) {
  if (message?.characterizeRetainedPickerForensicsSupport === true) {
    if (_pr88ForensicsQueryConflict(message) || message?.conversationId != null) {
      throw new Error("PR8_8_RETAINED_PICKER_FORENSICS_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "retained_picker_forensics_support",
      readOnly: true,
      zeroProductWrites: true,
      retainedPickerForensicsSupported: true,
      retainedPickerForensicsSchemaVersion: PR88_RETAINED_PICKER_FORENSICS_SCHEMA_VERSION,
      retainedExistingTabProbeSupported: true,
      domTopologySupported: true,
      accessibilityTopologySupported: true,
      conversationWriteGuardSupported: true,
      fencedReconciliationCloseSupported: true
    };
  }

  if (message?.characterizeRetainedPickerSurfaceForensics === true) {
    return _pr88ForensicsProbe(message);
  }

  return _pr88ForensicsPriorExecuteNativeTurn(message);
};
