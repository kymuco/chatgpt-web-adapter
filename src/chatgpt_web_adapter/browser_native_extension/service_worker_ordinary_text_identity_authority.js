// Request-bound ordinary-text conversation identity authority.
//
// Issue #79 proved that the browser SPA route can carry a namespaced display
// identity (for example WEB:<uuid>) that the canonical read plane rejects. The
// route is therefore never conversation-identity authority for an ordinary text
// write.
//
// This layer is deliberately last in the write-domain assembly. It grants
// ordinary-text conversation identity only when ALL of the following are true:
//
// 1. the protected submit commit boundary has actually been attempted;
// 2. the first post-commit conversation POST is bound by the already-reviewed
//    schema-29 request inspector to action=next, exact prompt text, one logical
//    user message id, zero attachments, and exact new/continuation semantics;
// 3. any asynchronous Network.getRequestPostData fallback has settled within a
//    bounded budget and no foreign post-commit user-message identity exists;
// 4. request-bound protocol conversation_id evidence has one verbatim consensus
//    from the exact matched request(s), using streamed SSE when available and a
//    response-body fallback only when the matched request completed without
//    usable streamed identity evidence.
//
// No route parsing, prefix stripping, UUID inference, retry, second submit, or
// canonical-read fallback is introduced here. Any post-commit identity ambiguity
// maps through the existing committed-write failure surface so callers cannot
// interpret it as retry authority.

const CWA_ORDINARY_IDENTITY_SCHEMA = 1;
const CWA_ORDINARY_IDENTITY_AUTHORITY =
  "REQUEST_BOUND_ORDINARY_TEXT_PROTOCOL_CONSENSUS";
const CWA_ORDINARY_IDENTITY_REQUEST_CORRELATION =
  "SCHEMA29_EXACT_REQUEST_BODY_IDENTITY";
const CWA_ORDINARY_IDENTITY_COMMITTED_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";
const CWA_ORDINARY_IDENTITY_POSTDATA_SETTLE_CAP_MS = 1_000;
const CWA_ORDINARY_IDENTITY_STREAM_SETTLE_CAP_MS = 750;
const CWA_ORDINARY_IDENTITY_RPC_RETURN_RESERVE_MS = 750;
const CWA_ORDINARY_IDENTITY_MAX_REQUESTS = 8;
const CWA_ORDINARY_IDENTITY_MAX_SSE_BUFFER_CHARS = 262_144;

const _cwaOrdinaryIdentityPriorExecuteNativeTurn = executeNativeTurn;
const _cwaOrdinaryIdentityPriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _cwaOrdinaryIdentityPriorSendCommand = sendCommand;

let _cwaOrdinaryIdentityActive = null;

function _cwaOrdinaryIdentityText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function _cwaOrdinaryIdentityEligible(message) {
  if (typeof message?.text !== "string" || !message.text.trim()) return false;
  if (Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0) {
    return false;
  }
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  if (mode !== "normal") return false;

  for (const flag of [
    "characterizeRichInputSupport",
    "characterizeSafeBrowserResponseStreamingSupport",
    "characterizeSafeBrowserResponseStreaming",
    "characterizePostAnswerTailTimingSupport",
    "characterizePostAnswerTailTiming",
    "characterizeEarlyProductCompletionSupport",
    "characterizeEarlyProductCompletion",
    "characterizeProductModelProfileSupport",
    "characterizeProductModelProfileSelectionRecord",
    "characterizeTemporaryTurn",
    "probeTemporaryMode",
    "probeTemporaryHistoryPresence",
    "probeTemporaryRouteReopen",
    "characterizeManualTemporaryGroundTruth",
    "characterizeGeneratedArtifactShapeSupport",
    "characterizeConnectorObservationSupport"
  ]) {
    if (message?.[flag] === true) return false;
  }
  return true;
}

function _cwaOrdinaryIdentityError(suffix, diagnostics = null) {
  let detail = `${CWA_ORDINARY_IDENTITY_COMMITTED_ERROR}:${suffix}`;
  if (diagnostics && typeof diagnostics === "object") {
    for (const [key, value] of Object.entries(diagnostics)) {
      if (typeof value === "boolean" || Number.isFinite(value)) {
        detail += `:${key}=${value}`;
      }
    }
  }
  const context = _cwaOrdinaryIdentityActive;
  if (context !== null) context.exactCommittedFailure = detail;
  return new Error(detail);
}

function _cwaOrdinaryIdentityCommitBoundary(method, params) {
  if (method === "Input.dispatchMouseEvent" && params?.type === "mouseReleased") {
    return "mouse_release";
  }
  if (
    method === "Input.dispatchKeyEvent" &&
    params?.type === "keyDown" &&
    (params?.key === "Enter" || params?.code === "Enter")
  ) {
    return "enter_keydown";
  }
  return null;
}

function _cwaOrdinaryIdentityCreateEntry(requestId) {
  return {
    requestId,
    matched: false,
    logicalMessageId: null,
    logicalUserMessageIds: [],
    requestBodyResolved: false,
    requestBodySource: "unresolved",
    postDataLookupPromise: null,
    responseReceived: false,
    responseStatus: null,
    loadingFinished: false,
    streamAttempted: false,
    streamSupported: null,
    streamReady: false,
    streamEnablePromise: null,
    pendingData: [],
    decoder: new TextDecoder("utf-8"),
    sseBuffer: "",
    sseBufferTruncated: false,
    protocolConflict: false,
    streamIdentityValues: new Set(),
    responseBodyObserved: false,
    responseBodyConflict: false,
    responseBodyIdentityValues: new Set()
  };
}

function _cwaOrdinaryIdentityApplyInspection(entry, inspected, source) {
  entry.matched = inspected?.matched === true;
  entry.logicalMessageId = _cwaOrdinaryIdentityText(inspected?.logicalMessageId);
  entry.logicalUserMessageIds = Array.isArray(inspected?.logicalUserMessageIds)
    ? inspected.logicalUserMessageIds
        .map((value) => _cwaOrdinaryIdentityText(value))
        .filter((value) => value !== null)
    : [];

  const explicitlyBodyless = source === "request-event-no-post-data";
  const identityClassified =
    inspected?.diagnostics?.requestJsonParsed === true &&
    inspected?.diagnostics?.userMessageIdentityClassified === true;
  entry.requestBodyResolved = explicitlyBodyless || identityClassified;
  entry.requestBodySource = entry.requestBodyResolved ? source : "unresolved";
}

function _cwaOrdinaryIdentityInspectPostData(context, entry, postData, source) {
  const inspected = _pr92Schema29InspectRequestPostData(
    postData,
    context.expectedText,
    0,
    context.expectedConversationId
  );
  _cwaOrdinaryIdentityApplyInspection(entry, inspected, source);
  if (entry.matched) _cwaOrdinaryIdentityMaybeEnableStream(context, entry);
}

function _cwaOrdinaryIdentityBase64Bytes(value) {
  if (typeof value !== "string" || !value) return new Uint8Array(0);
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function _cwaOrdinaryIdentityRecordProtocolBlock(entry, block) {
  const parsed = _pr92Schema29ExtractRequestBoundConversationMetadata(
    String(block || ""),
    false
  );
  if (parsed?.diagnostics?.conflictingConversationIds === true) {
    entry.protocolConflict = true;
  }
  const conversationId = _cwaOrdinaryIdentityText(parsed?.conversationId);
  if (conversationId !== null) entry.streamIdentityValues.add(conversationId);
}

function _cwaOrdinaryIdentityProcessBytes(entry, bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length === 0) return;
  const decoded = entry.decoder.decode(bytes, { stream: true });
  if (!decoded) return;
  entry.sseBuffer += decoded;
  if (entry.sseBuffer.length > CWA_ORDINARY_IDENTITY_MAX_SSE_BUFFER_CHARS) {
    entry.sseBuffer = entry.sseBuffer.slice(
      -CWA_ORDINARY_IDENTITY_MAX_SSE_BUFFER_CHARS
    );
    entry.sseBufferTruncated = true;
  }

  while (true) {
    const match = /\r?\n\r?\n/.exec(entry.sseBuffer);
    if (!match) break;
    const block = entry.sseBuffer.slice(0, match.index);
    entry.sseBuffer = entry.sseBuffer.slice(match.index + match[0].length);
    _cwaOrdinaryIdentityRecordProtocolBlock(entry, block);
  }
}

function _cwaOrdinaryIdentityEnqueueBase64(entry, base64Data) {
  if (typeof base64Data !== "string" || !base64Data) return;
  try {
    _cwaOrdinaryIdentityProcessBytes(
      entry,
      _cwaOrdinaryIdentityBase64Bytes(base64Data)
    );
  } catch {
    entry.protocolConflict = true;
  }
}

function _cwaOrdinaryIdentityFlush(entry) {
  try {
    const tail = entry.decoder.decode();
    if (tail) entry.sseBuffer += tail;
    if (entry.sseBuffer.trim()) {
      _cwaOrdinaryIdentityRecordProtocolBlock(entry, entry.sseBuffer);
    }
  } catch {
    entry.protocolConflict = true;
  }
  entry.sseBuffer = "";
}

function _cwaOrdinaryIdentityMaybeEnableStream(context, entry) {
  if (
    !entry.matched ||
    !entry.responseReceived ||
    entry.streamAttempted ||
    context.debuggee === null
  ) {
    return entry.streamEnablePromise;
  }

  entry.streamAttempted = true;
  try {
    const pending = chrome.debugger.sendCommand(
      context.debuggee,
      "Network.streamResourceContent",
      { requestId: entry.requestId }
    );
    entry.streamEnablePromise = Promise.resolve(pending)
      .then((response) => {
        entry.streamSupported = true;
        _cwaOrdinaryIdentityEnqueueBase64(entry, response?.bufferedData);
        entry.streamReady = true;
        const queued = entry.pendingData.splice(0);
        for (const value of queued) _cwaOrdinaryIdentityEnqueueBase64(entry, value);
        return true;
      })
      .catch(() => {
        entry.streamSupported = false;
        entry.streamReady = false;
        entry.pendingData.length = 0;
        return false;
      });
  } catch {
    entry.streamSupported = false;
    entry.streamReady = false;
    entry.streamEnablePromise = Promise.resolve(false);
  }
  return entry.streamEnablePromise;
}

function _cwaOrdinaryIdentityRecordRequest(context, source, params) {
  if (!context.submitArmed) return;
  const request = params?.request;
  if (!isConversationWrite(request?.url || "", request?.method || "")) return;
  const requestId = _cwaOrdinaryIdentityText(params?.requestId);
  if (requestId === null) return;
  if (context.entries.some((entry) => entry.requestId === requestId)) return;
  if (context.entries.length >= CWA_ORDINARY_IDENTITY_MAX_REQUESTS) {
    context.requestOverflow = true;
    return;
  }

  const entry = _cwaOrdinaryIdentityCreateEntry(requestId);
  context.entries.push(entry);

  const eventPostData = typeof request?.postData === "string" && request.postData.length > 0
    ? request.postData
    : null;
  if (eventPostData !== null) {
    _cwaOrdinaryIdentityInspectPostData(
      context,
      entry,
      eventPostData,
      "request-event-post-data"
    );
    return;
  }

  if (request?.hasPostData === false) {
    _cwaOrdinaryIdentityInspectPostData(
      context,
      entry,
      null,
      "request-event-no-post-data"
    );
    return;
  }

  try {
    const pending = chrome.debugger.sendCommand(
      source,
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
        _cwaOrdinaryIdentityInspectPostData(
          context,
          entry,
          decoded,
          "network-get-request-post-data"
        );
        return entry.requestBodyResolved;
      })
      .catch(() => false);
  } catch {
    entry.postDataLookupPromise = Promise.resolve(false);
  }
}

async function _cwaOrdinaryIdentityObserverFailureProbe(
  context,
  evidence
) {
  if (context.postDelegationObserverFailureProbe !== true) return null;

  const requestId = _cwaOrdinaryIdentityText(evidence?.requestId);
  const status = Number.isFinite(evidence?.responseStatus)
    ? Number(evidence.responseStatus)
    : null;
  if (
    requestId === null ||
    status === null ||
    status < 200 ||
    status >= 300
  ) {
    return null;
  }

  const entry = context.entries.find(
    (candidate) => candidate.requestId === requestId
  );
  if (!entry) return null;

  await _cwaOrdinaryIdentitySettlePostData(context);
  const correlation = _cwaOrdinaryIdentityEvaluateCorrelation(context);
  context.correlation = correlation;
  if (
    !correlation.ok ||
    !correlation.matchingEntries.some(
      (candidate) => candidate.requestId === requestId
    )
  ) {
    return null;
  }

  context.postDelegationObserverFailureProbeTriggered = true;
  context.postDelegationObserverFailureProbeRequestId = requestId;
  return new Error("CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED");
}

function _cwaOrdinaryIdentityObserve(context, source, method, params) {
  if (context.debuggee === null || source?.tabId !== context.debuggee.tabId) return;

  if (method === "Network.requestWillBeSent") {
    _cwaOrdinaryIdentityRecordRequest(context, source, params);
    return;
  }

  const requestId = _cwaOrdinaryIdentityText(params?.requestId);
  if (requestId === null) return;
  const entry = context.entries.find((candidate) => candidate.requestId === requestId);
  if (!entry) return;

  if (method === "Network.responseReceived") {
    entry.responseReceived = true;
    entry.responseStatus = Number.isFinite(params?.response?.status)
      ? Number(params.response.status)
      : null;
    _cwaOrdinaryIdentityMaybeEnableStream(context, entry);
    return;
  }

  if (method === "Network.dataReceived") {
    if (typeof params?.data !== "string" || !params.data) return;
    if (!entry.streamAttempted) return;
    if (entry.streamReady) _cwaOrdinaryIdentityEnqueueBase64(entry, params.data);
    else entry.pendingData.push(params.data);
    return;
  }

  if (method === "Network.loadingFinished") {
    entry.loadingFinished = true;
  }
}

function _cwaOrdinaryIdentityRemainingBudget(context, capMs) {
  const remaining = context.deadlineAt - performance.now();
  const usable = remaining - CWA_ORDINARY_IDENTITY_RPC_RETURN_RESERVE_MS;
  if (!Number.isFinite(usable) || usable <= 0) return 0;
  return Math.max(1, Math.min(capMs, usable));
}

async function _cwaOrdinaryIdentityAwaitBounded(promises, budgetMs) {
  const pending = promises.filter((value) => value && typeof value.then === "function");
  if (pending.length === 0 || budgetMs <= 0) return;
  let timer = null;
  try {
    await Promise.race([
      Promise.allSettled(pending),
      new Promise((resolve) => {
        timer = setTimeout(resolve, budgetMs);
      })
    ]);
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}

async function _cwaOrdinaryIdentitySettlePostData(context) {
  await _cwaOrdinaryIdentityAwaitBounded(
    context.entries.map((entry) => entry.postDataLookupPromise),
    _cwaOrdinaryIdentityRemainingBudget(
      context,
      CWA_ORDINARY_IDENTITY_POSTDATA_SETTLE_CAP_MS
    )
  );
}

function _cwaOrdinaryIdentityEvaluateCorrelation(context) {
  const entries = context.entries;
  const first = entries.length > 0 ? entries[0] : null;
  const firstMessageId = _cwaOrdinaryIdentityText(first?.logicalMessageId);
  const unresolvedCount = entries.filter(
    (entry) => entry.requestBodyResolved !== true
  ).length;
  const userMessageIds = new Set();
  for (const entry of entries) {
    for (const value of entry.logicalUserMessageIds) userMessageIds.add(value);
  }
  const foreignCount = firstMessageId === null
    ? userMessageIds.size
    : Array.from(userMessageIds).filter((value) => value !== firstMessageId).length;
  const matchingEntries = firstMessageId === null
    ? []
    : entries.filter(
        (entry) => entry.matched === true && entry.logicalMessageId === firstMessageId
      );

  return {
    ok:
      context.submitArmed === true &&
      context.requestOverflow !== true &&
      first?.matched === true &&
      firstMessageId !== null &&
      unresolvedCount === 0 &&
      foreignCount === 0 &&
      matchingEntries.length > 0,
    entryCount: entries.length,
    matchingEntryCount: matchingEntries.length,
    unresolvedCount,
    foreignCount,
    requestOverflow: context.requestOverflow === true,
    matchingEntries
  };
}

async function _cwaOrdinaryIdentityAnnotatePostDelegationFailure(
  context,
  error
) {
  const detail = error instanceof Error ? error.message : String(error);
  if (!detail.startsWith("CHATGPT_CONVERSATION_REQUEST_FAILED:")) return error;

  await _cwaOrdinaryIdentitySettlePostData(context);
  const correlation = _cwaOrdinaryIdentityEvaluateCorrelation(context);
  context.correlation = correlation;
  if (!correlation.ok) return error;

  const entry = correlation.matchingEntries[0];
  const userMessageId = _cwaOrdinaryIdentityText(entry?.logicalMessageId);
  const conversationId = _cwaOrdinaryIdentityText(context.expectedConversationId);
  if (userMessageId === null || conversationId === null) return error;

  const annotated = error instanceof Error ? error : new Error(detail);
  const runtimeTabId = Number.isInteger(context?.debuggee?.tabId)
    ? context.debuggee.tabId
    : null;
  if (runtimeTabId === null) return error;

  annotated.cwaPostDelegationRequestCorrelationProven = true;
  annotated.cwaPostDelegationUserMessageId = userMessageId;
  annotated.cwaPostDelegationConversationId = conversationId;
  annotated.cwaPostDelegationRuntimeTabId = runtimeTabId;
  annotated.cwaPostDelegationRecoveryContinuationObserved =
    context.canonicalCompletedRecoveryObserved === true;
  annotated.cwaPostDelegationObserverFailureProbeTriggered =
    context.postDelegationObserverFailureProbeTriggered === true;
  return annotated;
}

function _cwaOrdinaryIdentityConsensus(values, requestedConversationId) {
  const distinct = Array.from(new Set(values.filter((value) => value !== null)));
  if (distinct.length === 0) {
    return { state: "unresolved", conversationId: null, distinctCount: 0 };
  }
  if (distinct.length > 1) {
    return { state: "conflict", conversationId: null, distinctCount: distinct.length };
  }
  const candidate = distinct[0];
  if (requestedConversationId !== null && candidate !== requestedConversationId) {
    return { state: "request_mismatch", conversationId: null, distinctCount: 1 };
  }
  return { state: "consensus", conversationId: candidate, distinctCount: 1 };
}

async function _cwaOrdinaryIdentityReadResponseBody(context, entry) {
  if (context.debuggee === null || !entry.loadingFinished) return;
  entry.responseBodyObserved = true;
  try {
    const response = await chrome.debugger.sendCommand(
      context.debuggee,
      "Network.getResponseBody",
      { requestId: entry.requestId }
    );
    const parsed = _pr92Schema29ExtractRequestBoundConversationMetadata(
      response?.body,
      response?.base64Encoded === true
    );
    if (parsed?.diagnostics?.conflictingConversationIds === true) {
      entry.responseBodyConflict = true;
      return;
    }
    const conversationId = _cwaOrdinaryIdentityText(parsed?.conversationId);
    if (conversationId !== null) entry.responseBodyIdentityValues.add(conversationId);
  } catch {
    // Response-body fallback is only required if no streamed identity is usable.
  }
}

async function _cwaOrdinaryIdentityResolve(context, matchingEntries) {
  for (const entry of matchingEntries) {
    _cwaOrdinaryIdentityMaybeEnableStream(context, entry);
  }
  await _cwaOrdinaryIdentityAwaitBounded(
    matchingEntries.map((entry) => entry.streamEnablePromise),
    _cwaOrdinaryIdentityRemainingBudget(
      context,
      CWA_ORDINARY_IDENTITY_STREAM_SETTLE_CAP_MS
    )
  );

  for (const entry of matchingEntries) _cwaOrdinaryIdentityFlush(entry);

  if (matchingEntries.some((entry) => entry.sseBufferTruncated)) {
    throw _cwaOrdinaryIdentityError("SSE_CAPTURE_TRUNCATED");
  }
  if (matchingEntries.some((entry) => entry.protocolConflict)) {
    throw _cwaOrdinaryIdentityError("SSE_IDENTITY_CONFLICT");
  }

  let streamValues = matchingEntries.flatMap((entry) =>
    Array.from(entry.streamIdentityValues)
  );
  if (streamValues.length === 0) {
    for (const entry of matchingEntries) {
      await _cwaOrdinaryIdentityReadResponseBody(context, entry);
    }
  }

  if (matchingEntries.some((entry) => entry.responseBodyConflict)) {
    throw _cwaOrdinaryIdentityError("RESPONSE_IDENTITY_CONFLICT");
  }

  streamValues = matchingEntries.flatMap((entry) =>
    Array.from(entry.streamIdentityValues)
  );
  const bodyValues = matchingEntries.flatMap((entry) =>
    Array.from(entry.responseBodyIdentityValues)
  );
  const consensus = _cwaOrdinaryIdentityConsensus(
    [...streamValues, ...bodyValues],
    context.expectedConversationId
  );
  if (consensus.state === "unresolved") {
    throw _cwaOrdinaryIdentityError("SSE_IDENTITY_UNRESOLVED", {
      matchedRequests: matchingEntries.length,
      loadingFinished: matchingEntries.some((entry) => entry.loadingFinished)
    });
  }
  if (consensus.state === "conflict") {
    throw _cwaOrdinaryIdentityError("SSE_IDENTITY_CONFLICT", {
      distinctCount: consensus.distinctCount
    });
  }
  if (consensus.state === "request_mismatch") {
    throw _cwaOrdinaryIdentityError("SSE_REQUEST_IDENTITY_MISMATCH");
  }

  return {
    conversationId: consensus.conversationId,
    source:
      streamValues.length > 0 && bodyValues.length > 0
        ? "sse_and_response_body"
        : streamValues.length > 0
          ? "sse_stream"
          : "response_body",
    matchingRequestCount: matchingEntries.length
  };
}

sendCommand = function _cwaOrdinaryIdentitySendCommand(debuggee, method, params) {
  const context = _cwaOrdinaryIdentityActive;
  if (context !== null && context.officialActive === true) {
    const boundary = _cwaOrdinaryIdentityCommitBoundary(method, params);
    if (boundary !== null && context.submitArmed !== true) {
      context.submitArmed = true;
      context.commitBoundary = boundary;
    }
  }
  return _cwaOrdinaryIdentityPriorSendCommand(debuggee, method, params);
};

executeOfficialPageTurn = async function _cwaOrdinaryIdentityExecuteOfficialPageTurn(args) {
  const context = _cwaOrdinaryIdentityActive;
  if (context === null) return _cwaOrdinaryIdentityPriorExecuteOfficialPageTurn(args);

  const tabId = args?.tabId;
  context.debuggee = { tabId };
  context.officialActive = true;
  const observer = (source, method, params) => {
    try {
      _cwaOrdinaryIdentityObserve(context, source, method, params);
    } catch {
      context.observationErrorCount += 1;
    }
  };
  let listenerInstalled = false;
  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  try {
    let result;
    try {
      result = await _cwaOrdinaryIdentityPriorExecuteOfficialPageTurn({
        ...args,
        postDelegationObserverFailureProbe:
          context.postDelegationObserverFailureProbe === true
            ? (evidence) =>
                _cwaOrdinaryIdentityObserverFailureProbe(context, evidence)
            : null
      });
    } catch (error) {
      throw await _cwaOrdinaryIdentityAnnotatePostDelegationFailure(
        context,
        error
      );
    }
    await _cwaOrdinaryIdentitySettlePostData(context);
    const correlation = _cwaOrdinaryIdentityEvaluateCorrelation(context);
    context.correlation = correlation;
    if (!correlation.ok) {
      throw _cwaOrdinaryIdentityError("ORDINARY_REQUEST_CORRELATION_UNRESOLVED", {
        requestCount: correlation.entryCount,
        unresolvedCount: correlation.unresolvedCount,
        foreignCount: correlation.foreignCount,
        requestOverflow: correlation.requestOverflow
      });
    }

    const identity = await _cwaOrdinaryIdentityResolve(
      context,
      correlation.matchingEntries
    );
    context.authoritativeConversationId = identity.conversationId;
    context.identitySource = identity.source;
    context.matchingRequestCount = identity.matchingRequestCount;

    return {
      ...result,
      conversationId: identity.conversationId,
      ordinaryTextConversationIdentityAuthority: CWA_ORDINARY_IDENTITY_AUTHORITY,
      ordinaryTextRequestCorrelation: CWA_ORDINARY_IDENTITY_REQUEST_CORRELATION,
      ordinaryTextConversationIdentitySource: identity.source,
      ordinaryTextMatchingRequestCount: identity.matchingRequestCount,
      ordinaryTextCanonicalCompletedRecoveryObserved:
        context.canonicalCompletedRecoveryObserved === true,
      routeConversationIdentityAuthoritative: false
    };
  } finally {
    context.officialActive = false;
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Listener cleanup cannot change the already-observed write outcome.
      }
    }
  }
};

executeNativeTurn = async function _cwaOrdinaryIdentityExecuteNativeTurn(message) {
  if (!_cwaOrdinaryIdentityEligible(message)) {
    return _cwaOrdinaryIdentityPriorExecuteNativeTurn(message);
  }
  if (_cwaOrdinaryIdentityActive !== null) {
    throw new Error("CWA_ORDINARY_IDENTITY_CONTEXT_ALREADY_ACTIVE");
  }
  if (typeof _pr92Schema29InspectRequestPostData !== "function") {
    throw new Error("CWA_ORDINARY_IDENTITY_SCHEMA29_INSPECTOR_UNAVAILABLE");
  }
  if (typeof _pr92Schema29ExtractRequestBoundConversationMetadata !== "function") {
    throw new Error("CWA_ORDINARY_IDENTITY_SCHEMA29_PROTOCOL_PARSER_UNAVAILABLE");
  }

  const timeoutMs = Math.max(1_000, Number(message?.timeoutMs) || 150_000);
  const context = {
    expectedText: message.text,
    expectedConversationId: _cwaOrdinaryIdentityText(message?.conversationId),
    postDelegationObserverFailureProbe:
      message?.postDelegationObserverFailureProbe === true &&
      _cwaOrdinaryIdentityText(message?.conversationId) !== null,
    canonicalCompletedRecoveryObserved: message?.canonicalCompleted === true,
    postDelegationObserverFailureProbeTriggered: false,
    postDelegationObserverFailureProbeRequestId: null,
    deadlineAt: performance.now() + timeoutMs,
    debuggee: null,
    officialActive: false,
    submitArmed: false,
    commitBoundary: null,
    entries: [],
    requestOverflow: false,
    observationErrorCount: 0,
    correlation: null,
    authoritativeConversationId: null,
    identitySource: null,
    matchingRequestCount: 0,
    exactCommittedFailure: null
  };

  _cwaOrdinaryIdentityActive = context;
  try {
    const result = await _cwaOrdinaryIdentityPriorExecuteNativeTurn(message);
    if (context.authoritativeConversationId === null) {
      throw _cwaOrdinaryIdentityError("ORDINARY_IDENTITY_AUTHORITY_NOT_REACHED", {
        requestCount: context.entries.length,
        submitArmed: context.submitArmed
      });
    }
    return {
      ...result,
      conversationId: context.authoritativeConversationId,
      ordinaryTextConversationIdentityAuthority: CWA_ORDINARY_IDENTITY_AUTHORITY,
      ordinaryTextRequestCorrelation: CWA_ORDINARY_IDENTITY_REQUEST_CORRELATION,
      ordinaryTextConversationIdentitySource: context.identitySource,
      ordinaryTextMatchingRequestCount: context.matchingRequestCount,
      routeConversationIdentityAuthoritative: false
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const exact = context.exactCommittedFailure;
    if (
      typeof exact === "string" &&
      exact.startsWith(`${CWA_ORDINARY_IDENTITY_COMMITTED_ERROR}:`) &&
      detail.startsWith(CWA_ORDINARY_IDENTITY_COMMITTED_ERROR)
    ) {
      throw new Error(exact);
    }
    throw error;
  } finally {
    _cwaOrdinaryIdentityActive = null;
  }
};
