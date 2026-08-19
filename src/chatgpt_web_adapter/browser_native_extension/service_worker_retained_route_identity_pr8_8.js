// PR8.8 retained runtime-tab route identity forensics.
//
// Loaded after service_worker_retained_picker_forensics_pr8_8.js. This layer
// adds route-only characterization RPCs. It never attaches the debugger, reads
// DOM/AX topology, clicks product UI, inserts text, submits a conversation
// request, navigates/reloads a tab, or closes Browser Authority.

const PR88_RETAINED_ROUTE_IDENTITY_SCHEMA_VERSION = 1;
const _pr88RoutePriorExecuteNativeTurn = executeNativeTurn;

function _pr88RouteConversationId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (!conversationId || conversationId.includes("/") || conversationId.includes("?") || conversationId.includes("#")) {
    return null;
  }
  return conversationId;
}

function _pr88RouteIdentity(urlValue, expectedConversationId) {
  const url = typeof urlValue === "string" ? urlValue : "";
  let pathname = "/";
  try {
    pathname = new URL(url).pathname || "/";
  } catch {
    pathname = "/";
  }
  const observedConversationId = _pr88RouteConversationId(conversationIdFromUrl(url));
  let routeKind = "OTHER_CHATGPT";
  if (observedConversationId !== null) routeKind = "CONVERSATION";
  else if (pathname === "/" || pathname === "") routeKind = "ROOT";

  const conversationMatchesExpected = observedConversationId === expectedConversationId;
  let routeIdentityStatus = "OTHER_CHATGPT_ROUTE";
  if (conversationMatchesExpected) routeIdentityStatus = "EXPECTED_CONVERSATION_MATCH";
  else if (routeKind === "CONVERSATION") routeIdentityStatus = "OTHER_CONVERSATION";
  else if (routeKind === "ROOT") routeIdentityStatus = "ROOT_ROUTE";

  return {
    routeKind,
    observedConversationId,
    expectedConversationId,
    conversationMatchesExpected,
    routeIdentityStatus,
    rawUrlExported: false,
    queryExported: false,
    fragmentExported: false
  };
}

function _pr88RouteQueryConflict(message) {
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
    message?.characterizeInstantSelectionRecord === true ||
    message?.characterizeRetainedPickerForensicsSupport === true ||
    message?.characterizeRetainedPickerSurfaceForensics === true
  );
}

async function _pr88RouteStoredLeaseIdSafe() {
  try {
    if (typeof _pr88StoredLeaseId === "function") return await _pr88StoredLeaseId();
  } catch {}
  return null;
}

async function _pr88RouteDebuggerAttached(tabId) {
  try {
    const targets = await chrome.debugger.getTargets();
    return Boolean(targets.find((target) => target.tabId === tabId)?.attached);
  } catch {
    return null;
  }
}

async function _pr88RetainedRouteIdentityProbe(message) {
  if (_pr88RouteQueryConflict(message)) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_FLAG_CONFLICT");
  }
  const conversationId = _pr88RouteConversationId(message?.conversationId);
  if (conversationId === null) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_CONVERSATION_REQUIRED");
  }
  const expectedTabId = Number.isInteger(message?.expectedRuntimeTabId)
    ? message.expectedRuntimeTabId
    : null;
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_RUNTIME_TAB_REQUIRED");
  }
  if (expectedTabId !== null && runtimeTabId !== expectedTabId) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_RUNTIME_TAB_CHANGED");
  }

  const tabBefore = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tabBefore?.url || "")) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_TAB_NOT_CHATGPT");
  }
  const routeIdentity = _pr88RouteIdentity(tabBefore?.url || "", conversationId);
  const debuggerAttachedBefore = await _pr88RouteDebuggerAttached(runtimeTabId);

  // Deliberately no debugger attach and no DOM/AX inspection. The second tab
  // read proves the retained resource/route stayed stable while taking evidence.
  const tabAfter = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tabAfter?.url || "")) {
    throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_TAB_LEFT_CHATGPT");
  }
  const routeIdentityAfter = _pr88RouteIdentity(tabAfter?.url || "", conversationId);
  const runtimeTabIdAfter = await storedRuntimeTabId();
  const debuggerAttachedAfter = await _pr88RouteDebuggerAttached(runtimeTabId);
  const leaseId = await _pr88RouteStoredLeaseIdSafe();
  const routeIdentityStable = (
    routeIdentity.routeKind === routeIdentityAfter.routeKind &&
    routeIdentity.observedConversationId === routeIdentityAfter.observedConversationId &&
    routeIdentity.routeIdentityStatus === routeIdentityAfter.routeIdentityStatus
  );

  return {
    probeContext: "retained_runtime_tab_route_identity_forensics",
    readOnly: true,
    zeroProductWrites: true,
    retainedRouteIdentitySupported: true,
    retainedRouteIdentitySchemaVersion: PR88_RETAINED_ROUTE_IDENTITY_SCHEMA_VERSION,
    conversationId,
    expectedRuntimeTabId: expectedTabId,
    runtimeTabId,
    runtimeTabIdAfter,
    runtimeTabRetained: runtimeTabIdAfter === runtimeTabId,
    browserAuthorityLeaseId: leaseId,
    leaseIdPresent: leaseId !== null,
    routeIdentity,
    routeIdentityAfter,
    routeIdentityStable,
    routeMismatchCharacterized: routeIdentity.conversationMatchesExpected !== true,
    domAxInspectionPerformed: false,
    conversationWriteGuardObserved: false,
    conversationWriteCount: null,
    tabWasActive: Boolean(tabBefore?.active),
    tabActiveAfter: Boolean(tabAfter?.active),
    tabActivatedDuringProbe: false,
    foregroundActivationObserved: Boolean(tabBefore?.active || tabAfter?.active),
    debuggerAttachedBefore,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _executeNativeTurnWithRetainedRouteIdentity(message) {
  if (message?.characterizeRetainedRouteIdentitySupport === true) {
    if (_pr88RouteQueryConflict(message) || message?.conversationId != null) {
      throw new Error("PR8_8_RETAINED_ROUTE_IDENTITY_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "retained_runtime_tab_route_identity_support",
      readOnly: true,
      zeroProductWrites: true,
      retainedRouteIdentitySupported: true,
      retainedRouteIdentitySchemaVersion: PR88_RETAINED_ROUTE_IDENTITY_SCHEMA_VERSION,
      retainedExistingTabRouteProbeSupported: true,
      conversationMismatchCharacterizationSupported: true,
      routeMismatchDomAxSuppressionSupported: true,
      rawRouteRedactionSupported: true,
      exactMatchSurfaceForensicsDelegationSupported: true
    };
  }

  if (message?.characterizeRetainedRouteIdentity === true) {
    return _pr88RetainedRouteIdentityProbe(message);
  }

  return _pr88RoutePriorExecuteNativeTurn(message);
};
