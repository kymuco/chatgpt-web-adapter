// PR12.0 CWA identity-capture diagnostics.
//
// Observation-only instrumentation for the `WEB:*` promoted-conversation-id
// investigation. This module never alters write semantics: it does not gate,
// retry, re-submit, strip namespace prefixes, infer UUIDs, or promote any
// identity. It wraps the fully-assembled write chain (installed last in the
// write domain) and records, per turn:
//
// - exact CDP requestId of every conversation-write POST observed during the
//   turn window, with HTTP status/mime and loading state;
// - sanitized request-body identity facts (action, verbatim conversation_id
//   slot, client message ids, text-part LENGTHS only) — the raw request body
//   is never retained;
// - every extractSafeStreamMetadata() identity parse on the exact request-bound
//   response body (verbatim conversation_id / turn_exchange_id values plus the
//   schema-29 parse diagnostics counters) — the raw response body is never
//   retained;
// - the schema-20 protected-submit arm marker observation and the final route
//   conversation id, tagged diagnostic-only.
//
// All captured values are identity/correlation evidence only. No cookies,
// tokens, auth headers, SSE payloads, or free text ever enter the record.
// The record rides the turn result as `cwaIdentityCaptureDiag` (the provider
// ignores unknown result fields) and is mirrored to chrome.storage.local so a
// failed turn still leaves durable evidence. Automatic write retry remains
// forbidden everywhere; this module performs zero network requests of its own
// beyond read-only CDP `Network.getRequestPostData` on already-observed
// requests while the write path's own debugger session is attached.

const CWA_IDCAP_CAPTURE_SCHEMA = 1;
const CWA_IDCAP_STORAGE_KEY_LAST = "cwaIdentityCaptureDiagLast";
const CWA_IDCAP_STORAGE_KEY_HISTORY = "cwaIdentityCaptureDiagHistory";
const CWA_IDCAP_HISTORY_LIMIT = 5;
const CWA_IDCAP_MAX_REQUESTS = 8;
const CWA_IDCAP_MAX_IDENTITY_PARSES = 8;
const CWA_IDCAP_MAX_USER_MESSAGE_IDS = 4;
const CWA_IDCAP_MAX_SSE_IDENTITY_EVENTS = 24;
const CWA_IDCAP_SSE_BUFFER_LIMIT = 1_000_000;
const CWA_IDCAP_MAX_IDENTITY_FIELDS = 8;

const _cwaIdcapPriorExecuteNativeTurn = executeNativeTurn;
const _cwaIdcapPriorExtractSafeStreamMetadata = extractSafeStreamMetadata;

// Load sentinel: proves this exact overlay file was imported by the running
// service worker. Version/timestamp only — never credential or payload data.
const CWA_IDCAP_SENTINEL_KEY = "cwaIdentityCaptureDiagLoadedV1";
try {
  chrome.storage.local
    .set({
      [CWA_IDCAP_SENTINEL_KEY]: {
        schema: CWA_IDCAP_CAPTURE_SCHEMA,
        bundle: "worktree-cwa-main-test",
        loadedAtMs: Date.now()
      }
    })
    .catch(() => {});
} catch {}

// Streaming-path sentinel (v2): SSE identity capture via Network.dataReceived
// on the exact request-bound conversation POST — parallel, read-only, no
// dependency on observation-domain load order.
const CWA_IDCAP_SENTINEL_V2_KEY = "cwaIdentityCaptureDiagLoadedV2";
try {
  chrome.storage.local
    .set({
      [CWA_IDCAP_SENTINEL_V2_KEY]: {
        schema: CWA_IDCAP_CAPTURE_SCHEMA,
        streamCapture: "network-dataReceived-request-bound",
        loadedAtMs: Date.now()
      }
    })
    .catch(() => {});
} catch {}

let _cwaIdcapActiveCapture = null;
let _cwaIdcapCaptureCounter = 0;
let _cwaIdcapPendingResponseBodyRequestId = null;

function _cwaIdcapStableReason(error) {
  const message = error instanceof Error ? error.message : String(error || "");
  const trimmed = message.trim().slice(0, 300);
  return /^PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED/.test(trimmed) ||
    /^[A-Z0-9_]+(:[A-Za-z0-9_=.,-]+)*$/.test(trimmed)
    ? trimmed
    : "CWA_IDCAP_UNSAFE_ERROR_TEXT_OMITTED";
}

function _cwaIdcapSanitizeUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return null;
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return null;
  }
}

function _cwaIdcapIsConversationWrite(url, method) {
  if (method !== "POST") return false;
  const sanitized = _cwaIdcapSanitizeUrl(url);
  if (sanitized === null) return false;
  const path = sanitized.replace(/^https:\/\/chatgpt\.com/, "").replace(/\/+$/, "");
  return path.endsWith("/backend-api/f/conversation") ||
    path.endsWith("/backend-api/conversation");
}

function _cwaIdcapNonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function _cwaIdcapParseRequestBodyIdentity(postData, base64Encoded) {
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
  const textPartLengths = [];
  let pointerPartCount = 0;
  for (const message of messages) {
    if (message === null || typeof message !== "object" || Array.isArray(message)) {
      continue;
    }
    if (message?.author?.role !== "user") continue;
    const messageId = _cwaIdcapNonEmptyString(message.id);
    if (messageId !== null && userMessageIds.length < CWA_IDCAP_MAX_USER_MESSAGE_IDS) {
      userMessageIds.push(messageId);
    }
    const parts = Array.isArray(message?.content?.parts) ? message.content.parts : [];
    for (const part of parts) {
      if (typeof part === "string") {
        textPartLengths.push(part.length);
      } else if (
        part !== null &&
        typeof part === "object" &&
        _cwaIdcapNonEmptyString(part.asset_pointer) !== null
      ) {
        pointerPartCount += 1;
      }
    }
  }

  return {
    resolved: true,
    action: payload.action === "next" ? "next" : _cwaIdcapNonEmptyString(payload.action),
    conversationId: _cwaIdcapNonEmptyString(payload.conversation_id),
    userMessageCount: messages.filter(
      (message) => message?.author?.role === "user"
    ).length,
    userMessageIds,
    textPartLengths,
    pointerPartCount
  };
}

function _cwaIdcapPushBounded(list, limit, value) {
  const target = Array.isArray(list) ? list : [];
  target.push(value);
  while (target.length > limit) target.shift();
  return target;
}

function _cwaIdcapBase64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

// Extracts verbatim identity field slots from one complete SSE block. Only
// field paths/values are recorded — raw SSE text, headers, and auth material
// never enter the capture.
function _cwaIdcapSseIdentityFields(payload) {
  const fields = [];
  const pushField = (path, value) => {
    const normalized = _cwaIdcapNonEmptyString(value);
    if (normalized !== null && fields.length < CWA_IDCAP_MAX_IDENTITY_FIELDS) {
      fields.push({ path, value: normalized });
    }
  };
  if (Object.prototype.hasOwnProperty.call(payload, "conversation_id")) {
    pushField("conversation_id", payload.conversation_id);
  }
  if (Object.prototype.hasOwnProperty.call(payload, "turn_exchange_id")) {
    pushField("turn_exchange_id", payload.turn_exchange_id);
  }
  if (Object.prototype.hasOwnProperty.call(payload, "message_id")) {
    pushField("message_id", payload.message_id);
  }
  const rootAddValue =
    payload.p === "" &&
    payload.o === "add" &&
    payload.v !== null &&
    typeof payload.v === "object" &&
    !Array.isArray(payload.v)
      ? payload.v
      : null;
  if (rootAddValue !== null) {
    if (Object.prototype.hasOwnProperty.call(rootAddValue, "conversation_id")) {
      pushField("p=''/o=add/v.conversation_id", rootAddValue.conversation_id);
    }
    if (Object.prototype.hasOwnProperty.call(rootAddValue, "id")) {
      pushField("p=''/o=add/v.id", rootAddValue.id);
    }
    const nestedMessage =
      rootAddValue.message !== null && typeof rootAddValue.message === "object"
        ? rootAddValue.message
        : null;
    if (nestedMessage !== null) {
      const role = _cwaIdcapNonEmptyString(nestedMessage.author?.role) || "unknown";
      if (Object.prototype.hasOwnProperty.call(nestedMessage, "id")) {
        pushField(`p=''/o=add/v.message.id[${role}]`, nestedMessage.id);
      }
    }
  }
  const message =
    payload.message !== null && typeof payload.message === "object"
      ? payload.message
      : null;
  if (message !== null) {
    const role = _cwaIdcapNonEmptyString(message.author?.role) || "unknown";
    if (Object.prototype.hasOwnProperty.call(message, "id")) {
      pushField(`message.id[${role}]`, message.id);
    }
  }
  return fields;
}

function _cwaIdcapRecordSseBlock(capture, entry, block) {
  const lines = String(block || "").split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return;
  capture.sseEventCount = (capture.sseEventCount || 0) + 1;

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
  capture.sseJsonEventCount = (capture.sseJsonEventCount || 0) + 1;

  const fields = _cwaIdcapSseIdentityFields(payload);
  if (fields.length === 0) return;
  capture.sseIdentityEvents = _cwaIdcapPushBounded(
    capture.sseIdentityEvents || [],
    CWA_IDCAP_MAX_SSE_IDENTITY_EVENTS,
    {
      orderIndex: capture.sseEventCount,
      requestId: entry.requestId,
      observedAtMs: Date.now(),
      eventType: _cwaIdcapNonEmptyString(payload.type),
      identityFields: fields
    }
  );
}

function _cwaIdcapProcessSseChunk(capture, entry, base64Data) {
  if (typeof base64Data !== "string" || !base64Data) return;
  try {
    if (!entry.sseDecoder) entry.sseDecoder = new TextDecoder("utf-8");
    entry.sseFirstDataAtMs = entry.sseFirstDataAtMs || Date.now();
    entry.sseLastDataAtMs = Date.now();
    entry.sseChunkCount = (entry.sseChunkCount || 0) + 1;
    entry.sseBuffer = (entry.sseBuffer || "") + entry.sseDecoder.decode(
      _cwaIdcapBase64ToBytes(base64Data),
      { stream: true }
    );
    if (entry.sseBuffer.length > CWA_IDCAP_SSE_BUFFER_LIMIT) {
      // Identity records appear in the early stream; guard memory only.
      entry.sseBuffer = entry.sseBuffer.slice(0, CWA_IDCAP_SSE_BUFFER_LIMIT);
      entry.sseBufferTruncated = true;
    }
    let match;
    while ((match = /\r?\n\r?\n/.exec(entry.sseBuffer)) !== null) {
      const block = entry.sseBuffer.slice(0, match.index);
      entry.sseBuffer = entry.sseBuffer.slice(match.index + match[0].length);
      _cwaIdcapRecordSseBlock(capture, entry, block);
    }
  } catch {
    entry.sseDecodeErrorCount = (entry.sseDecodeErrorCount || 0) + 1;
  }
}

function _cwaIdcapFlushSseEntry(capture, entry) {
  try {
    if (!entry.sseDecoder) return;
    const tail = entry.sseDecoder.decode();
    if (tail) entry.sseBuffer += tail;
    let match;
    while ((match = /\r?\n\r?\n/.exec(entry.sseBuffer)) !== null) {
      const block = entry.sseBuffer.slice(0, match.index);
      entry.sseBuffer = entry.sseBuffer.slice(match.index + match[0].length);
      _cwaIdcapRecordSseBlock(capture, entry, block);
    }
    if (entry.sseBuffer.trim()) {
      _cwaIdcapRecordSseBlock(capture, entry, entry.sseBuffer);
    }
    entry.sseBuffer = "";
  } catch {
    // Flush is best-effort; never perturb the write path.
  }
}

function _cwaIdcapPersist(capture) {
  try {
    chrome.storage.local.get(CWA_IDCAP_STORAGE_KEY_HISTORY, (existing) => {
      try {
        const history = Array.isArray(existing?.[CWA_IDCAP_STORAGE_KEY_HISTORY])
          ? existing[CWA_IDCAP_STORAGE_KEY_HISTORY]
          : [];
        const next = [...history, capture].slice(-CWA_IDCAP_HISTORY_LIMIT);
        chrome.storage.local.set({
          [CWA_IDCAP_STORAGE_KEY_LAST]: capture,
          [CWA_IDCAP_STORAGE_KEY_HISTORY]: next
        }).catch(() => {});
      } catch {}
    });
  } catch {}
}

const _cwaIdcapPriorSendCommand = sendCommand;

sendCommand = function _cwaIdcapSendCommand(debuggee, method, params) {
  if (
    _cwaIdcapActiveCapture !== null &&
    method === "Network.getResponseBody" &&
    typeof params?.requestId === "string" &&
    params.requestId
  ) {
    // The next safe-metadata parse belongs to this exact request-bound body.
    _cwaIdcapPendingResponseBodyRequestId = params.requestId;
  }
  return _cwaIdcapPriorSendCommand(debuggee, method, params);
};

extractSafeStreamMetadata = function _cwaIdcapCaptureSafeStreamMetadata(
  body,
  base64Encoded
) {
  const parsed = _cwaIdcapPriorExtractSafeStreamMetadata(body, base64Encoded);
  try {
    if (_cwaIdcapActiveCapture !== null) {
      const schema29Diagnostics =
        typeof _pr92Schema29LastIdentityParseDiagnostics === "object" &&
        _pr92Schema29LastIdentityParseDiagnostics !== null
          ? { ..._pr92Schema29LastIdentityParseDiagnostics }
          : null;
      _cwaIdcapActiveCapture.identityParses = _cwaIdcapPushBounded(
        _cwaIdcapActiveCapture.identityParses,
        CWA_IDCAP_MAX_IDENTITY_PARSES,
        {
          associatedRequestId: _cwaIdcapPendingResponseBodyRequestId,
          observedAtMs: Date.now(),
          conversationId: parsed?.conversationId ?? null,
          turnExchangeId: parsed?.turnExchangeId ?? null,
          schema29ParseDiagnostics
        }
      );
    }
  } catch {
    // Diagnostics must never perturb identity extraction.
  }
  _cwaIdcapPendingResponseBodyRequestId = null;
  return parsed;
};

executeNativeTurn = async function _cwaIdcapExecuteNativeTurnWithCapture(message) {
  const isRichWrite =
    Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0;
  const capture = {
    schema: CWA_IDCAP_CAPTURE_SCHEMA,
    captureId: ++_cwaIdcapCaptureCounter,
    mode: isRichWrite ? "rich_write" : "ordinary_text",
    startedAtMs: Date.now(),
    finishedAtMs: null,
    requestedConversationId:
      typeof message?.conversationId === "string" && message.conversationId.trim()
        ? message.conversationId.trim()
        : null,
    expectedTextLength: typeof message?.text === "string" ? message.text.length : 0,
    expectedAttachmentCount: isRichWrite ? message.attachmentPaths.length : 0,
    protectedSubmitArmMarkerObserved: false,
    conversationWriteRequests: [],
    identityParses: [],
    result: null,
    error: null
  };

  const observer = (source, method, params) => {
    if (_cwaIdcapActiveCapture !== capture) return;
    try {
      if (method === "Runtime.consoleAPICalled") {
        if (capture.protectedSubmitArmMarkerObserved) return;
        const args = Array.isArray(params?.args) ? params.args : [];
        if (
          args.some(
            (arg) =>
              typeof arg?.value === "string" &&
              arg.value.startsWith(PR92_SCHEMA20_ARM_MARKER_PREFIX)
          )
        ) {
          capture.protectedSubmitArmMarkerObserved = true;
        }
        return;
      }
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (!_cwaIdcapIsConversationWrite(request?.url || "", request?.method || "")) {
          return;
        }
        const requestId = _cwaIdcapNonEmptyString(params?.requestId);
        if (requestId === null) return;
        const existing = capture.conversationWriteRequests.some(
          (entry) => entry.requestId === requestId
        );
        if (existing) return;

        const entry = {
          requestId,
          url: _cwaIdcapSanitizeUrl(request?.url || ""),
          method: request?.method || null,
          hasUserGesture: params?.hasUserGesture === true,
          observedAtMs: Date.now(),
          responseStatus: null,
          responseMimeType: null,
          loadingFinished: false,
          loadingFailedReason: null,
          requestBodyIdentity: null
        };
        capture.conversationWriteRequests = _cwaIdcapPushBounded(
          capture.conversationWriteRequests,
          CWA_IDCAP_MAX_REQUESTS,
          entry
        );

        // Read-only request-body identity parse. The raw body is discarded;
        // only safe identity facts are retained. Read-only CDP access reuses
        // the write path's attached session and can never perturb it.
        try {
          const pending = sendCommand(source, "Network.getRequestPostData", {
            requestId
          });
          Promise.resolve(pending)
            .then((response) => {
              entry.requestBodyIdentity = _cwaIdcapParseRequestBodyIdentity(
                response?.postData,
                response?.base64Encoded === true
              );
            })
            .catch(() => {
              entry.requestBodyIdentity = { resolved: false };
            });
        } catch {
          entry.requestBodyIdentity = { resolved: false };
        }
        return;
      }
      if (method === "Network.responseReceived") {
        const entry = capture.conversationWriteRequests.find(
          (candidate) => candidate.requestId === params?.requestId
        );
        if (entry) {
          entry.responseStatus = params?.response?.status ?? null;
          entry.responseMimeType = params?.response?.mimeType ?? null;
        }
        return;
      }
      if (method === "Network.dataReceived") {
        const entry = capture.conversationWriteRequests.find(
          (candidate) => candidate.requestId === params?.requestId
        );
        if (entry) {
          _cwaIdcapProcessSseChunk(capture, entry, params?.data);
        }
        return;
      }
      if (method === "Network.loadingFinished") {
        const entry = capture.conversationWriteRequests.find(
          (candidate) => candidate.requestId === params?.requestId
        );
        if (entry) entry.loadingFinished = true;
        return;
      }
      if (method === "Network.loadingFailed") {
        const entry = capture.conversationWriteRequests.find(
          (candidate) => candidate.requestId === params?.requestId
        );
        if (entry) entry.loadingFailedReason = "LOADING_FAILED";
      }
    } catch {
      // Observation must never throw into the write path.
    }
  };

  chrome.debugger.onEvent.addListener(observer);
  _cwaIdcapActiveCapture = capture;
  let sseFlushed = false;
  try {
    const result = await _cwaIdcapPriorExecuteNativeTurn(message);
    for (const entry of capture.conversationWriteRequests) {
      _cwaIdcapFlushSseEntry(capture, entry);
    }
    sseFlushed = true;
    capture.finishedAtMs = Date.now();
    const finalUrl = typeof result?.finalUrl === "string" ? result.finalUrl : "";
    capture.result = {
      ok: true,
      promotedConversationId: result?.conversationId ?? null,
      turnExchangeId: result?.turnExchangeId ?? null,
      responseStatus: result?.responseStatus ?? null,
      responseMimeType: result?.responseMimeType ?? null,
      finalUrl: _cwaIdcapSanitizeUrl(finalUrl),
      routeConversationId: conversationIdFromUrl(finalUrl),
      routeConversationIdAuthority: "ROUTE_DIAGNOSTIC_ONLY",
      elapsedMs: result?.elapsedMs ?? null,
      submitStrategy: result?.submitStrategy ?? null
    };
    return { ...result, cwaIdentityCaptureDiag: capture };
  } catch (error) {
    for (const entry of capture.conversationWriteRequests) {
      _cwaIdcapFlushSseEntry(capture, entry);
    }
    sseFlushed = true;
    capture.finishedAtMs = Date.now();
    capture.error = _cwaIdcapStableReason(error);
    throw error;
  } finally {
    if (!sseFlushed) {
      for (const entry of capture.conversationWriteRequests) {
        _cwaIdcapFlushSseEntry(capture, entry);
      }
    }
    if (_cwaIdcapActiveCapture === capture) _cwaIdcapActiveCapture = null;
    _cwaIdcapPendingResponseBodyRequestId = null;
    chrome.debugger.onEvent.removeListener(observer);
    _cwaIdcapPersist(capture);
  }
};

// reload-probe: force unpacked-extension watcher reload (content-only change)
