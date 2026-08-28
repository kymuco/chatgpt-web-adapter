// PR9.2 schema-20 protected-submit request-correlation closure.
//
// Loaded after schema 19. Schema 19 made new-chat identity request-bound, but
// schema 17 still selected the first conversation POST observed after Network
// setup. A manual/user conversation POST during composer setup could therefore
// become the request whose response stream supplied the causal conversation id.
//
// Schema 20 narrows request authority without changing the protected-submit
// primitive. A unique page-side arm marker is emitted inside the same synchronous
// Runtime.evaluate page task that then performs schema-7 attachment validation
// and button.click(). Schema-17 conversation-write authority remains closed until
// the extension observes that exact marker. A user page task cannot interleave
// between the marker and the click. A second observer records every raw
// conversation POST after the marker; transport success additionally requires
// exactly one such POST and it must not carry CDP's user-gesture bit. Ambiguous
// post-arm traffic fails closed as known-write/readback-incomplete, with no retry.

const _pr92Schema20PriorCreateTurnContext = _pr92CreateTurnContext;
const _pr92Schema20PriorAtomicAttachmentSubmitExpression =
  _pr92Schema7AtomicAttachmentSubmitExpression;
const _pr92Schema20PriorIsConversationWrite = isConversationWrite;
const _pr92Schema20PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema20PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA20_REPAIR_SCHEMA = 20;
const PR92_SCHEMA20_REQUEST_CORRELATION =
  "PAGE_SIDE_ARMED_SINGLE_CONVERSATION_POST";
const PR92_SCHEMA20_IDENTITY_AUTHORITY =
  "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF";
const PR92_SCHEMA20_ARM_MARKER_PREFIX =
  "__PR92_SCHEMA20_PROTECTED_SUBMIT_ARM__:";

function _pr92Schema20RandomMarker() {
  let nonce = "";
  try {
    if (typeof crypto?.randomUUID === "function") nonce = crypto.randomUUID();
  } catch {}
  if (!nonce) {
    nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  }
  return `${PR92_SCHEMA20_ARM_MARKER_PREFIX}${nonce}`;
}

_pr92CreateTurnContext = function _pr92Schema20CreateTurnContext(message) {
  const context = _pr92Schema20PriorCreateTurnContext(message);
  context.schema20ProtectedSubmitArmed = false;
  context.schema20ProtectedSubmitArmedAt = null;
  context.schema20ProtectedSubmitMarker = _pr92Schema20RandomMarker();
  context.schema20ProtectedSubmitMarkerObserved = false;
  context.schema20PostArmConversationRequests = [];
  return context;
};

// Schema 7 calls this expression builder immediately before dispatching the only
// Runtime.evaluate command that may click. Wrap that immutable expression so the
// unique marker is emitted in the renderer in the same synchronous page task as
// final attachment validation and button.click(). No page/user task can execute
// between the marker and the protected click.
_pr92Schema7AtomicAttachmentSubmitExpression = function _pr92Schema20PageSideArmProtectedSubmit(
  selector,
  deadlineEpochMs,
  expectedNames
) {
  const expression = _pr92Schema20PriorAtomicAttachmentSubmitExpression(
    selector,
    deadlineEpochMs,
    expectedNames
  );
  const context = _pr92ActiveRichInputContext;
  if (context === null) return expression;
  const encodedMarker = JSON.stringify(context.schema20ProtectedSubmitMarker);
  return `(() => {
    try { console.debug(${encodedMarker}); } catch {}
    return (${expression});
  })()`;
};

// Schema 17 calls this predicate from its Network.requestWillBeSent listener.
// During a rich turn, conversation writes have no authority until the exact
// page-side arm marker from the protected-submit task has been observed.
// Text-only behavior remains exactly the prior predicate.
isConversationWrite = function _pr92Schema20SubmitBoundConversationWrite(url, method) {
  if (!_pr92Schema20PriorIsConversationWrite(url, method)) return false;
  const context = _pr92ActiveRichInputContext;
  if (context === null) return true;
  return context.schema20ProtectedSubmitArmed === true;
};

function _pr92Schema20ObserveArmMarker(context, params) {
  if (context === null || context.schema20ProtectedSubmitArmed === true) return;
  const expected = context.schema20ProtectedSubmitMarker;
  if (typeof expected !== "string" || !expected) return;
  const args = Array.isArray(params?.args) ? params.args : [];
  const matched = args.some((arg) => arg?.value === expected);
  if (!matched) return;
  context.schema20ProtectedSubmitMarkerObserved = true;
  context.schema20ProtectedSubmitArmed = true;
  context.schema20ProtectedSubmitArmedAt = performance.now();
}

function _pr92Schema20RecordPostArmConversationRequest(context, params) {
  if (context === null || context.schema20ProtectedSubmitArmed !== true) return;
  const request = params?.request;
  if (
    !_pr92Schema20PriorIsConversationWrite(
      request?.url || "",
      request?.method || ""
    )
  ) {
    return;
  }
  const requestId = typeof params?.requestId === "string" ? params.requestId : "";
  if (!requestId) return;
  const existing = context.schema20PostArmConversationRequests.find(
    (entry) => entry.requestId === requestId
  );
  if (existing) return;
  context.schema20PostArmConversationRequests.push({
    requestId,
    hasUserGesture: params?.hasUserGesture === true
  });
}

executeOfficialPageTurn = async function _pr92Schema20ExecuteOfficialPageTurnWithSubmitBoundRequest(
  args
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema20PriorExecuteOfficialPageTurn(args);

  const tabId = args?.tabId;
  const observer = (source, method, params) => {
    if (source?.tabId !== tabId) return;
    if (method === "Runtime.consoleAPICalled") {
      _pr92Schema20ObserveArmMarker(context, params);
      return;
    }
    if (method === "Network.requestWillBeSent") {
      _pr92Schema20RecordPostArmConversationRequest(context, params);
    }
  };
  chrome.debugger.onEvent.addListener(observer);

  try {
    const result = await _pr92Schema20PriorExecuteOfficialPageTurn(args);
    if (
      result?.diagnostics?.conversationRequestSeen !== true ||
      result?.diagnostics?.loadingFinished !== true
    ) {
      return result;
    }

    const observed = Array.isArray(context.schema20PostArmConversationRequests)
      ? context.schema20PostArmConversationRequests
      : [];
    const markerObserved = context.schema20ProtectedSubmitMarkerObserved === true;
    const exactlyOnePostArmRequest = observed.length === 1;
    const soleRequest = exactlyOnePostArmRequest ? observed[0] : null;
    const soleRequestHasUserGesture = soleRequest?.hasUserGesture === true;

    if (!markerObserved || !exactlyOnePostArmRequest || soleRequestHasUserGesture) {
      // A conversation write is already known to have completed, but its causal
      // ownership is not uniquely attributable to the protected page-side submit.
      // Never report the wrong conversation and never retry the write.
      throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);
    }

    return {
      ...result,
      diagnostics: {
        ...result.diagnostics,
        protectedSubmitRequestCorrelation: PR92_SCHEMA20_REQUEST_CORRELATION,
        protectedSubmitArmMarkerObserved: true,
        protectedSubmitRequestId: soleRequest.requestId,
        postArmConversationRequestCount: observed.length,
        protectedSubmitRequestHadUserGesture: false,
        preArmConversationRequestsAuthoritative: false
      }
    };
  } finally {
    chrome.debugger.onEvent.removeListener(observer);
    context.schema20ProtectedSubmitArmed = false;
  }
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema20Repair(message) {
  const result = await _pr92Schema20PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA20_REPAIR_SCHEMA,
    newChatConversationIdentityAuthority: PR92_SCHEMA20_IDENTITY_AUTHORITY,
    protectedSubmitRequestCorrelation: PR92_SCHEMA20_REQUEST_CORRELATION,
    protectedSubmitRequestArmedByPageSideMarker: true,
    pageSideArmMarkerAndProtectedClickSameTask: true,
    preArmConversationRequestsAuthoritative: false,
    exactlyOnePostArmConversationRequestRequired: true,
    userGesturePostArmRequestCanSatisfyProtectedSubmit: false,
    ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: true,
    automaticWriteRetryAfterSubmitCorrelationFailure: false
  };
};
