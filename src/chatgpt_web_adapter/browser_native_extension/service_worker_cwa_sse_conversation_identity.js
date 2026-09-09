// PR12.0 ordinary-text request-bound SSE conversation-identity authority.
//
// Live evidence (cwa_identity_capture_journal.json, _2, _3) proved the
// historical ordinary-text identity promotion was not request-bound:
//
// - the PR8.11.1 early-terminal boundary returns before
//   Network.loadingFinished and skips Network.getResponseBody +
//   extractSafeStreamMetadata entirely, so the only surviving identity source
//   was the /c/<id> SPA route URL;
// - that route URL is product-owned display state and has already carried a
//   namespaced route form (run-2), which the canonical read plane rejects with
//   HTTP 400 "Invalid conversation ...";
// - the request-bound SSE stream, by contrast, emitted one stable verbatim
//   conversation_id consensus (run-3: 7/7 records, first record) that the
//   canonical plane accepts and that binds to the client message id of the
//   protected write.
//
// This module therefore makes the request-bound SSE consensus the ONLY
// ordinary-text conversation-identity authority:
//
// - verbatim candidates are collected from the exact conversation-write POST's
//   own SSE stream (dataReceived frames already tapped by the production
//   streaming consumer) and from the exact response-body parse
//   (extractSafeStreamMetadata) on the non-streaming boundary;
// - 0 distinct candidates  -> fail closed PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED;
// - >1 distinct candidates -> fail closed ...:SSE_IDENTITY_CONFLICT;
// - continuation requests whose SSE consensus contradicts the requested
//   conversation id -> fail closed ...:SSE_REQUEST_IDENTITY_MISMATCH;
// - exactly 1 distinct candidate -> promoted verbatim onto the turn result.
//
// The route conversation id is never consulted here and never promoted. No
// prefix is stripped, no UUID is inferred, no transform is applied. The
// client message id from the protected request body is retained as the
// request-bound correlation key. This module adds no retry, no second submit,
// and no canonical-read behavior; failures map through the existing committed
// readback-incomplete surface and remain non-retryable.

const CWA_SSE_IDENTITY_SCHEMA = 1;
const CWA_SSE_IDENTITY_AUTHORITY =
  "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS";
const CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";
const CWA_SSE_IDENTITY_MAX_SSE_BUFFER_CHARS = 1_000_000;
const CWA_SSE_IDENTITY_MAX_RECORDS = 32;
const CWA_SSE_IDENTITY_MAX_REQUESTS = 4;
const CWA_SSE_IDENTITY_MAX_USER_MESSAGE_IDS = 4;

const _cwaSseIdentityPriorExecuteNativeTurn = executeNativeTurn;
const _cwaSseIdentityPriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const _cwaSseIdentityPriorSendCommand = sendCommand;

let _cwaSseIdentityActive = null;
let _cwaSseIdentityCaptureCounter = 0;
let _cwaSseIdentityPendingBodyRequestId = null;

// Load sentinel: proves this authority module was imported by the running
// service worker. Version/timestamp only — never credential or payload data.
const CWA_SSE_IDENTITY_SENTINEL_KEY = "cwaSseConversationIdentityLoadedV1";
try {
  chrome.storage.local
    .set({
      [CWA_SSE_IDENTITY_SENTINEL_KEY]: {
        schema: CWA_SSE_IDENTITY_SCHEMA,
        bundle: "worktree-cwa-main-test",
        loadedAtMs: Date.now()
      }
    })
    .catch(() => {});
} catch {}

function _cwaSseIdentityText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function _cwaSseIdentityStableReason(error) {
  const message = error instanceof Error ? error.message : String(error || "");
  const trimmed = message.trim().slice(0, 300);
  return /^PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED/.test(trimmed) ||
    /^[A-Z0-9_]+(:[A-Za-z0-9_=.,-]+)*$/.test(trimmed)
    ? trimmed
    : "CWA_SSE_IDENTITY_UNSAFE_ERROR_TEXT_OMITTED";
}

function _cwaSseIdentityIsOrdinaryWrite(message) {
  if (typeof message?.text !== "string" || !message.text.trim()) return false;
  if (Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0) {
    return false;
  }
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  if (mode !== "normal") return false;
  if (message?.characterizeRichInputSupport === true) return false;
  if (message?.characterizeSafeBrowserResponseStreamingSupport === true) return false;
  if (message?.characterizeSafeBrowserResponseStreaming === true) return false;
  if (message?.characterizePostAnswerTailTimingSupport === true) return false;
  if (message?.characterizePostAnswerTailTiming === true) return false;
  if (message?.characterizeEarlyProductCompletionSupport === true) return false;
  if (message?.characterizeEarlyProductCompletion === true) return false;
  if (message?.characterizeProductModelProfileSupport === true) return false;
  if (message?.characterizeProductModelProfileSelectionRecord === true) return false;
  if (message?.characterizeTemporaryTurn === true) return false;
  if (message?.probeTemporaryMode === true) return false;
  if (message?.probeTemporaryHistoryPresence === true) return false;
  if (message?.probeTemporaryRouteReopen === true) return false;
  if (message?.characterizeManualTemporaryGroundTruth === true) return false;
  return true;
}

// Verbatim conversation_id field slots only. Message ids are correlation
// material, not conversation identity, and are deliberately excluded here.
function _cwaSseIdentityConversationIdSlots(payload) {
  const slots = [];
  if (Object.prototype.hasOwnProperty.call(payload, "conversation_id")) {
    const value = _cwaSseIdentityText(payload.conversation_id);
    if (value !== null) slots.push({ fieldPath: "conversation_id", value });
  }
  const rootAddValue =
    payload.p === "" &&
    payload.o === "add" &&
    payload.v !== null &&
    typeof payload.v === "object" &&
    !Array.isArray(payload.v)
      ? payload.v
      : null;
  if (
    rootAddValue !== null &&
    Object.prototype.hasOwnProperty.call(rootAddValue, "conversation_id")
  ) {
    const value = _cwaSseIdentityText(rootAddValue.conversation_id);
    if (value !== null) {
      slots.push({ fieldPath: "p=''/o=add/v.conversation_id", value });
    }
  }
  return slots;
}

// Pure consensus over request-bound verbatim candidates. Deduplication is the
// caller's responsibility (a Set), so identical duplicate records (test E)
// collapse before this function is consulted.
function _cwaSseIdentityConsensus(distinctValues, requestedConversationId) {
  if (!Array.isArray(distinctValues) || distinctValues.length === 0) {
    return { state: "unresolved", conversationId: null, distinctCount: 0 };
  }
  if (distinctValues.length > 1) {
    return { state: "conflict", conversationId: null, distinctCount: distinctValues.length };
  }
  const candidate = distinctValues[0];
  if (
    requestedConversationId !== null &&
    requestedConversationId !== undefined &&
    requestedConversationId !== candidate
  ) {
    return { state: "request_mismatch", conversationId: null, distinctCount: 1 };
  }
  return { state: "consensus", conversationId: candidate, distinctCount: 1 };
}

function _cwaSseIdentityParseRequestBodyIdentity(postData, base64Encoded) {
  const unresolved = { resolved: false };
  let decoded = postData;
  if (base64Encoded === true) {
    try {
      decoded = _pr92Schema28DecodeResponseBody(postData, true);
    } catch {
      return unresolved;
    }
  }
  if (typeof decoded !== "string" || !decoded) return unresolved;
  let payload;
  try {
    payload = JSON.parse(decoded);
  } catch {
    return unresolved;
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return unresolved;
  }
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const userMessageIds = [];
  for (const message of messages) {
    if (message === null || typeof message !== "object" || Array.isArray(message)) {
      continue;
    }
    if (message?.author?.role !== "user") continue;
    const messageId = _cwaSseIdentityText(message.id);
    if (messageId !== null && userMessageIds.length < CWA_SSE_IDENTITY_MAX_USER_MESSAGE_IDS) {
      userMessageIds.push(messageId);
    }
  }
  return {
    resolved: true,
    action: payload.action === "next" ? "next" : _cwaSseIdentityText(payload.action),
    conversationId: _cwaSseIdentityText(payload.conversation_id),
    userMessageIds
  };
}

function _cwaSseIdentityRecordRecord(state, entry) {
  state.records = _cwaSseIdentityPushBounded(
    state.records,
    CWA_SSE_IDENTITY_MAX_RECORDS,
    entry
  );
}

function _cwaSseIdentityPushBounded(list, limit, value) {
  const target = Array.isArray(list) ? list : [];
  target.push(value);
  while (target.length > limit) target.shift();
  return target;
}

// Records verbatim conversation_id slots from one complete SSE block. Raw SSE
// text is never retained; only slot paths, values, order and timestamps.
function _cwaSseIdentityRecordSseBlock(state, requestId, block) {
  const lines = String(block || "").split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return;
  state.sseRecordCount += 1;

  const data = dataLines.join("\n").trim();
  if (!data || data === "[DONE]") return;
  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return;
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return;
  }
  state.sseJsonRecordCount += 1;

  const slots = _cwaSseIdentityConversationIdSlots(payload);
  if (slots.length === 0) return;
  for (const slot of slots) {
    state.distinctValues.add(slot.value);
  }
  _cwaSseIdentityRecordRecord(state, {
    requestId,
    orderIndex: state.sseRecordCount,
    observedAtMs: Date.now(),
    eventType: _cwaSseIdentityText(payload.type),
    identityFields: slots
  });
}

function _cwaSseIdentityProcessSseChunk(state, base64Data) {
  if (typeof base64Data !== "string" || !base64Data) return;
  try {
    if (state.sseDecoder === null) state.sseDecoder = new TextDecoder("utf-8");
    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    state.sseBuffer += state.sseDecoder.decode(bytes, { stream: true });
    if (state.sseBuffer.length > CWA_SSE_IDENTITY_MAX_SSE_BUFFER_CHARS) {
      // The conversation_id consensus appears in the early stream; this guard
      // is memory protection only and drops the oldest bytes.
      state.sseBuffer = state.sseBuffer.slice(-CWA_SSE_IDENTITY_MAX_SSE_BUFFER_CHARS);
      state.sseBufferTruncated = true;
    }
    let match;
    while ((match = /\r?\n\r?\n/.exec(state.sseBuffer)) !== null) {
      const block = state.sseBuffer.slice(0, match.index);
      state.sseBuffer = state.sseBuffer.slice(match.index + match[0].length);
      _cwaSseIdentityRecordSseBlock(state, state.conversationRequestId, block);
    }
  } catch {
    state.sseDecodeErrorCount += 1;
  }
}

function _cwaSseIdentityFlushSseBuffer(state) {
  try {
    if (state.sseDecoder !== null) {
      const tail = state.sseDecoder.decode();
      if (tail) state.sseBuffer += tail;
    }
    let match;
    while ((match = /\r?\n\r?\n/.exec(state.sseBuffer)) !== null) {
      const block = state.sseBuffer.slice(0, match.index);
      state.sseBuffer = state.sseBuffer.slice(match.index + match[0].length);
      _cwaSseIdentityRecordSseBlock(state, state.conversationRequestId, block);
    }
    if (state.sseBuffer.trim()) {
      _cwaSseIdentityRecordSseBlock(state, state.conversationRequestId, state.sseBuffer);
    }
    state.sseBuffer = "";
  } catch {
    // The flush is best-effort and must never perturb the write path.
  }
}

sendCommand = function _cwaSseIdentitySendCommand(
  debuggee,
  method,
  params
) {
  if (
    _cwaSseIdentityActive !== null &&
    method === "Network.getResponseBody" &&
    typeof params?.requestId === "string" &&
    params.requestId
  ) {
    _cwaSseIdentityPendingBodyRequestId = params.requestId;
  }
  return _cwaSseIdentityPriorSendCommand(debuggee, method, params);
};

// Non-streaming boundary channel: the exact response body of the selected
// conversation request is parsed by the inherited schema-29 request-bound
// parser. Its consensus output is recorded verbatim as one more request-bound
// candidate source; its conflict flag is honored as a hard conflict.
extractSafeStreamMetadata = function _cwaSseIdentityCaptureExtract(
  body,
  base64Encoded
) {
  const parsed = _cwaSseIdentityPriorExtractSafeStreamMetadata(body, base64Encoded);
  try {
    const state = _cwaSseIdentityActive;
    if (state !== null) {
      const diagnostics =
        typeof _pr92Schema29LastIdentityParseDiagnostics === "object" &&
        _pr92Schema29LastIdentityParseDiagnostics !== null
          ? _pr92Schema29LastIdentityParseDiagnostics
          : null;
      const conversationId = parsed?.conversationId ?? null;
      if (conversationId !== null) state.distinctValues.add(conversationId);
      state.extractConflict =
        state.extractConflict || diagnostics?.conflictingConversationIds === true;
      _cwaSseIdentityRecordRecord(state, {
        requestId: _cwaSseIdentityPendingBodyRequestId,
        observedAtMs: Date.now(),
        source: "response_body_parse",
        conversationId,
        conflictingConversationIds: diagnostics?.conflictingConversationIds === true
      });
    }
  } catch {
    // Identity capture must never perturb the inherited parser.
  }
  _cwaSseIdentityPendingBodyRequestId = null;
  return parsed;
};

executeNativeTurn = async function _cwaSseIdentityExecuteNativeTurn(message) {
  if (!_cwaSseIdentityIsOrdinaryWrite(message)) {
    return _cwaSseIdentityPriorExecuteNativeTurn(message);
  }
  if (_cwaSseIdentityActive !== null) {
    throw new Error("CWA_SSE_IDENTITY_CONTEXT_ALREADY_ACTIVE");
  }

  const state = {
    captureId: ++_cwaSseIdentityCaptureCounter,
    requestedConversationId:
      typeof message?.conversationId === "string" && message.conversationId.trim()
        ? message.conversationId.trim()
        : null,
    conversationRequestId: null,
    clientMessageId: null,
    requestBodyResolved: false,
    sseDecoder: null,
    sseBuffer: "",
    sseBufferTruncated: false,
    sseRecordCount: 0,
    sseJsonRecordCount: 0,
    sseDecodeErrorCount: 0,
    extractConflict: false,
    records: [],
    distinctValues: new Set()
  };

  const observer = (source, method, params) => {
    if (_cwaSseIdentityActive !== state) return;
    try {
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (!isConversationWrite(request?.url || "", request?.method || "")) return;
        const requestId = _cwaSseIdentityText(params?.requestId);
        if (requestId === null) return;
        const existing = state.records.some(
          (record) => record.requestId === requestId
        );
        if (existing || state.conversationRequestId !== null) return;
        state.conversationRequestId = requestId;

        try {
          const pending = sendCommand(source, "Network.getRequestPostData", {
            requestId
          });
          Promise.resolve(pending)
            .then((response) => {
              const identity = _cwaSseIdentityParseRequestBodyIdentity(
                response?.postData,
                response?.base64Encoded === true
              );
              state.requestBodyResolved = identity.resolved === true;
              state.clientMessageId = identity.resolved
                ? identity.userMessageIds[0] ?? null
                : null;
            })
            .catch(() => {
              state.requestBodyResolved = false;
            });
        } catch {
          state.requestBodyResolved = false;
        }
        return;
      }
      if (method === "Network.dataReceived") {
        if (state.conversationRequestId === null) return;
        if (params?.requestId !== state.conversationRequestId) return;
        _cwaSseIdentityProcessSseChunk(state, params?.data);
      }
    } catch {
      // Observation must never throw into the write path.
    }
  };

  chrome.debugger.onEvent.addListener(observer);
  _cwaSseIdentityActive = state;
  let flushed = false;
  try {
    const result = await _cwaSseIdentityPriorExecuteNativeTurn(message);
    _cwaSseIdentityFlushSseBuffer(state);
    flushed = true;

    const consensus = _cwaSseIdentityConsensus(
      Array.from(state.distinctValues),
      state.requestedConversationId
    );
    if (consensus.state === "unresolved") {
      throw new Error(
        `${CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR}` +
          `:SSE_IDENTITY_UNRESOLVED` +
          `:sseRecordCount=${state.sseRecordCount}` +
          `:sseJsonRecordCount=${state.sseJsonRecordCount}` +
          `:requestBodyResolved=${state.requestBodyResolved === true}` +
          `:clientMessageIdBound=${state.clientMessageId !== null}` +
          `:authority=${CWA_SSE_IDENTITY_AUTHORITY}`
      );
    }
    if (
      consensus.state === "conflict" ||
      consensus.state === "request_mismatch"
    ) {
      throw new Error(
        `${CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR}` +
          (consensus.state === "conflict"
            ? `:SSE_IDENTITY_CONFLICT`
            : `:SSE_REQUEST_IDENTITY_MISMATCH`) +
          `:distinctCount=${consensus.distinctCount}` +
          `:requestBodyResolved=${state.requestBodyResolved === true}` +
          `:authority=${CWA_SSE_IDENTITY_AUTHORITY}`
      );
    }

    return {
      ...result,
      conversationId: consensus.conversationId,
      sseConversationIdentityAuthority: CWA_SSE_IDENTITY_AUTHORITY,
      sseConversationIdentityRecordCount: state.records.length,
      sseConversationIdentityDistinctCount: consensus.distinctCount,
      routeConversationIdentityAuthoritative: false
    };
  } catch (error) {
    if (!flushed) _cwaSseIdentityFlushSseBuffer(state);
    if (
      error instanceof Error &&
      error.message.startsWith(CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR)
    ) {
      throw error;
    }
    if (error instanceof Error && error.message === "CWA_SSE_IDENTITY_CONTEXT_ALREADY_ACTIVE") {
      throw error;
    }
    // Preserve the turn's own failure unchanged; the identity authority must
    // never rewrite or mask a failed write outcome.
    throw error;
  } finally {
    if (!flushed) _cwaSseIdentityFlushSseBuffer(state);
    if (_cwaSseIdentityActive === state) _cwaSseIdentityActive = null;
    _cwaSseIdentityPendingBodyRequestId = null;
    chrome.debugger.onEvent.removeListener(observer);
  }
};
