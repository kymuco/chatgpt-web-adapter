// PR9.2 schema-29 exact-request protocol conversation-id consensus repair.
//
// The authenticated schema-28 one-write probe proved that the protected image
// write committed and ChatGPT answered, while the exact protected response body
// decoded successfully and contained JSON SSE data records but zero
// `stream_handoff` records. Schema 28 therefore failed after commit because it
// treated one transport event type as the identity authority instead of treating
// the exact protected request body and recognized protocol identity slots as the
// causal boundary.
//
// Current ChatGPT /backend-api/f/conversation SSE can carry conversation identity
// in either a top-level `conversation_id` field or in the root delta-add envelope
// `{p:"", o:"add", v:{..., conversation_id:"..."}}`. Schema 29 accepts only
// those two recognized protocol slots from Network.getResponseBody for the exact
// protected requestId. Arbitrary nested message/content/tool data can never supply
// identity. Every observed recognized conversation id must agree; disagreement
// fails closed. A `stream_handoff.conversation_id` remains valid as a top-level
// special case, but stream_handoff is no longer required. Route state remains
// diagnostic only and automatic write retry remains forbidden.
//
// Schema 21 moved the page-side arm marker to the validated click boundary:
// immediately before `button.click()` in the same synchronous renderer task,
// after every attachment/deadline/Send-button validation has succeeded. That
// supersedes schema 20's older requirement that exactly one conversation POST may
// occur during the entire remaining page-turn lifetime. Schema 29 therefore binds
// request authority to the FIRST conversation POST observed after that validated
// click-boundary arm. Later post-arm conversation POSTs are diagnostic only and
// cannot retroactively invalidate the already selected exact request. Pre-arm
// requests still have zero authority, the selected first request must not carry
// `hasUserGesture === true`, and the exact selected response body must still yield
// one conflict-free protocol conversation-id consensus.

const _pr92Schema29PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema29PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema29PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const PR92_SCHEMA29_REPAIR_SCHEMA = 29;
const PR92_SCHEMA29_IDENTITY_AUTHORITY =
  "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS";
const PR92_SCHEMA29_REQUEST_CORRELATION =
  "VALIDATED_CLICK_ARMED_FIRST_CONVERSATION_POST";
const PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";

let _pr92Schema29LastIdentityParseDiagnostics = null;
let _pr92Schema29LastSubmitCorrelationDiagnostics = null;

function _pr92Schema29NonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function _pr92Schema29ExtractRequestBoundConversationMetadata(body, base64Encoded) {
  const decoded = _pr92Schema28DecodeResponseBody(body, base64Encoded);
  const diagnostics = {
    bodyDecoded: typeof decoded === "string",
    base64Encoded: base64Encoded === true,
    parsedJsonDataRecords: 0,
    protocolConversationIdRecordCount: 0,
    topLevelConversationIdRecordCount: 0,
    rootAddValueConversationIdRecordCount: 0,
    distinctProtocolConversationIdCount: 0,
    protocolConversationIdSourceKinds: [],
    streamHandoffCount: 0,
    conflictingConversationIds: false,
    conflictingTurnExchangeIds: false
  };
  if (typeof decoded !== "string") {
    return {
      conversationId: null,
      turnExchangeId: null,
      diagnostics
    };
  }

  const conversationIds = new Set();
  const turnExchangeIds = new Set();
  const sourceKinds = new Set();

  for (const rawLine of decoded.split(/\r?\n/)) {
    if (!rawLine.startsWith("data:")) continue;
    const payloadText = rawLine.slice(5).trim();
    if (!payloadText || payloadText === "[DONE]" || !payloadText.startsWith("{")) {
      continue;
    }

    let payload;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      continue;
    }
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
      continue;
    }
    diagnostics.parsedJsonDataRecords += 1;

    const eventType = _pr92Schema29NonEmptyString(payload.type);
    if (eventType === "stream_handoff") diagnostics.streamHandoffCount += 1;

    let topLevelConversationId = null;
    if (Object.prototype.hasOwnProperty.call(payload, "conversation_id")) {
      topLevelConversationId = _pr92Schema29NonEmptyString(payload.conversation_id);
    }
    if (topLevelConversationId) {
      diagnostics.protocolConversationIdRecordCount += 1;
      diagnostics.topLevelConversationIdRecordCount += 1;
      conversationIds.add(topLevelConversationId);
      sourceKinds.add("top-level");

      if (Object.prototype.hasOwnProperty.call(payload, "turn_exchange_id")) {
        const candidateTurnExchangeId = _pr92Schema29NonEmptyString(
          payload.turn_exchange_id
        );
        if (candidateTurnExchangeId) turnExchangeIds.add(candidateTurnExchangeId);
      }
    }

    const rootAddValue =
      payload.p === "" &&
      payload.o === "add" &&
      payload.v !== null &&
      typeof payload.v === "object" &&
      !Array.isArray(payload.v)
        ? payload.v
        : null;
    let rootAddConversationId = null;
    if (
      rootAddValue !== null &&
      Object.prototype.hasOwnProperty.call(rootAddValue, "conversation_id")
    ) {
      rootAddConversationId = _pr92Schema29NonEmptyString(
        rootAddValue.conversation_id
      );
    }
    if (rootAddConversationId) {
      diagnostics.protocolConversationIdRecordCount += 1;
      diagnostics.rootAddValueConversationIdRecordCount += 1;
      conversationIds.add(rootAddConversationId);
      sourceKinds.add("root-add-v");
    }
  }

  diagnostics.distinctProtocolConversationIdCount = conversationIds.size;
  diagnostics.protocolConversationIdSourceKinds = Array.from(sourceKinds).sort();
  diagnostics.conflictingConversationIds = conversationIds.size > 1;
  diagnostics.conflictingTurnExchangeIds = turnExchangeIds.size > 1;

  const conversationId = conversationIds.size === 1
    ? Array.from(conversationIds)[0]
    : null;
  const turnExchangeId = conversationId !== null && turnExchangeIds.size === 1
    ? Array.from(turnExchangeIds)[0]
    : null;

  return {
    conversationId,
    turnExchangeId,
    diagnostics
  };
}

function _pr92Schema29EvaluateSubmitCorrelation(context) {
  const observed = Array.isArray(context?.schema20PostArmConversationRequests)
    ? context.schema20PostArmConversationRequests
    : [];
  const markerObserved = context?.schema20ProtectedSubmitMarkerObserved === true;
  const firstRequest = observed.length > 0 ? observed[0] : null;
  const firstRequestId = _pr92Schema29NonEmptyString(firstRequest?.requestId);
  const firstRequestHadUserGesture = firstRequest?.hasUserGesture === true;
  const ok =
    markerObserved &&
    firstRequestId !== null &&
    firstRequestHadUserGesture === false;

  return {
    ok,
    markerObserved,
    postArmConversationRequestCount: observed.length,
    firstRequestId,
    firstRequestHadUserGesture,
    exactlyOnePostArmConversationRequestRequired: false,
    additionalPostArmConversationRequestsAuthoritative: false
  };
}

extractSafeStreamMetadata = function _pr92Schema29ExtractSafeStreamMetadata(
  body,
  base64Encoded
) {
  // Preserve the complete schema-28 and earlier observer chain for responseHints
  // and other non-identity side effects. Its returned IDs are deliberately ignored.
  try {
    _pr92Schema29PriorExtractSafeStreamMetadata(body, base64Encoded);
  } catch {
    // Observability must never perturb the request-bound identity path.
  }

  const parsed = _pr92Schema29ExtractRequestBoundConversationMetadata(
    body,
    base64Encoded
  );
  _pr92Schema29LastIdentityParseDiagnostics = { ...parsed.diagnostics };

  // Schema 19 consumes these fields after schema 17 reads Network.getResponseBody
  // for the exact completed protected requestId. Overwrite any older parser result
  // so only schema-29 protocol-slot consensus can satisfy new-chat identity.
  const context = _pr92ActiveRichInputContext;
  if (context !== null) {
    context.schema19CausalConversationId =
      typeof parsed.conversationId === "string" && parsed.conversationId
        ? parsed.conversationId
        : null;
    context.schema19CausalTurnExchangeId =
      typeof parsed.turnExchangeId === "string" && parsed.turnExchangeId
        ? parsed.turnExchangeId
        : null;
  }

  return {
    conversationId: parsed.conversationId,
    turnExchangeId: parsed.turnExchangeId
  };
};

executeOfficialPageTurn = async function _pr92Schema29ExecuteOfficialPageTurn(args) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema29PriorExecuteOfficialPageTurn(args);

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
    // Deliberately bypass only schema 20's obsolete post-return exactly-one
    // request gate. `_pr92Schema20PriorExecuteOfficialPageTurn` is schema 19,
    // which retains schema 17's request/completion tracking. The global
    // schema-20 `isConversationWrite` predicate remains active, so schema 17
    // still cannot select any conversation POST until this observer sees the
    // schema-21 validated-click-boundary arm marker.
    const result = await _pr92Schema20PriorExecuteOfficialPageTurn(args);
    if (
      result?.diagnostics?.conversationRequestSeen !== true ||
      result?.diagnostics?.loadingFinished !== true
    ) {
      return result;
    }

    const correlation = _pr92Schema29EvaluateSubmitCorrelation(context);
    _pr92Schema29LastSubmitCorrelationDiagnostics = {
      markerObserved: correlation.markerObserved,
      postArmConversationRequestCount: correlation.postArmConversationRequestCount,
      firstRequestHadUserGesture: correlation.firstRequestHadUserGesture
    };
    if (!correlation.ok) {
      throw new Error(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR);
    }

    const isNewChatRichTurn = context.schema19RequestedConversationId == null;
    return {
      ...result,
      diagnostics: {
        ...result.diagnostics,
        ...(isNewChatRichTurn
          ? {
              conversationIdentityAuthority: PR92_SCHEMA29_IDENTITY_AUTHORITY,
              routeConversationIdentityAuthoritative: false,
              requestBoundProtocolConversationIdConsensus: true
            }
          : {}),
        protectedSubmitRequestCorrelation: PR92_SCHEMA29_REQUEST_CORRELATION,
        protectedSubmitArmMarkerObserved: true,
        protectedSubmitRequestId: correlation.firstRequestId,
        postArmConversationRequestCount: correlation.postArmConversationRequestCount,
        protectedSubmitRequestHadUserGesture: false,
        preArmConversationRequestsAuthoritative: false,
        firstPostArmConversationRequestAuthoritative: true,
        additionalPostArmConversationRequestsAuthoritative: false,
        exactlyOnePostArmConversationRequestRequired: false
      }
    };
  } finally {
    chrome.debugger.onEvent.removeListener(observer);
    context.schema20ProtectedSubmitArmed = false;
  }
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema29Repair(message) {
  const isPotentialNewChatRichWrite =
    Array.isArray(message?.attachmentPaths) &&
    message.attachmentPaths.length > 0 &&
    !(typeof message?.conversationId === "string" && message.conversationId.trim());
  if (isPotentialNewChatRichWrite) {
    _pr92Schema29LastIdentityParseDiagnostics = null;
    _pr92Schema29LastSubmitCorrelationDiagnostics = null;
  }

  let result;
  try {
    result = await _pr92Schema29PriorExecuteNativeTurn(message);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (detail.startsWith(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR)) {
      const diagnostics = _pr92Schema29LastIdentityParseDiagnostics;
      const correlation = _pr92Schema29LastSubmitCorrelationDiagnostics;
      const suffix = diagnostics
        ? `:SCHEMA29:bodyDecoded=${diagnostics.bodyDecoded === true}` +
          `:base64Encoded=${diagnostics.base64Encoded === true}` +
          `:parsedJsonDataRecords=${Number(diagnostics.parsedJsonDataRecords) || 0}` +
          `:protocolConversationIdRecordCount=${Number(diagnostics.protocolConversationIdRecordCount) || 0}` +
          `:topLevelConversationIdRecordCount=${Number(diagnostics.topLevelConversationIdRecordCount) || 0}` +
          `:rootAddValueConversationIdRecordCount=${Number(diagnostics.rootAddValueConversationIdRecordCount) || 0}` +
          `:distinctProtocolConversationIdCount=${Number(diagnostics.distinctProtocolConversationIdCount) || 0}` +
          `:streamHandoffCount=${Number(diagnostics.streamHandoffCount) || 0}` +
          `:conflictingConversationIds=${diagnostics.conflictingConversationIds === true}` +
          `:conflictingTurnExchangeIds=${diagnostics.conflictingTurnExchangeIds === true}` +
          `:protocolConversationIdSourceKinds=${diagnostics.protocolConversationIdSourceKinds.join(",")}` +
          `:protectedSubmitMarkerObserved=${correlation?.markerObserved === true}` +
          `:postArmConversationRequestCount=${Number(correlation?.postArmConversationRequestCount) || 0}` +
          `:firstPostArmRequestHadUserGesture=${correlation?.firstRequestHadUserGesture === true}`
        : ":SCHEMA29:identityParserNotReached=true";
      throw new Error(`${PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR}${suffix}`);
    }
    throw error;
  }

  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA29_REPAIR_SCHEMA,
    newChatConversationIdentityAuthority: PR92_SCHEMA29_IDENTITY_AUTHORITY,
    requestBoundProtocolConversationIdAuthority: true,
    requestBoundProtocolConversationIdConsensusRequired: true,
    topLevelConversationIdAuthority: true,
    rootAddValueConversationIdAuthority: true,
    unrecognizedNestedConversationIdCanSatisfyIdentity: false,
    streamHandoffRequiredForCausalConversationIdentity: false,
    conflictingRequestBoundConversationIdsFailClosed: true,
    routeConversationIdentityAuthoritative: false,
    protectedSubmitRequestCorrelation: PR92_SCHEMA29_REQUEST_CORRELATION,
    firstPostArmConversationRequestAuthoritative: true,
    additionalPostArmConversationRequestsAuthoritative: false,
    validatedClickBoundaryFirstRequestSelection: true,
    exactlyOnePostArmConversationRequestRequired: false,
    userGesturePostArmRequestCanSatisfyProtectedSubmit: false,
    ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: false,
    automaticWriteRetryAfterSubmitCorrelationFailure: false,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
