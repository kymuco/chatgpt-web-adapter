// PR9.2 schema-29 request-body-bound rich-submit and protocol identity closure.
//
// Earlier PR9.2 layers deliberately failed closed while the real ChatGPT rich
// request/response protocol was still being characterized. Authenticated runs
// then established two concrete facts:
//   1. current /backend-api/f/conversation SSE can expose one conflict-free
//      conversation id through recognized top-level/root-add protocol slots even
//      when `stream_handoff` is absent;
//   2. a valid rich turn can produce additional post-arm conversation POSTs, so
//      schema 20's historical "exactly one POST for the whole remaining turn"
//      rule is not a stable causal identity primitive.
//
// Schema 29 therefore closes correlation at the actual request boundary rather
// than at POST multiplicity. The schema-21 page-side arm marker still occurs
// immediately before the validated button.click() in the same renderer task.
// The FIRST conversation POST observed after that arm is still the exact request
// tracked by schema 17/19, but it is accepted only when its own request JSON proves
// that it contains exactly one matching user message for this turn: exact inserted
// text, a non-empty client message id, the expected rich-attachment count through
// recognized message attachment channels, and (for continuation) the exact
// requested conversation id. A new-chat request must not carry a conversation id.
//
// Additional post-arm conversation POSTs are non-authoritative. A duplicate of
// the same already-matched client message id is the same logical write; a second
// content-matching request with a different client message id is ambiguous and
// fails closed. `hasUserGesture` is retained only as diagnostics, never identity.
// Raw request text, postData, request ids, message ids, and conversation ids are
// never emitted in diagnostics.
//
// Response identity remains independently request-bound: Network.getResponseBody
// is read for the exact completed request id, recognized conversation-id protocol
// slots must all agree, route state is diagnostic only, and automatic write retry
// remains forbidden.

const _pr92Schema29PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema29PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema29PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const PR92_SCHEMA29_REPAIR_SCHEMA = 29;
const PR92_SCHEMA29_IDENTITY_AUTHORITY =
  "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS";
const PR92_SCHEMA29_REQUEST_CORRELATION =
  "VALIDATED_CLICK_REQUEST_BODY_USER_MESSAGE_IDENTITY";
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

function _pr92Schema29RequestMessageAttachmentChannels(message) {
  const content = message?.content;
  const parts = Array.isArray(content?.parts) ? content.parts : [];
  const pointerParts = parts.filter((part) => {
    if (part === null || typeof part !== "object" || Array.isArray(part)) return false;
    return _pr92Schema29NonEmptyString(part.asset_pointer) !== null;
  });
  const metadataAttachments = Array.isArray(message?.metadata?.attachments)
    ? message.metadata.attachments
    : [];

  const channels = [];
  if (pointerParts.length > 0) channels.push(pointerParts.length);
  if (metadataAttachments.length > 0) channels.push(metadataAttachments.length);
  return {
    pointerPartCount: pointerParts.length,
    metadataAttachmentCount: metadataAttachments.length,
    channels
  };
}

function _pr92Schema29MatchRequestPostData(
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) {
  const diagnostics = {
    postDataPresent: typeof postData === "string" && postData.length > 0,
    requestJsonParsed: false,
    actionNext: false,
    conversationIdentityMatches: false,
    userMessageCount: 0,
    exactTextUserMessageCount: 0,
    exactRichUserMessageCount: 0,
    requestMessageIdPresent: false,
    pointerPartCount: 0,
    metadataAttachmentCount: 0,
    attachmentEvidenceChannelCount: 0,
    attachmentCountsMatch: false
  };
  if (!diagnostics.postDataPresent) {
    return { matched: false, logicalMessageId: null, diagnostics };
  }

  let payload;
  try {
    payload = JSON.parse(postData);
  } catch {
    return { matched: false, logicalMessageId: null, diagnostics };
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return { matched: false, logicalMessageId: null, diagnostics };
  }
  diagnostics.requestJsonParsed = true;
  diagnostics.actionNext = payload.action === "next";
  if (!diagnostics.actionNext) {
    return { matched: false, logicalMessageId: null, diagnostics };
  }

  const requestConversationId = _pr92Schema29NonEmptyString(payload.conversation_id);
  diagnostics.conversationIdentityMatches = expectedConversationId === null
    ? requestConversationId === null
    : requestConversationId === expectedConversationId;
  if (!diagnostics.conversationIdentityMatches) {
    return { matched: false, logicalMessageId: null, diagnostics };
  }

  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const exactCandidates = [];
  for (const message of messages) {
    if (message === null || typeof message !== "object" || Array.isArray(message)) continue;
    if (message?.author?.role !== "user") continue;
    diagnostics.userMessageCount += 1;

    const parts = Array.isArray(message?.content?.parts) ? message.content.parts : [];
    const textParts = parts.filter((part) => typeof part === "string");
    if (textParts.join("") !== expectedText) continue;
    diagnostics.exactTextUserMessageCount += 1;

    const attachment = _pr92Schema29RequestMessageAttachmentChannels(message);
    const channels = attachment.channels;
    const attachmentCountsMatch = expectedAttachmentCount > 0
      ? channels.length > 0 && channels.every((count) => count === expectedAttachmentCount)
      : channels.every((count) => count === 0);
    if (!attachmentCountsMatch) continue;

    const messageId = _pr92Schema29NonEmptyString(message.id);
    if (!messageId) continue;
    exactCandidates.push({
      messageId,
      pointerPartCount: attachment.pointerPartCount,
      metadataAttachmentCount: attachment.metadataAttachmentCount,
      attachmentEvidenceChannelCount: channels.length
    });
  }

  diagnostics.exactRichUserMessageCount = exactCandidates.length;
  if (exactCandidates.length !== 1) {
    return { matched: false, logicalMessageId: null, diagnostics };
  }

  const candidate = exactCandidates[0];
  diagnostics.requestMessageIdPresent = true;
  diagnostics.pointerPartCount = candidate.pointerPartCount;
  diagnostics.metadataAttachmentCount = candidate.metadataAttachmentCount;
  diagnostics.attachmentEvidenceChannelCount = candidate.attachmentEvidenceChannelCount;
  diagnostics.attachmentCountsMatch = true;
  return {
    matched: true,
    logicalMessageId: candidate.messageId,
    diagnostics
  };
}

function _pr92Schema29RecordPostArmConversationRequest(context, params) {
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

  const requestId = _pr92Schema29NonEmptyString(params?.requestId);
  if (!requestId) return;
  const observed = Array.isArray(context.schema29PostArmConversationRequests)
    ? context.schema29PostArmConversationRequests
    : [];
  if (observed.some((entry) => entry.requestId === requestId)) return;

  const matched = _pr92Schema29MatchRequestPostData(
    request?.postData,
    context.schema29ExpectedText,
    context.schema29ExpectedAttachmentCount,
    context.schema19RequestedConversationId
  );
  observed.push({
    requestId,
    hasUserGesture: params?.hasUserGesture === true,
    matched: matched.matched === true,
    logicalMessageId: matched.logicalMessageId,
    diagnostics: matched.diagnostics
  });
  context.schema29PostArmConversationRequests = observed;
}

function _pr92Schema29EvaluateSubmitCorrelation(context) {
  const observed = Array.isArray(context?.schema29PostArmConversationRequests)
    ? context.schema29PostArmConversationRequests
    : [];
  const markerObserved = context?.schema20ProtectedSubmitMarkerObserved === true;
  const first = observed.length > 0 ? observed[0] : null;
  const matching = observed.filter((entry) => entry?.matched === true);
  const distinctLogicalMessageIds = new Set(
    matching
      .map((entry) => _pr92Schema29NonEmptyString(entry?.logicalMessageId))
      .filter(Boolean)
  );
  const firstMatched = first?.matched === true;
  const firstDiagnostics = first?.diagnostics || null;
  const userGestureRequestCount = observed.filter(
    (entry) => entry?.hasUserGesture === true
  ).length;
  const ok =
    markerObserved &&
    firstMatched &&
    distinctLogicalMessageIds.size === 1;

  return {
    ok,
    markerObserved,
    postArmConversationRequestCount: observed.length,
    matchingRequestCount: matching.length,
    distinctMatchingLogicalMessageCount: distinctLogicalMessageIds.size,
    firstRequestMatched: firstMatched,
    firstRequestPostDataPresent: firstDiagnostics?.postDataPresent === true,
    firstRequestJsonParsed: firstDiagnostics?.requestJsonParsed === true,
    firstRequestActionNext: firstDiagnostics?.actionNext === true,
    firstRequestConversationIdentityMatches:
      firstDiagnostics?.conversationIdentityMatches === true,
    firstRequestExactTextUserMessageCount:
      Number(firstDiagnostics?.exactTextUserMessageCount) || 0,
    firstRequestExactRichUserMessageCount:
      Number(firstDiagnostics?.exactRichUserMessageCount) || 0,
    firstRequestMessageIdPresent: firstDiagnostics?.requestMessageIdPresent === true,
    firstRequestPointerPartCount: Number(firstDiagnostics?.pointerPartCount) || 0,
    firstRequestMetadataAttachmentCount:
      Number(firstDiagnostics?.metadataAttachmentCount) || 0,
    firstRequestAttachmentEvidenceChannelCount:
      Number(firstDiagnostics?.attachmentEvidenceChannelCount) || 0,
    firstRequestAttachmentCountsMatch: firstDiagnostics?.attachmentCountsMatch === true,
    postArmUserGestureRequestCount: userGestureRequestCount,
    additionalPostArmRequestsAuthoritative: false,
    hasUserGestureAuthoritative: false
  };
}

extractSafeStreamMetadata = function _pr92Schema29ExtractSafeStreamMetadata(
  body,
  base64Encoded
) {
  // Preserve schema-28 and earlier response-hint observers. Their returned IDs
  // are deliberately ignored; schema-29 protocol-slot consensus is authoritative.
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
  context.schema29ExpectedText = typeof args?.text === "string" ? args.text : "";
  context.schema29ExpectedAttachmentCount = Array.isArray(context.attachmentPaths)
    ? context.attachmentPaths.length
    : 0;
  context.schema29PostArmConversationRequests = [];

  const observer = (source, method, params) => {
    if (source?.tabId !== tabId) return;
    if (method === "Runtime.consoleAPICalled") {
      _pr92Schema20ObserveArmMarker(context, params);
      return;
    }
    if (method === "Network.requestWillBeSent") {
      _pr92Schema29RecordPostArmConversationRequest(context, params);
    }
  };
  // Register before schema 17 installs its request listener. For each debugger
  // event this observer therefore records the same first armed conversation POST
  // that schema 17 subsequently selects as its exact request id.
  chrome.debugger.onEvent.addListener(observer);

  try {
    // Deliberately bypass only schema 20's historical post-return multiplicity /
    // hasUserGesture gate. `_pr92Schema20PriorExecuteOfficialPageTurn` is schema
    // 19 and retains schema 17 exact request tracking, completion proof, bounded
    // response-body read, and request-bound conversation identity. The global
    // schema-20 isConversationWrite predicate still blocks all pre-arm requests.
    const result = await _pr92Schema20PriorExecuteOfficialPageTurn(args);
    if (
      result?.diagnostics?.conversationRequestSeen !== true ||
      result?.diagnostics?.loadingFinished !== true
    ) {
      return result;
    }

    const correlation = _pr92Schema29EvaluateSubmitCorrelation(context);
    _pr92Schema29LastSubmitCorrelationDiagnostics = { ...correlation };
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
        protectedSubmitRequestBodyMatched: true,
        protectedSubmitLogicalMessageIdentityUnique: true,
        postArmConversationRequestCount: correlation.postArmConversationRequestCount,
        matchingPostArmConversationRequestCount: correlation.matchingRequestCount,
        additionalPostArmConversationRequestsAuthoritative: false,
        protectedSubmitRequestHadUserGesture: null,
        hasUserGestureAuthoritative: false,
        preArmConversationRequestsAuthoritative: false
      }
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (detail.startsWith(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR)) {
      _pr92Schema29LastSubmitCorrelationDiagnostics =
        _pr92Schema29EvaluateSubmitCorrelation(context);
    }
    throw error;
  } finally {
    chrome.debugger.onEvent.removeListener(observer);
    context.schema20ProtectedSubmitArmed = false;
    context.schema29ExpectedText = null;
    context.schema29ExpectedAttachmentCount = 0;
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
          `:matchingRequestCount=${Number(correlation.matchingRequestCount) || 0}` +
          `:distinctMatchingLogicalMessageCount=${Number(correlation.distinctMatchingLogicalMessageCount) || 0}` +
          `:firstRequestMatched=${correlation.firstRequestMatched === true}` +
          `:firstRequestPostDataPresent=${correlation.firstRequestPostDataPresent === true}` +
          `:firstRequestJsonParsed=${correlation.firstRequestJsonParsed === true}` +
          `:firstRequestActionNext=${correlation.firstRequestActionNext === true}` +
          `:firstRequestConversationIdentityMatches=${correlation.firstRequestConversationIdentityMatches === true}` +
          `:firstRequestExactTextUserMessageCount=${Number(correlation.firstRequestExactTextUserMessageCount) || 0}` +
          `:firstRequestExactRichUserMessageCount=${Number(correlation.firstRequestExactRichUserMessageCount) || 0}` +
          `:firstRequestMessageIdPresent=${correlation.firstRequestMessageIdPresent === true}` +
          `:firstRequestPointerPartCount=${Number(correlation.firstRequestPointerPartCount) || 0}` +
          `:firstRequestMetadataAttachmentCount=${Number(correlation.firstRequestMetadataAttachmentCount) || 0}` +
          `:firstRequestAttachmentEvidenceChannelCount=${Number(correlation.firstRequestAttachmentEvidenceChannelCount) || 0}` +
          `:firstRequestAttachmentCountsMatch=${correlation.firstRequestAttachmentCountsMatch === true}` +
          `:postArmUserGestureRequestCount=${Number(correlation.postArmUserGestureRequestCount) || 0}`
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
    protectedSubmitRequestCorrelation: PR92_SCHEMA29_REQUEST_CORRELATION,
    validatedClickRequestBodyCorrelation: true,
    requestPostDataRequiredForProtectedSubmitCorrelation: true,
    exactUserTextRequiredForProtectedSubmitCorrelation: true,
    requestMessageIdRequiredForProtectedSubmitCorrelation: true,
    requestAttachmentCountRequiredForProtectedSubmitCorrelation: true,
    continuationConversationIdRequiredForProtectedSubmitCorrelation: true,
    newChatConversationIdMustBeAbsentForProtectedSubmitCorrelation: true,
    additionalPostArmConversationRequestsAuthoritative: false,
    duplicateSameLogicalMessageRequestAllowed: true,
    distinctMatchingLogicalMessagesFailClosed: true,
    hasUserGestureAuthoritative: false,
    exactlyOnePostArmConversationRequestRequired: false,
    ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: false,
    submitCorrelationFailureDiagnosticsAvailable: true,
    automaticWriteRetryAfterSubmitCorrelationFailure: false,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
