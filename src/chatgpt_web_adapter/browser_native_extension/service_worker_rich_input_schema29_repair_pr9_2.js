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
// The first authenticated schema-29 full-gate attempt later proved another useful
// fact: the exact selected response body carried twelve recognized conversation-id
// records, all agreeing on one id, yet the inherited schema-20 submit-correlation
// layer still rejected the committed turn. Do not weaken that causal guard from a
// single observation. Instead preserve schema-20 authority unchanged and surface
// content-safe correlation counters on the same committed failure so one bounded
// live characterization can distinguish marker absence, post-arm multiplicity,
// and user-gesture rejection without exposing request ids or request content.

const _pr92Schema29PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema29PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema29PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const PR92_SCHEMA29_REPAIR_SCHEMA = 29;
const PR92_SCHEMA29_IDENTITY_AUTHORITY =
  "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS";
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

function _pr92Schema29CaptureSubmitCorrelationDiagnostics(context) {
  const observed = Array.isArray(context?.schema20PostArmConversationRequests)
    ? context.schema20PostArmConversationRequests
    : [];
  const markerObserved = context?.schema20ProtectedSubmitMarkerObserved === true;
  const userGestureRequestCount = observed.filter(
    (entry) => entry?.hasUserGesture === true
  ).length;
  const nonUserGestureRequestCount = Math.max(
    0,
    observed.length - userGestureRequestCount
  );
  const exactlyOnePostArmRequest = observed.length === 1;
  const soleRequestHadUserGesture = exactlyOnePostArmRequest
    ? observed[0]?.hasUserGesture === true
    : null;
  return {
    markerObserved,
    postArmConversationRequestCount: observed.length,
    postArmUserGestureRequestCount: userGestureRequestCount,
    postArmNonUserGestureRequestCount: nonUserGestureRequestCount,
    exactlyOnePostArmRequest,
    soleRequestHadUserGesture,
    schema20CorrelationWouldPass:
      markerObserved &&
      exactlyOnePostArmRequest &&
      soleRequestHadUserGesture === false
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
  try {
    const result = await _pr92Schema29PriorExecuteOfficialPageTurn(args);
    const isNewChatRichTurn =
      context !== null && context.schema19RequestedConversationId == null;
    if (
      !isNewChatRichTurn ||
      typeof result?.conversationId !== "string" ||
      !result.conversationId
    ) {
      return result;
    }

    return {
      ...result,
      diagnostics: {
        ...result.diagnostics,
        conversationIdentityAuthority: PR92_SCHEMA29_IDENTITY_AUTHORITY,
        routeConversationIdentityAuthoritative: false,
        requestBoundProtocolConversationIdConsensus: true
      }
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (detail.startsWith(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR)) {
      _pr92Schema29LastSubmitCorrelationDiagnostics =
        _pr92Schema29CaptureSubmitCorrelationDiagnostics(context);
    }
    throw error;
  }
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema29Repair(message) {
  const isRichWrite =
    Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0;
  if (isRichWrite) {
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
      const identitySuffix = diagnostics
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
          `:protocolConversationIdSourceKinds=${diagnostics.protocolConversationIdSourceKinds.join(",")}`
        : ":SCHEMA29:identityParserNotReached=true";
      const correlationSuffix = correlation
        ? `:protectedSubmitMarkerObserved=${correlation.markerObserved === true}` +
          `:postArmConversationRequestCount=${Number(correlation.postArmConversationRequestCount) || 0}` +
          `:postArmUserGestureRequestCount=${Number(correlation.postArmUserGestureRequestCount) || 0}` +
          `:postArmNonUserGestureRequestCount=${Number(correlation.postArmNonUserGestureRequestCount) || 0}` +
          `:exactlyOnePostArmRequest=${correlation.exactlyOnePostArmRequest === true}` +
          `:soleRequestHadUserGesture=${correlation.soleRequestHadUserGesture === null ? "unknown" : correlation.soleRequestHadUserGesture === true}` +
          `:schema20CorrelationWouldPass=${correlation.schema20CorrelationWouldPass === true}`
        : ":submitCorrelationDiagnosticsUnavailable=true";
      throw new Error(
        `${PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR}${identitySuffix}${correlationSuffix}`
      );
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
    submitCorrelationFailureDiagnosticsAvailable: true,
    submitCorrelationAuthorityUnchanged: true,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
