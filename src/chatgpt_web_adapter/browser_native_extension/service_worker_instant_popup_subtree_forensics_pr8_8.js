// PR8.8 in-failure open-picker popup-subtree evidence capture.
//
// Loaded after service_worker_instant_failure_forensics_pr8_8.js. This layer
// adds no product mutation. It catches the same locate/selection failure after
// the prior failure layer has persisted its bounded record, captures only the
// currently-open popup subtree through the debugger that is already attached by
// the ordinary write path, persists bounded topology keyed by the same lease,
// and rethrows the original exception object unchanged.

const PR88_INSTANT_POPUP_SUBTREE_SCHEMA_VERSION = 1;
const PR88_INSTANT_POPUP_SUBTREE_STORAGE_KEY =
  "browserAuthorityLastInstantPopupSubtreeForensicsV1";
const PR88_INSTANT_POPUP_MAX_SURFACES = 8;
const PR88_INSTANT_POPUP_MAX_MODE_LABELS = 16;
const PR88_INSTANT_POPUP_MAX_ACTIONABLES = 32;

const _pr88PopupPriorExecuteNativeTurn = executeNativeTurn;
const _pr88PopupPriorLocateAndFocusComposer = locateAndFocusComposer;

function _pr88PopupLeaseId(value) {
  const leaseId = typeof value === "string" ? value.trim() : "";
  return leaseId || null;
}

function _pr88PopupModes(value) {
  try {
    if (typeof _pr88ForensicsModes === "function") {
      return _pr88ForensicsModes(value);
    }
  } catch {}
  const text = typeof value === "string"
    ? value.trim().toLowerCase().replace(/[\s_\-]+/g, " ")
    : "";
  if (!text) return [];
  const out = [];
  if (/(^|\b)(instant|мгновенно)(\b|$)/.test(text)) out.push("INSTANT");
  if (/(^|\b)(medium|средний)(\b|$)/.test(text) || text.includes("thinking standard")) out.push("MEDIUM");
  if (text.includes("extra high") || text.includes("очень высокий") || text.includes("thinking heavy")) out.push("EXTRA_HIGH");
  else if (/(^|\b)(high|высокий)(\b|$)/.test(text) || text.includes("thinking extended")) out.push("HIGH");
  if (text.includes("pro standard")) out.push("PRO_STANDARD");
  if (text.includes("pro extended")) out.push("PRO_EXTENDED");
  if (text === "thinking") out.push("REASONING_OTHER");
  if (text === "pro") out.push("PRO_OTHER");
  return Array.from(new Set(out));
}

function _pr88PopupRoute(urlValue) {
  const url = typeof urlValue === "string" ? urlValue : "";
  const observedConversationId = (() => {
    try {
      const value = conversationIdFromUrl(url);
      return typeof value === "string" && value.trim() ? value.trim() : null;
    } catch {
      return null;
    }
  })();
  let pathname = "/";
  try { pathname = new URL(url).pathname || "/"; } catch {}
  let routeKind = "OTHER_CHATGPT";
  if (observedConversationId !== null) routeKind = "CONVERSATION";
  else if (pathname === "/" || pathname === "") routeKind = "ROOT";
  return { routeKind, observedConversationId };
}

function _pr88PopupDomExpression() {
  return `(() => {
    const MAX_SURFACES = ${PR88_INSTANT_POPUP_MAX_SURFACES};
    const MAX_MODE_LABELS = ${PR88_INSTANT_POPUP_MAX_MODE_LABELS};
    const MAX_ACTIONABLES = ${PR88_INSTANT_POPUP_MAX_ACTIONABLES};
    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\\s_\\-]+/g, ' ');
    const modes = (value) => {
      const text = normalize(value);
      if (!text) return [];
      const out = [];
      if (/(^|\\b)(instant|мгновенно)(\\b|$)/.test(text)) out.push('INSTANT');
      if (/(^|\\b)(medium|средний)(\\b|$)/.test(text) || text.includes('thinking standard')) out.push('MEDIUM');
      if (text.includes('extra high') || text.includes('очень высокий') || text.includes('thinking heavy')) out.push('EXTRA_HIGH');
      else if (/(^|\\b)(high|высокий)(\\b|$)/.test(text) || text.includes('thinking extended')) out.push('HIGH');
      if (text.includes('pro standard')) out.push('PRO_STANDARD');
      if (text.includes('pro extended')) out.push('PRO_EXTENDED');
      if (text === 'thinking') out.push('REASONING_OTHER');
      if (text === 'pro') out.push('PRO_OTHER');
      return Array.from(new Set(out));
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
      return {x: Math.round(r.left), y: Math.round(r.top), width: Math.round(r.width), height: Math.round(r.height)};
    };
    const ownText = (el) => Array.from(el.childNodes || [])
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .map((n) => n.textContent || '')
      .join(' ');
    const directFields = (el) => [
      ['OWN_TEXT', ownText(el)],
      ['ARIA_LABEL', el.getAttribute('aria-label')],
      ['TITLE', el.getAttribute('title')],
      ['TEST_ID', el.getAttribute('data-testid')]
    ];
    const modeRecord = (el) => {
      for (const [source, value] of directFields(el)) {
        const found = modes(value);
        if (found.length === 1) return {mode: found[0], evidence: source};
      }
      const subtree = Array.from(new Set([
        ...modes(typeof el.innerText === 'string' ? el.innerText.slice(0, 320) : ''),
        ...modes(el.textContent ? String(el.textContent).slice(0, 320) : '')
      ]));
      if (subtree.length === 1) return {mode: subtree[0], evidence: 'SUBTREE_TEXT'};
      return {mode: null, evidence: 'NONE'};
    };
    const directModes = (el) => Array.from(new Set(directFields(el).flatMap(([, value]) => modes(value))));
    const subtreeModes = (el) => Array.from(new Set([
      ...modes(typeof el.innerText === 'string' ? el.innerText.slice(0, 320) : ''),
      ...modes(el.textContent ? String(el.textContent).slice(0, 320) : '')
    ]));
    const actionableRoles = new Set(['menuitem','menuitemradio','menuitemcheckbox','option','radio','button','tab','treeitem']);
    const isActionable = (el) => el instanceof Element && (el.tagName === 'BUTTON' || actionableRoles.has(el.getAttribute('role') || ''));
    const actionableRecord = (el) => {
      if (!el) return null;
      const style = getComputedStyle(el);
      return {
        tag: el.tagName,
        role: el.getAttribute('role') || null,
        directModes: directModes(el),
        subtreeModes: subtreeModes(el),
        ariaChecked: el.getAttribute('aria-checked'),
        ariaSelected: el.getAttribute('aria-selected'),
        ariaExpanded: el.getAttribute('aria-expanded'),
        ariaHaspopup: el.getAttribute('aria-haspopup'),
        dataState: ['open','closed','selected','checked','unchecked','active','inactive','on','off'].includes(normalize(el.getAttribute('data-state'))) ? normalize(el.getAttribute('data-state')) : null,
        disabled: Boolean(el.disabled === true || el.getAttribute('aria-disabled') === 'true'),
        pointerEventsEnabled: style.pointerEvents !== 'none',
        rect: rect(el),
        childElementCount: el.children ? el.children.length : 0
      };
    };
    const nearestActionableAncestor = (el, surface) => {
      let current = el;
      let hops = 0;
      while (current && hops <= 8) {
        if (isActionable(current)) return {element: current, hops};
        if (current === surface) break;
        current = current.parentElement;
        hops += 1;
      }
      return {element: null, hops: null};
    };
    const allSurfaces = Array.from(document.querySelectorAll('[role="menu"],[role="listbox"],[role="dialog"],[role="radiogroup"],[role="group"]')).filter(visible);
    const priority = {menu: 0, listbox: 1, radiogroup: 2, dialog: 3, group: 4};
    const surfaceRecords = [];
    for (const surface of allSurfaces) {
      const descendants = Array.from(surface.querySelectorAll('*')).filter(visible);
      const rawModes = descendants.map((el) => ({el, rec: modeRecord(el)})).filter((item) => item.rec.mode);
      const minimalModes = rawModes.filter((item) => !rawModes.some((other) => other !== item && item.el.contains(other.el) && other.rec.mode === item.rec.mode));
      if (!minimalModes.length) continue;
      const actionables = descendants.filter(isActionable);
      const role = surface.getAttribute('role') || null;
      surfaceRecords.push({surface, role, descendants, minimalModes, actionables, knownModeCount: minimalModes.length, actionCount: actionables.length});
    }
    surfaceRecords.sort((a, b) => {
      const pa = Object.prototype.hasOwnProperty.call(priority, a.role) ? priority[a.role] : 9;
      const pb = Object.prototype.hasOwnProperty.call(priority, b.role) ? priority[b.role] : 9;
      if (pa !== pb) return pa - pb;
      if (a.knownModeCount !== b.knownModeCount) return b.knownModeCount - a.knownModeCount;
      const ar = a.surface.getBoundingClientRect();
      const br = b.surface.getBoundingClientRect();
      return (ar.width * ar.height) - (br.width * br.height);
    });
    const candidateSurfaces = surfaceRecords.slice(0, MAX_SURFACES).map((item) => ({
      tag: item.surface.tagName,
      role: item.role,
      knownModeDescendantCount: item.knownModeCount,
      actionableDescendantCount: item.actionCount,
      rect: rect(item.surface)
    }));
    const selected = surfaceRecords.length ? surfaceRecords[0] : null;
    if (!selected) {
      return {
        surfaceFound: false,
        surfaceSelectionStatus: 'NO_MODE_POPUP_FOUND',
        candidateSurfaceCount: surfaceRecords.length,
        candidateSurfaces,
        candidateSurfacesTruncated: surfaceRecords.length > MAX_SURFACES,
        recognizedModes: [],
        popupSubtreeVisibleElementCount: 0,
        modeLabelCount: 0,
        modeLabels: [],
        modeLabelsTruncated: false,
        actionableDescendantCount: 0,
        actionableDescendants: [],
        actionableDescendantsTruncated: false,
        candidateCapDealiased: true,
        globalCandidateCapUsed: false
      };
    }
    const modeLabelsAll = selected.minimalModes.map((item) => {
      const nearest = nearestActionableAncestor(item.el, selected.surface);
      return {
        mode: item.rec.mode,
        evidence: item.rec.evidence,
        tag: item.el.tagName,
        role: item.el.getAttribute('role') || null,
        rect: rect(item.el),
        actionableAncestorFound: Boolean(nearest.element),
        actionableAncestorHops: nearest.hops,
        actionableAncestor: actionableRecord(nearest.element)
      };
    });
    const actionableAll = selected.actionables.map((el) => {
      const descendantModes = Array.from(new Set(
        selected.minimalModes.filter((item) => el.contains(item.el)).map((item) => item.rec.mode)
      )).sort();
      return {
        ...actionableRecord(el),
        modeBearingDescendantModes: descendantModes,
        modeBearingDescendantCount: descendantModes.length
      };
    });
    const recognizedModes = Array.from(new Set(modeLabelsAll.map((item) => item.mode))).sort();
    return {
      surfaceFound: true,
      surfaceSelectionStatus: 'SELECTED_MODE_BEARING_POPUP',
      candidateSurfaceCount: surfaceRecords.length,
      candidateSurfaces,
      candidateSurfacesTruncated: surfaceRecords.length > MAX_SURFACES,
      selectedSurface: {
        tag: selected.surface.tagName,
        role: selected.role,
        knownModeDescendantCount: selected.knownModeCount,
        actionableDescendantCount: selected.actionCount,
        rect: rect(selected.surface)
      },
      recognizedModes,
      popupSubtreeVisibleElementCount: selected.descendants.length,
      modeLabelCount: modeLabelsAll.length,
      modeLabels: modeLabelsAll.slice(0, MAX_MODE_LABELS),
      modeLabelsTruncated: modeLabelsAll.length > MAX_MODE_LABELS,
      actionableDescendantCount: actionableAll.length,
      actionableDescendants: actionableAll.slice(0, MAX_ACTIONABLES),
      actionableDescendantsTruncated: actionableAll.length > MAX_ACTIONABLES,
      candidateCapDealiased: true,
      globalCandidateCapUsed: false
    };
  })()`;
}

async function _pr88PopupCapture(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  let route = { routeKind: "UNKNOWN", observedConversationId: null };
  if (tabId !== null) {
    try {
      const tab = await chrome.tabs.get(tabId);
      route = _pr88PopupRoute(tab?.url || "");
    } catch {}
  }
  try {
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr88PopupDomExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const topology = result?.result?.value;
    const safe = topology && typeof topology === "object" ? topology : {};
    return {
      captureStatus: safe.surfaceFound === true ? "POPUP_SUBTREE_CAPTURED" : "NO_MODE_POPUP_FOUND",
      captureTabId: tabId,
      routeKind: route.routeKind,
      observedConversationId: route.observedConversationId,
      rawUrlExported: false,
      rawTextExported: false,
      rawHtmlExported: false,
      candidateCapDealiased: safe.candidateCapDealiased === true,
      globalCandidateCapUsed: safe.globalCandidateCapUsed === true,
      topology: safe
    };
  } catch {
    return {
      captureStatus: "CAPTURE_FAILED",
      captureTabId: tabId,
      routeKind: route.routeKind,
      observedConversationId: route.observedConversationId,
      rawUrlExported: false,
      rawTextExported: false,
      rawHtmlExported: false,
      candidateCapDealiased: false,
      globalCandidateCapUsed: false,
      topology: {}
    };
  }
}

async function _pr88PopupPersist(error, context, debuggee) {
  const leaseId = _pr88PopupLeaseId(context?.leaseId);
  if (leaseId === null) return false;
  const capture = await _pr88PopupCapture(debuggee);
  const failureCode = (() => {
    try { return typeof _pr88FailureCode === "function" ? _pr88FailureCode(error) : "UNKNOWN"; } catch { return "UNKNOWN"; }
  })();
  const failureReason = (() => {
    try { return typeof _pr88FailureReason === "function" ? _pr88FailureReason(error) : null; } catch { return null; }
  })();
  await chrome.storage.local.set({
    [PR88_INSTANT_POPUP_SUBTREE_STORAGE_KEY]: {
      schemaVersion: PR88_INSTANT_POPUP_SUBTREE_SCHEMA_VERSION,
      leaseId,
      capturedAtFailure: true,
      failureCode,
      failureReason,
      ...capture
    }
  });
  return true;
}

locateAndFocusComposer = async function _locateAndFocusComposerWithInstantPopupSubtreeEvidence(debuggee) {
  try {
    return await _pr88PopupPriorLocateAndFocusComposer(debuggee);
  } catch (error) {
    let context = null;
    try {
      if (typeof _pr88SelectionContext !== "undefined") context = _pr88SelectionContext;
    } catch {}
    if (context !== null && _pr88PopupLeaseId(context?.leaseId) !== null) {
      try {
        await _pr88PopupPersist(error, context, debuggee);
      } catch {
        // Popup evidence must never replace or mask the original failure.
      }
    }
    throw error;
  }
};

async function _pr88PopupStoredRecord() {
  try {
    const stored = await chrome.storage.local.get(PR88_INSTANT_POPUP_SUBTREE_STORAGE_KEY);
    const value = stored?.[PR88_INSTANT_POPUP_SUBTREE_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

function _pr88PopupPublicRecord(record) {
  if (!record || typeof record !== "object") return null;
  return {
    schemaVersion: Number.isInteger(record.schemaVersion) ? record.schemaVersion : null,
    capturedAtFailure: record.capturedAtFailure === true,
    failureCode: typeof record.failureCode === "string" ? record.failureCode : "UNKNOWN",
    failureReason: typeof record.failureReason === "string" ? record.failureReason : null,
    captureStatus: typeof record.captureStatus === "string" ? record.captureStatus : "UNKNOWN",
    captureTabId: Number.isInteger(record.captureTabId) ? record.captureTabId : null,
    routeKind: typeof record.routeKind === "string" ? record.routeKind : null,
    observedConversationId: typeof record.observedConversationId === "string" ? record.observedConversationId : null,
    rawUrlExported: false,
    rawTextExported: false,
    rawHtmlExported: false,
    leaseIdExported: false,
    zeroProductWrites: true,
    automaticRetry: false,
    candidateCapDealiased: record.candidateCapDealiased === true,
    globalCandidateCapUsed: record.globalCandidateCapUsed === true,
    topology: record.topology && typeof record.topology === "object" ? record.topology : {}
  };
}

executeNativeTurn = async function _executeNativeTurnWithInstantPopupSubtreeForensics(message) {
  if (message?.characterizeInstantFailureForensicsSupport === true) {
    const prior = await _pr88PopupPriorExecuteNativeTurn(message);
    return {
      ...prior,
      popupSubtreeCaptureSupported: true,
      popupLocalTraversalSupported: true,
      modeLabelActionableAncestorMappingSupported: true,
      candidateCapDealiasingSupported: true,
      popupEvidencePersistenceSupported: true,
      rawPopupTextRedactionSupported: true
    };
  }

  if (message?.characterizeInstantFailureForensicsRecord === true) {
    const prior = await _pr88PopupPriorExecuteNativeTurn(message);
    const expectedLeaseId = _pr88PopupLeaseId(message?.expectedBrowserAuthorityLeaseId);
    const stored = await _pr88PopupStoredRecord();
    const popupAvailable = (
      expectedLeaseId !== null &&
      stored !== null &&
      _pr88PopupLeaseId(stored.leaseId) === expectedLeaseId
    );
    return {
      ...prior,
      popupSubtreeRecordAvailable: popupAvailable,
      popupSubtree: popupAvailable ? _pr88PopupPublicRecord(stored) : null
    };
  }

  return _pr88PopupPriorExecuteNativeTurn(message);
};
