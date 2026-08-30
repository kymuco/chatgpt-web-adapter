// PR9.2 schema-29 exact-request top-level conversation-id consensus repair.
//
// The authenticated schema-28 one-write probe proved that the protected image
// write committed and ChatGPT answered, while the exact protected response body
// decoded successfully and contained 25 JSON SSE data records but zero
// `stream_handoff` records. Schema 28 therefore failed after commit because it
// treated one transport event type as the identity authority instead of treating
// the exact protected request body itself as the causal boundary.
//
// Schema 29 keeps the same exact-request authority boundary established by
// schemas 17/19/20/21. It accepts only non-empty TOP-LEVEL `conversation_id`
// fields from JSON SSE data records in Network.getResponseBody for the exact
// protected requestId. Nested content can never supply identity. All observed
// top-level conversation ids must agree; disagreement fails closed. A
// `stream_handoff.conversation_id` remains valid, but stream_handoff is no longer
// required. Route state remains diagnostic only and automatic write retry remains
// forbidden.

const _pr92Schema29PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema29PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema29PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const PR92_SCHEMA29_REPAIR_SCHEMA = 29;
const PR92_SCHEMA29_IDENTITY_AUTHORITY =
  "NETWORK_REQUEST_BOUND_TOP_LEVEL_CONVERSATION_ID_CONSENSUS";
const PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";

let _pr92Schema29LastIdentityParseDiagnostics = null;

function _pr92Schema29ExtractRequestBoundConversationMetadata(body, base64Encoded) {
  const decoded = _pr92Schema28DecodeResponseBody(body, base64Encoded);
  const diagnostics = {
    bodyDecoded: typeof decoded === "string",
    base64Encoded: base64Encoded === true,
    parsedJsonDataRecords: 0,
    topLevelConversationIdRecordCount: 0,
    distinctTopLevelConversationIdCount: 0,
    topLevelConversationIdEventTypes: [],
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
  const eventTypes = new Set();

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

    const eventType = typeof payload.type === "string" && payload.type.trim()
      ? payload.type.trim()
      : "<untyped>";
    if (eventType === "stream_handoff") diagnostics.streamHandoffCount += 1;

    if (!Object.prototype.hasOwnProperty.call(payload, "conversation_id")) continue;
    const candidateConversationId =
      typeof payload.conversation_id === "string" && payload.conversation_id.trim()
        ? payload.conversation_id.trim()
        : null;
    if (!candidateConversationId) continue;

    diagnostics.topLevelConversationIdRecordCount += 1;
    conversationIds.add(candidateConversationId);
    eventTypes.add(eventType);

    if (Object.prototype.hasOwnProperty.call(payload, "turn_exchange_id")) {
      const candidateTurnExchangeId =
        typeof payload.turn_exchange_id === "string" && payload.turn_exchange_id.trim()
          ? payload.turn_exchange_id.trim()
          : null;
      if (candidateTurnExchangeId) turnExchangeIds.add(candidateTurnExchangeId);
    }
  }

  diagnostics.distinctTopLevelConversationIdCount = conversationIds.size;
  diagnostics.topLevelConversationIdEventTypes = Array.from(eventTypes).sort().slice(0, 16);
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
  // so only schema-29 consensus can satisfy new-chat identity.
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
  const result = await _pr92Schema29PriorExecuteOfficialPageTurn(args);
  const context = _pr92ActiveRichInputContext;
  const isNewChatRichTurn = context !== null && context.schema19RequestedConversationId == null;
  if (!isNewChatRichTurn || typeof result?.conversationId !== "string" || !result.conversationId) {
    return result;
  }

  return {
    ...result,
    diagnostics: {
      ...result.diagnostics,
      conversationIdentityAuthority: PR92_SCHEMA29_IDENTITY_AUTHORITY,
      routeConversationIdentityAuthoritative: false,
      requestBoundTopLevelConversationIdConsensus: true
    }
  };
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema29Repair(message) {
  const isPotentialNewChatRichWrite =
    Array.isArray(message?.attachmentPaths) &&
    message.attachmentPaths.length > 0 &&
    !(typeof message?.conversationId === "string" && message.conversationId.trim());
  if (isPotentialNewChatRichWrite) {
    _pr92Schema29LastIdentityParseDiagnostics = null;
  }

  let result;
  try {
    result = await _pr92Schema29PriorExecuteNativeTurn(message);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (detail.startsWith(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR)) {
      const diagnostics = _pr92Schema29LastIdentityParseDiagnostics;
      const suffix = diagnostics
        ? `:SCHEMA29:bodyDecoded=${diagnostics.bodyDecoded === true}` +
          `:base64Encoded=${diagnostics.base64Encoded === true}` +
          `:parsedJsonDataRecords=${Number(diagnostics.parsedJsonDataRecords) || 0}` +
          `:topLevelConversationIdRecordCount=${Number(diagnostics.topLevelConversationIdRecordCount) || 0}` +
          `:distinctTopLevelConversationIdCount=${Number(diagnostics.distinctTopLevelConversationIdCount) || 0}` +
          `:streamHandoffCount=${Number(diagnostics.streamHandoffCount) || 0}` +
          `:conflictingConversationIds=${diagnostics.conflictingConversationIds === true}` +
          `:conflictingTurnExchangeIds=${diagnostics.conflictingTurnExchangeIds === true}` +
          `:topLevelConversationIdEventTypes=${diagnostics.topLevelConversationIdEventTypes.join(",")}`
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
    requestBoundTopLevelConversationIdAuthority: true,
    requestBoundTopLevelConversationIdConsensusRequired: true,
    nestedConversationIdCanSatisfyIdentity: false,
    streamHandoffRequiredForCausalConversationIdentity: false,
    conflictingRequestBoundConversationIdsFailClosed: true,
    routeConversationIdentityAuthoritative: false,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
