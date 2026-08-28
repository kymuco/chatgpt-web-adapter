// PR9.2 schema-20 protected-submit request-correlation closure.
//
// Loaded after schema 19. Schema 19 made new-chat identity request-bound, but
// schema 17 still selected the first conversation POST observed after Network
// setup. A manual/user conversation POST during composer setup could therefore
// become the request whose response stream supplied the causal conversation id.
//
// Schema 20 narrows request authority without changing the protected-submit
// primitive. Conversation POST observation is armed only synchronously when the
// schema-7 atomic submit expression is constructed, immediately before the
// non-awaited Runtime.evaluate dispatch. All earlier conversation POSTs are
// invisible to schema-17 write authority. A second observer records every raw
// conversation POST after that arm. Transport success requires exactly one such
// POST and that request must not carry CDP's user-gesture bit. Multiple post-arm
// POSTs or a user-gesture candidate fail closed as a known-write/readback-
// incomplete state, with no automatic retry.

const _pr92Schema20PriorCreateTurnContext = _pr92CreateTurnContext;
const _pr92Schema20PriorAtomicAttachmentSubmitExpression =
  _pr92Schema7AtomicAttachmentSubmitExpression;
const _pr92Schema20PriorIsConversationWrite = isConversationWrite;
const _pr92Schema20PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema20PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA20_REPAIR_SCHEMA = 20;
const PR92_SCHEMA20_REQUEST_CORRELATION =
  "PROTECTED_SUBMIT_ARMED_SINGLE_CONVERSATION_POST";
const PR92_SCHEMA20_IDENTITY_AUTHORITY =
  "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF";

_pr92CreateTurnContext = function _pr92Schema20CreateTurnContext(message) {
  const context = _pr92Schema20PriorCreateTurnContext(message);
  context.schema20ProtectedSubmitArmed = false;
  context.schema20ProtectedSubmitArmedAt = null;
  context.schema20PostArmConversationRequests = [];
  return context;
};

// This hook runs inside schema 7 immediately before the Runtime.evaluate command
// that carries the atomic final validation + button.click() expression. The
// schema-7 caller performs no await between this expression construction and
// dispatch, so setup-time requests cannot cross the authority boundary.
_pr92Schema7AtomicAttachmentSubmitExpression = function _pr92Schema20ArmProtectedSubmit(
  selector,
  deadlineEpochMs,
  expectedNames
) {
  const context = _pr92ActiveRichInputContext;
  if (context !== null) {
    context.schema20ProtectedSubmitArmed = true;
    context.schema20ProtectedSubmitArmedAt = performance.now();
  }
  return _pr92Schema20PriorAtomicAttachmentSubmitExpression(
    selector,
    deadlineEpochMs,
    expectedNames
  );
};

// Schema 17 calls this predicate from its Network.requestWillBeSent listener.
// During a rich turn, conversation writes have no authority until the protected
// submit has been armed at the atomic dispatch boundary above. Text-only behavior
// remains exactly the prior predicate.
isConversationWrite = function _pr92Schema20SubmitBoundConversationWrite(url, method) {
  if (!_pr92Schema20PriorIsConversationWrite(url, method)) return false;
  const context = _pr92ActiveRichInputContext;
  if (context === null) return true;
  return context.schema20ProtectedSubmitArmed === true;
};

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
    if (source?.tabId !== tabId || method !== "Network.requestWillBeSent") return;
    _pr92Schema20RecordPostArmConversationRequest(context, params);
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
    const exactlyOnePostArmRequest = observed.length === 1;
    const soleRequest = exactlyOnePostArmRequest ? observed[0] : null;
    const soleRequestHasUserGesture = soleRequest?.hasUserGesture === true;

    if (!exactlyOnePostArmRequest || soleRequestHasUserGesture) {
      // At least one conversation write is already known to have completed, but
      // its causal ownership is not uniquely attributable to our protected
      // submit. Never report the wrong conversation and never retry the write.
      throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);
    }

    return {
      ...result,
      diagnostics: {
        ...result.diagnostics,
        protectedSubmitRequestCorrelation: PR92_SCHEMA20_REQUEST_CORRELATION,
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
    protectedSubmitRequestArmedAtAtomicDispatchBoundary: true,
    preArmConversationRequestsAuthoritative: false,
    exactlyOnePostArmConversationRequestRequired: true,
    userGesturePostArmRequestCanSatisfyProtectedSubmit: false,
    ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: true,
    automaticWriteRetryAfterSubmitCorrelationFailure: false
  };
};
