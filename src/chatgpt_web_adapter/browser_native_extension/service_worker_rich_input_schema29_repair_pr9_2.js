// PR9.2 schema-29 request-body-bound rich-submit and protocol identity closure.
//
// Authenticated rich-input runs established that the product write succeeds even
// when current ChatGPT emits additional /conversation POSTs after the protected
// click and emits no `stream_handoff` record. Raw POST multiplicity and CDP's
// `hasUserGesture` bit are therefore not stable logical-turn identity primitives.
//
// Schema 29 keeps the reviewed schema-21 protected boundary: a unique page-side
// arm marker is emitted immediately before the validated `button.click()` in the
// same synchronous renderer task. Schema 17/19 still select and complete the FIRST
// conversation POST after that arm and read Network.getResponseBody for that exact
// requestId. Schema 29 replaces only schema 20's historical final
// "exactly-one-post + !hasUserGesture" gate with request-body identity.
//
// The first armed request must prove, from its own JSON body, exactly one intended
// user message: action=next, exact inserted text, non-empty client message id,
// expected attachment count in recognized request channels, and the correct
// conversation-id semantics (absent for new chat; exact for continuation).
//
// CDP may omit Request.postData even when hasPostData=true. When that happens,
// schema 29 immediately dispatches Network.getRequestPostData(requestId) while the
// same debugger session is still attached. The returned body is parsed directly
// into safe identity facts and is never retained. Correlation waits only within a
// short bounded post-write budget that preserves schema 19's RPC-return reserve.
// An unresolved request body fails closed rather than falling back to POST count,
// route state, or user-gesture heuristics.
//
// Additional armed service POSTs are allowed and non-authoritative. Additional
// requests carrying no new user-message identity cannot invalidate the selected
// write. A retry carrying the same client message id is the same logical turn and
// is allowed. Any distinct post-arm user message id fails closed, preventing a
// concurrent manual user turn from contaminating canonical assistant readback.
//
// Response identity is independently exact-request-bound: recognized top-level
// and root-add conversation-id slots in the selected request's response body must
// all agree. Route state remains diagnostic only and automatic write retry remains
// forbidden. Raw request text, postData, request ids, message ids, and conversation
// ids are never emitted in diagnostics.

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
const PR92_SCHEMA29_POSTDATA_SETTLE_CAP_MS = 1_000;

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
    return { conversationId: null, turnExchangeId: null, diagnostics };
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

  return { conversationId, turnExchangeId, diagnostics };
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

function _pr92Schema29InspectRequestPostData(
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
    userMessageIdCount: 0,
    userMessageIdentityClassified: false,
    exactTextUserMessageCount: 0,
    exactRichUserMessageCount: 0,
    requestMessageIdPresent: false,
    pointerPartCount: 0,
    metadataAttachmentCount: 0,
    attachmentEvidenceChannelCount: 0,
    attachmentCountsMatch: false
  };
  if (!diagnostics.postDataPresent) {
    return {
      matched: false,
      logicalMessageId: null,
      logicalUserMessageIds: [],
      diagnostics
    };
  }

  let payload;
  try {
    payload = JSON.parse(postData);
  } catch {
    return {
      matched: false,
      logicalMessageId: null,
      logicalUserMessageIds: [],
      diagnostics
    };
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return {
      matched: false,
      logicalMessageId: null,
      logicalUserMessageIds: [],
      diagnostics
    };
  }
  diagnostics.requestJsonParsed = true;
  diagnostics.actionNext = payload.action === "next";

  const requestConversationId = _pr92Schema29NonEmptyString(payload.conversation_id);
  diagnostics.conversationIdentityMatches = expectedConversationId === null
    ? requestConversationId === null
    : requestConversationId === expectedConversationId;

  const messagesFieldPresent = Object.prototype.hasOwnProperty.call(
    payload,
    "messages"
  );
  if (messagesFieldPresent && !Array.isArray(payload.messages)) {
    return {
      matched: false,
      logicalMessageId: null,
      logicalUserMessageIds: [],
      diagnostics
    };
  }

  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const exactCandidates = [];
  const logicalUserMessageIds = [];
  for (const message of messages) {
    if (message === null || typeof message !== "object" || Array.isArray(message)) continue;
    if (message?.author?.role !== "user") continue;
    diagnostics.userMessageCount += 1;

    const messageId = _pr92Schema29NonEmptyString(message.id);
    if (messageId) {
      diagnostics.userMessageIdCount += 1;
      logicalUserMessageIds.push(messageId);
    }

    if (
      !diagnostics.actionNext ||
      !diagnostics.conversationIdentityMatches
    ) {
      continue;
    }
    const parts = Array.isArray(message?.content?.parts) ? message.content.parts : [];
    const textParts = parts.filter((part) => typeof part === "string");
    if (textParts.join("") !== expectedText) continue;
    diagnostics.exactTextUserMessageCount += 1;

    const attachment = _pr92Schema29RequestMessageAttachmentChannels(message);
    const channels = attachment.channels;
    const attachmentCountsMatch = expectedAttachmentCount > 0
      ? channels.length > 0 && channels.every((count) => count === expectedAttachmentCount)
      : channels.every((count) => count === 0);
    if (!attachmentCountsMatch || !messageId) continue;

    exactCandidates.push({
      messageId,
      pointerPartCount: attachment.pointerPartCount,
      metadataAttachmentCount: attachment.metadataAttachmentCount,
      attachmentEvidenceChannelCount: channels.length
    });
  }

  diagnostics.userMessageIdentityClassified =
    diagnostics.userMessageCount === diagnostics.userMessageIdCount;

  diagnostics.exactRichUserMessageCount = exactCandidates.length;
  if (exactCandidates.length !== 1) {
    return {
      matched: false,
      logicalMessageId: null,
      logicalUserMessageIds,
      diagnostics
    };
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
    logicalUserMessageIds,
    diagnostics
  };
}

function _pr92Schema29ApplyRequestInspection(entry, inspected, source) {
  entry.matched = inspected?.matched === true;
  entry.logicalMessageId = inspected?.logicalMessageId || null;
  entry.logicalUserMessageIds = Array.isArray(inspected?.logicalUserMessageIds)
    ? inspected.logicalUserMessageIds.slice()
    : [];
  entry.diagnostics = inspected?.diagnostics || null;

  const explicitlyBodyless =
    source === "request-event-no-post-data";
  const identityClassified =
    inspected?.diagnostics?.requestJsonParsed === true &&
    inspected?.diagnostics?.userMessageIdentityClassified === true;

  entry.requestBodyResolved = explicitlyBodyless || identityClassified;
  entry.requestBodySource = entry.requestBodyResolved
    ? source
    : "unresolved";
}

function _pr92Schema29RecordPostArmConversationRequest(debuggee, context, params) {
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

  const entry = {
    requestId,
    hasUserGesture: params?.hasUserGesture === true,
    matched: false,
    logicalMessageId: null,
    logicalUserMessageIds: [],
    diagnostics: null,
    requestBodyResolved: false,
    requestBodySource: "unresolved",
    postDataLookupPromise: null
  };
  observed.push(entry);
  context.schema29PostArmConversationRequests = observed;

  const eventPostData = typeof request?.postData === "string" && request.postData.length > 0
    ? request.postData
    : null;
  if (eventPostData !== null) {
    _pr92Schema29ApplyRequestInspection(
      entry,
      _pr92Schema29InspectRequestPostData(
        eventPostData,
        context.schema29ExpectedText,
        context.schema29ExpectedAttachmentCount,
        context.schema19RequestedConversationId
      ),
      "request-event-post-data"
    );
    return;
  }

  if (request?.hasPostData === false) {
    _pr92Schema29ApplyRequestInspection(
      entry,
      _pr92Schema29InspectRequestPostData(
        null,
        context.schema29ExpectedText,
        context.schema29ExpectedAttachmentCount,
        context.schema19RequestedConversationId
      ),
      "request-event-no-post-data"
    );
    return;
  }

  // CDP explicitly permits Request.postData to be omitted when the body is too
  // long. Dispatch the exact-request fallback immediately, while schema 17's
  // debugger session is still attached. The promise stores only parsed facts.
  try {
    const pending = chrome.debugger.sendCommand(
      debuggee,
      "Network.getRequestPostData",
      { requestId }
    );
    entry.postDataLookupPromise = Promise.resolve(pending)
      .then((response) => {
        const decoded = _pr92Schema28DecodeResponseBody(
          response?.postData,
          response?.base64Encoded === true
        );
        if (typeof decoded !== "string" || !decoded) return false;
        _pr92Schema29ApplyRequestInspection(
          entry,
          _pr92Schema29InspectRequestPostData(
            decoded,
            context.schema29ExpectedText,
            context.schema29ExpectedAttachmentCount,
            context.schema19RequestedConversationId
          ),
          "network-get-request-post-data"
        );
        return true;
      })
      .catch(() => false);
  } catch {
    entry.postDataLookupPromise = Promise.resolve(false);
  }
}

async function _pr92Schema29AwaitPostDataLookups(context) {
  const observed = Array.isArray(context?.schema29PostArmConversationRequests)
    ? context.schema29PostArmConversationRequests
    : [];
  const pending = observed
    .map((entry) => entry?.postDataLookupPromise)
    .filter((value) => value && typeof value.then === "function");
  if (pending.length === 0) return;

  const remaining = _pr92RemainingTurnMsOrZero(context);
  const usable = remaining - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS;
  if (!Number.isFinite(usable) || usable <= 0) return;
  const localBudget = Math.max(
    1,
    Math.min(PR92_SCHEMA29_POSTDATA_SETTLE_CAP_MS, usable)
  );
  const localDeadlineAt = Math.min(
    context.deadlineAt - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS,
    performance.now() + localBudget
  );
  try {
    await _pr92Schema7RunUntil(
      localDeadlineAt,
      "SCHEMA29_REQUEST_POST_DATA_SETTLE",
      () => Promise.allSettled(pending)
    );
  } catch {
    // Any still-unresolved body remains fail-closed correlation evidence.
  }
}

function _pr92Schema29EvaluateSubmitCorrelation(context) {
  const observed = Array.isArray(context?.schema29PostArmConversationRequests)
    ? context.schema29PostArmConversationRequests
    : [];
  const markerObserved = context?.schema20ProtectedSubmitMarkerObserved === true;
  const first = observed.length > 0 ? observed[0] : null;
  const firstMatched = first?.matched === true;
  const firstLogicalMessageId = _pr92Schema29NonEmptyString(first?.logicalMessageId);
  const firstDiagnostics = first?.diagnostics || null;

  const matching = observed.filter((entry) => entry?.matched === true);
  const unresolvedRequestBodyCount = observed.filter(
    (entry) => entry?.requestBodyResolved !== true
  ).length;
  const fallbackRequestBodyCount = observed.filter(
    (entry) => entry?.requestBodySource === "network-get-request-post-data"
  ).length;
  const eventRequestBodyCount = observed.filter(
    (entry) => entry?.requestBodySource === "request-event-post-data"
  ).length;
  const postArmUserMessageIds = new Set();
  for (const entry of observed) {
    const ids = Array.isArray(entry?.logicalUserMessageIds)
      ? entry.logicalUserMessageIds
      : [];
    for (const value of ids) {
      const normalized = _pr92Schema29NonEmptyString(value);
      if (normalized) postArmUserMessageIds.add(normalized);
    }
  }
  const distinctPostArmUserMessageCount = postArmUserMessageIds.size;
  const foreignPostArmUserMessageCount = firstLogicalMessageId === null
    ? distinctPostArmUserMessageCount
    : Array.from(postArmUserMessageIds).filter(
        (value) => value !== firstLogicalMessageId
      ).length;
  const userGestureRequestCount = observed.filter(
    (entry) => entry?.hasUserGesture === true
  ).length;

  const ok =
    markerObserved &&
    firstMatched &&
    firstLogicalMessageId !== null &&
    unresolvedRequestBodyCount === 0 &&
    foreignPostArmUserMessageCount === 0;

  return {
    ok,
    markerObserved,
    postArmConversationRequestCount: observed.length,
    matchingRequestCount: matching.length,
    distinctPostArmUserMessageCount,
    foreignPostArmUserMessageCount,
    unresolvedRequestBodyCount,
    fallbackRequestBodyCount,
    eventRequestBodyCount,
    firstRequestMatched: firstMatched,
    firstRequestPostDataPresent: firstDiagnostics?.postDataPresent === true,
    firstRequestJsonParsed: firstDiagnostics?.requestJsonParsed === true,
    firstRequestActionNext: firstDiagnostics?.actionNext === true,
    firstRequestConversationIdentityMatches:
      firstDiagnostics?.conversationIdentityMatches === true,
    firstRequestUserMessageIdCount:
      Number(firstDiagnostics?.userMessageIdCount) || 0,
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
    additionalServicePostArmRequestsAllowed: true,
    distinctPostArmUserMessagesFailClosed: true,
    additionalPostArmRequestsAuthoritative: false,
    hasUserGestureAuthoritative: false
  };
}

extractSafeStreamMetadata = function _pr92Schema29ExtractSafeStreamMetadata(
  body,
  base64Encoded
) {
  try {
    _pr92Schema29PriorExtractSafeStreamMetadata(body, base64Encoded);
  } catch {
    // Observability must never perturb exact-request identity.
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
  const debuggee = { tabId };
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
      _pr92Schema29RecordPostArmConversationRequest(debuggee, context, params);
    }
  };
  chrome.debugger.onEvent.addListener(observer);

  try {
    // Bypass only schema 20's obsolete post-return multiplicity/user-gesture
    // decision. Schema 19 retains schema 17's selected requestId, completion,
    // response-body read, and causal conversation identity. The global schema-20
    // isConversationWrite predicate still denies all pre-arm request authority.
    const result = await _pr92Schema20PriorExecuteOfficialPageTurn(args);
    if (
      result?.diagnostics?.conversationRequestSeen !== true ||
      result?.diagnostics?.loadingFinished !== true
    ) {
      return result;
    }

    await _pr92Schema29AwaitPostDataLookups(context);
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
        additionalServicePostArmRequestsAllowed: true,
        distinctPostArmUserMessagesFailClosed: true,
        additionalPostArmConversationRequestsAuthoritative: false,
        protectedSubmitRequestHadUserGesture: null,
        hasUserGestureAuthoritative: false,
        preArmConversationRequestsAuthoritative: false
      }
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (
      detail.startsWith(PR92_SCHEMA29_COMMITTED_IDENTITY_ERROR) &&
      _pr92Schema29LastSubmitCorrelationDiagnostics === null
    ) {
      // Do not settle Network.getRequestPostData a second time. If the
      // authoritative correlation path already waited, reuse its diagnostics.
      // If an inherited committed-state error arrived before that point,
      // unresolved request bodies remain fail-closed immediately.
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
          `:distinctPostArmUserMessageCount=${Number(correlation.distinctPostArmUserMessageCount) || 0}` +
          `:foreignPostArmUserMessageCount=${Number(correlation.foreignPostArmUserMessageCount) || 0}` +
          `:unresolvedRequestBodyCount=${Number(correlation.unresolvedRequestBodyCount) || 0}` +
          `:fallbackRequestBodyCount=${Number(correlation.fallbackRequestBodyCount) || 0}` +
          `:firstRequestMatched=${correlation.firstRequestMatched === true}` +
          `:firstRequestPostDataPresent=${correlation.firstRequestPostDataPresent === true}` +
          `:firstRequestJsonParsed=${correlation.firstRequestJsonParsed === true}` +
          `:firstRequestActionNext=${correlation.firstRequestActionNext === true}` +
          `:firstRequestConversationIdentityMatches=${correlation.firstRequestConversationIdentityMatches === true}` +
          `:firstRequestUserMessageIdCount=${Number(correlation.firstRequestUserMessageIdCount) || 0}` +
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
    requestPostDataFallbackSupported: true,
    requestPostDataFallbackExactRequestBound: true,
    unresolvedRequestBodyFailsClosed: true,
    exactUserTextRequiredForProtectedSubmitCorrelation: true,
    requestMessageIdRequiredForProtectedSubmitCorrelation: true,
    requestAttachmentCountRequiredForProtectedSubmitCorrelation: true,
    continuationConversationIdRequiredForProtectedSubmitCorrelation: true,
    newChatConversationIdMustBeAbsentForProtectedSubmitCorrelation: true,
    additionalServicePostArmRequestsAllowed: true,
    additionalPostArmConversationRequestsAuthoritative: false,
    duplicateSameLogicalMessageRequestAllowed: true,
    distinctPostArmUserMessagesFailClosed: true,
    hasUserGestureAuthoritative: false,
    exactlyOnePostArmConversationRequestRequired: false,
    ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: false,
    submitCorrelationFailureDiagnosticsAvailable: true,
    automaticWriteRetryAfterSubmitCorrelationFailure: false,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
