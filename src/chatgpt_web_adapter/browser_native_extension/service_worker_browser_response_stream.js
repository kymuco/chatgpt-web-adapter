// PR15.19 explicit production owner for browser response streaming.
//
// Consolidates the PR8.9 safe CDP stream observer, product p/v patch reducer,
// and revision-safe text delivery into one shipping module. Core reducers remain
// explicit so later PR8.11/PR8.12 response overlays can preserve their historical
// hooks without PR8.9 relying on import-order reassignment.

const PR89_BROWSER_STREAM_SCHEMA_VERSION = 1;
const PR89_BROWSER_STREAM_MAX_OBSERVATIONS = 64;
const PR89_BROWSER_STREAM_MAX_PREVIEW_CHARS = 160;
const PR89_BROWSER_STREAM_MAX_SSE_BUFFER_CHARS = 262144;


let _pr89BrowserStreamContext = null;

function _pr89BrowserStreamElapsedMs(context) {
  return Math.max(0, Math.round(performance.now() - context.startedAt));
}

function _pr89BrowserStreamPreview(text) {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  if (compact.length <= PR89_BROWSER_STREAM_MAX_PREVIEW_CHARS) return compact;
  return compact.slice(0, PR89_BROWSER_STREAM_MAX_PREVIEW_CHARS - 1) + "…";
}

function _pr89BrowserStreamBase64Bytes(value) {
  if (typeof value !== "string" || !value) return new Uint8Array(0);
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function _pr89BrowserStreamSha256(text) {
  const bytes = new TextEncoder().encode(String(text || ""));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function _pr89BrowserStreamFinishReason(message) {
  const metadata = message?.metadata;
  const finishDetails = metadata && typeof metadata === "object"
    ? metadata.finish_details
    : null;
  if (finishDetails && typeof finishDetails === "object" &&
      typeof finishDetails.type === "string" && finishDetails.type.trim()) {
    return finishDetails.type.trim();
  }
  if (metadata && typeof metadata.finish_reason === "string" &&
      metadata.finish_reason.trim()) {
    return metadata.finish_reason.trim();
  }
  return typeof message?.finish_reason === "string" && message.finish_reason.trim()
    ? message.finish_reason.trim()
    : null;
}

function _pr89BaseBrowserStreamVisibleAssistantText(message) {
  if (!message || typeof message !== "object") return null;
  if (message?.author?.role !== "assistant") return null;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return null;

  const recipient = typeof message.recipient === "string"
    ? message.recipient.trim()
    : "";
  if (recipient && recipient !== "all") return null;

  const content = message.content;
  if (!content || typeof content !== "object") return null;
  const contentType = typeof content.content_type === "string"
    ? content.content_type.trim()
    : "";
  if (contentType && contentType !== "text" && contentType !== "multimodal_text") {
    return null;
  }

  const parts = Array.isArray(content.parts) ? content.parts : [];
  let text = "";
  for (const part of parts) {
    if (typeof part === "string") {
      text += part;
    } else if (part && typeof part === "object" && typeof part.text === "string") {
      text += part.text;
    }
  }
  if (!text.trim() && typeof content.text === "string") {
    text = content.text;
  }
  if (!text.trim()) return null;

  const messageId = typeof message.id === "string" && message.id.trim()
    ? message.id.trim()
    : null;
  return {
    messageKey: messageId || "assistant-current",
    messageId,
    contentType: contentType || null,
    text,
    finishReason: _pr89BrowserStreamFinishReason(message)
  };
}

function _pr89BrowserStreamCollectAssistantMessages(value, output, depth = 0) {
  if (depth > 7 || value == null) return;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 128)) {
      _pr89BrowserStreamCollectAssistantMessages(item, output, depth + 1);
    }
    return;
  }
  if (typeof value !== "object") return;

  const candidate = _pr89BrowserStreamVisibleAssistantText(value);
  if (candidate) output.push(candidate);

  for (const key of ["message", "messages", "data", "result", "payload", "turn"]) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      _pr89BrowserStreamCollectAssistantMessages(value[key], output, depth + 1);
    }
  }
}

async function _pr89BrowserStreamRecordAssistantCore(context, candidate) {
  const text = candidate.text;
  const previous = context.lastTextByKey.get(candidate.messageKey);
  if (previous === text) return;

  let kind = "SNAPSHOT";
  let delta = null;
  if (previous != null) {
    if (text.startsWith(previous)) {
      kind = "DELTA";
      delta = text.slice(previous.length);
    } else {
      kind = "REVISION";
    }
  }

  context.lastTextByKey.set(candidate.messageKey, text);
  context.assistantTextEventCount += 1;
  const observedAtMs = _pr89BrowserStreamElapsedMs(context);
  if (context.firstTextObservedMs === null) context.firstTextObservedMs = observedAtMs;
  context.lastTextObservedMs = observedAtMs;
  if (context.loadingFinishedMs === null) context.preNetworkCompleteTextObserved = true;

  const textSha256 = await _pr89BrowserStreamSha256(text);
  const previousTextSha256 = previous == null
    ? null
    : await _pr89BrowserStreamSha256(previous);
  const deltaSha256 = delta ? await _pr89BrowserStreamSha256(delta) : null;

  if (context.observations.length < PR89_BROWSER_STREAM_MAX_OBSERVATIONS) {
    context.observations.push({
      sequence: context.assistantTextEventCount,
      kind,
      observedAtMs,
      messageKey: candidate.messageKey,
      messageId: candidate.messageId,
      contentType: candidate.contentType,
      textLength: text.length,
      textSha256,
      textPreview: _pr89BrowserStreamPreview(text),
      deltaLength: delta == null ? null : delta.length,
      deltaSha256,
      deltaPreview: delta == null ? null : _pr89BrowserStreamPreview(delta),
      previousTextSha256,
      finishReason: candidate.finishReason,
      beforeNetworkComplete: context.loadingFinishedMs === null
    });
  } else {
    context.observationsTruncated = true;
  }
}

async function _pr89BrowserStreamProcessSseEventFullEnvelope(context, block) {
  const lines = String(block || "").split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return;
  context.sseEventCount += 1;

  const data = dataLines.join("\n").trim();
  if (!data || data === "[DONE]") return;

  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    context.nonJsonSseEventCount += 1;
    return;
  }
  context.jsonEventCount += 1;

  const candidates = [];
  _pr89BrowserStreamCollectAssistantMessages(payload, candidates);
  for (const candidate of candidates) {
    await _pr89BrowserStreamRecordAssistant(context, candidate);
  }
}

async function _pr89BrowserStreamProcessBytes(context, bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length === 0) return;
  const decoded = context.decoder.decode(bytes, { stream: true });
  if (!decoded) return;
  context.sseBuffer += decoded;

  if (context.sseBuffer.length > PR89_BROWSER_STREAM_MAX_SSE_BUFFER_CHARS) {
    context.sseBuffer = context.sseBuffer.slice(-PR89_BROWSER_STREAM_MAX_SSE_BUFFER_CHARS);
    context.sseBufferTruncated = true;
  }

  while (true) {
    const match = /\r?\n\r?\n/.exec(context.sseBuffer);
    if (!match) break;
    const block = context.sseBuffer.slice(0, match.index);
    context.sseBuffer = context.sseBuffer.slice(match.index + match[0].length);
    await _pr89BrowserStreamProcessSseEvent(context, block);
  }
}

function _pr89BrowserStreamEnqueueBase64(context, base64Data, source) {
  if (typeof base64Data !== "string" || !base64Data) return;
  let bytes;
  try {
    bytes = _pr89BrowserStreamBase64Bytes(base64Data);
  } catch {
    context.decodeErrorCount += 1;
    return;
  }
  if (source === "buffered") context.bufferedByteLength += bytes.length;
  else context.dataByteLength += bytes.length;

  context.processing = context.processing
    .then(() => _pr89BrowserStreamProcessBytes(context, bytes))
    .catch(() => {
      context.processingErrorCount += 1;
    });
}

async function _pr89BrowserStreamEnable(debuggee, context) {
  if (context.streamResourceContentAttempted) return;
  context.streamResourceContentAttempted = true;
  try {
    const result = await chrome.debugger.sendCommand(
      debuggee,
      "Network.streamResourceContent",
      { requestId: context.conversationRequestId }
    );
    context.streamResourceContentSupported = true;
    context.streamResourceContentEnabledMs = _pr89BrowserStreamElapsedMs(context);
    _pr89BrowserStreamEnqueueBase64(context, result?.bufferedData, "buffered");

    context.streamResourceContentReady = true;
    const pending = context.pendingData.splice(0);
    for (const value of pending) {
      _pr89BrowserStreamEnqueueBase64(context, value, "data");
    }
  } catch (error) {
    context.streamResourceContentSupported = false;
    context.streamResourceContentError = error instanceof Error ? error.message : String(error);
    context.pendingData.length = 0;
  }
}

function _pr89BrowserStreamCreateContext() {
  return {
    startedAt: performance.now(),
    conversationRequestId: null,
    responseStatus: null,
    responseMimeType: null,
    responseReceivedMs: null,
    loadingFinishedMs: null,
    streamResourceContentAttempted: false,
    streamResourceContentSupported: null,
    streamResourceContentReady: false,
    streamResourceContentEnabledMs: null,
    streamResourceContentError: null,
    bufferedByteLength: 0,
    dataEventCount: 0,
    dataByteLength: 0,
    pendingData: [],
    decoder: new TextDecoder("utf-8"),
    sseBuffer: "",
    sseBufferTruncated: false,
    sseEventCount: 0,
    jsonEventCount: 0,
    nonJsonSseEventCount: 0,
    decodeErrorCount: 0,
    processingErrorCount: 0,
    assistantTextEventCount: 0,
    firstTextObservedMs: null,
    lastTextObservedMs: null,
    preNetworkCompleteTextObserved: false,
    lastTextByKey: new Map(),
    observations: [],
    observationsTruncated: false,
    processing: Promise.resolve()
  };
}

function _pr89BrowserStreamSafeResultCore(context) {
  const first = context.firstTextObservedMs;
  const networkDone = context.loadingFinishedMs;
  return {
    schemaVersion: PR89_BROWSER_STREAM_SCHEMA_VERSION,
    source: "CDP_NETWORK_STREAM_RESOURCE_CONTENT",
    experimentalCdpMethod: true,
    conversationRequestObserved: typeof context.conversationRequestId === "string",
    responseStatus: Number.isFinite(context.responseStatus) ? context.responseStatus : null,
    responseMimeType: typeof context.responseMimeType === "string" ? context.responseMimeType : null,
    responseReceivedMs: context.responseReceivedMs,
    loadingFinishedMs: networkDone,
    streamResourceContentAttempted: context.streamResourceContentAttempted,
    streamResourceContentSupported: context.streamResourceContentSupported,
    streamResourceContentEnabledMs: context.streamResourceContentEnabledMs,
    streamResourceContentError: context.streamResourceContentError,
    bufferedByteLength: context.bufferedByteLength,
    dataEventCount: context.dataEventCount,
    dataByteLength: context.dataByteLength,
    sseEventCount: context.sseEventCount,
    jsonEventCount: context.jsonEventCount,
    nonJsonSseEventCount: context.nonJsonSseEventCount,
    decodeErrorCount: context.decodeErrorCount,
    processingErrorCount: context.processingErrorCount,
    assistantTextEventCount: context.assistantTextEventCount,
    firstTextObservedMs: first,
    lastTextObservedMs: context.lastTextObservedMs,
    preNetworkCompleteTextObserved: context.preNetworkCompleteTextObserved,
    firstTextLeadBeforeNetworkCompleteMs: (
      first !== null && networkDone !== null && networkDone >= first
    ) ? networkDone - first : null,
    observationCount: context.observations.length,
    observationsTruncated: context.observationsTruncated,
    sseBufferTruncated: context.sseBufferTruncated,
    observations: context.observations
  };
}

async function _executeOfficialPageTurnWithSafeBrowserStream(args, next) {
  const context = _pr89BrowserStreamContext;
  if (context === null) return next(args);

  const tabId = args?.tabId;
  const debuggee = { tabId };
  let listenerInstalled = false;

  const observer = (source, method, params) => {
    try {
      if (source?.tabId !== tabId) return;

      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (
          context.conversationRequestId === null &&
          isConversationWrite(request?.url || "", request?.method || "")
        ) {
          context.conversationRequestId = params.requestId;
        }
        return;
      }

      if (
        context.conversationRequestId === null ||
        params?.requestId !== context.conversationRequestId
      ) return;

      if (method === "Network.responseReceived") {
        context.responseStatus = params?.response?.status ?? null;
        context.responseMimeType = typeof params?.response?.mimeType === "string"
          ? params.response.mimeType
          : null;
        context.responseReceivedMs = _pr89BrowserStreamElapsedMs(context);
        void _pr89BrowserStreamEnable(debuggee, context);
        return;
      }

      if (method === "Network.dataReceived") {
        context.dataEventCount += 1;
        if (typeof params?.data !== "string" || !params.data) return;
        if (!context.streamResourceContentReady) context.pendingData.push(params.data);
        else _pr89BrowserStreamEnqueueBase64(context, params.data, "data");
        return;
      }

      if (method === "Network.loadingFinished") {
        context.loadingFinishedMs = _pr89BrowserStreamElapsedMs(context);
      }
    } catch {
      context.processingErrorCount += 1;
    }
  };

  try {
    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
  } catch {
    listenerInstalled = false;
  }

  try {
    return await next(args);
  } finally {
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Diagnostic cleanup only.
      }
    }
    try {
      await context.processing;
      const tail = context.decoder.decode();
      if (tail) context.sseBuffer += tail;
      if (context.sseBuffer.trim()) {
        await _pr89BrowserStreamProcessSseEvent(context, context.sseBuffer);
        context.sseBuffer = "";
      }
    } catch {
      context.processingErrorCount += 1;
    }
  }
};

async function _executeNativeTurnWithSafeBrowserStream(message, next) {
  if (message?.characterizeSafeBrowserResponseStreamingSupport === true) {
    if (message?.text != null || message?.conversationId != null) {
      throw new Error("PR8_9_BROWSER_STREAM_SUPPORT_FLAG_CONFLICT");
    }
    return {
      probeContext: "pr8_9_safe_browser_response_streaming_support",
      readOnly: true,
      safeBrowserResponseStreamingSupported: true,
      schemaVersion: PR89_BROWSER_STREAM_SCHEMA_VERSION,
      cdpMethod: "Network.streamResourceContent",
      experimentalCdpMethod: true
    };
  }

  if (message?.characterizeSafeBrowserResponseStreaming !== true) {
    return next(message);
  }

  const text = typeof message?.text === "string" ? message.text.trim() : "";
  const leaseId = typeof message?.browserAuthorityLeaseId === "string"
    ? message.browserAuthorityLeaseId.trim()
    : "";
  if (!text || !leaseId) {
    throw new Error("PR8_9_BROWSER_STREAM_REQUIRES_ORDINARY_LEASED_WRITE");
  }
  if (_pr89BrowserStreamContext !== null) {
    throw new Error("PR8_9_BROWSER_STREAM_CONTEXT_ALREADY_ACTIVE");
  }

  const context = _pr89BrowserStreamCreateContext();
  _pr89BrowserStreamContext = context;
  try {
    const result = await next(message);
    await context.processing;
    return {
      ...result,
      safeBrowserResponseStreaming: _pr89BrowserStreamSafeResult(context)
    };
  } finally {
    _pr89BrowserStreamContext = null;
  }
};

function _pr89PatchEnsureState(context) {
  if (context.patchProtocolInitialized === true) return;
  context.patchProtocolInitialized = true;
  context.patchProtocolEventCount = 0;
  context.patchTextDeltaCount = 0;
  context.patchMessageSkeletonCount = 0;
  context.patchMetadataUpdateCount = 0;
  context.patchAssistantActive = false;
  context.patchRecipient = "all";
  context.patchMessageId = null;
  context.patchMessageKey = "assistant-current";
  context.patchContentType = "text";
  context.patchFinishReason = null;
  context.patchTextByKey = new Map();
}

function _pr89PatchOptionalString(value) {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function _pr89PatchMetadataFinishReason(metadata) {
  if (!metadata || typeof metadata !== "object") return null;
  const details = metadata.finish_details;
  if (details && typeof details === "object") {
    const value = _pr89PatchOptionalString(details.type);
    if (value) return value;
  }
  return _pr89PatchOptionalString(metadata.finish_reason);
}

function _pr89PatchVisibleContentType(message) {
  const value = _pr89PatchOptionalString(message?.content?.content_type);
  if (value === "text" || value === "multimodal_text") return value;
  return value || "text";
}

async function _pr89PatchSelectMessage(context, message) {
  _pr89PatchEnsureState(context);
  if (!message || typeof message !== "object") return;

  context.patchMessageSkeletonCount += 1;
  const role = _pr89PatchOptionalString(message?.author?.role);
  const recipient = _pr89PatchOptionalString(message?.recipient) || "all";
  const hidden = message?.metadata?.is_visually_hidden_from_conversation === true;
  const contentType = _pr89PatchVisibleContentType(message);
  const visibleType = contentType === "text" || contentType === "multimodal_text";

  context.patchRecipient = recipient;
  context.patchAssistantActive = (
    role === "assistant" &&
    recipient === "all" &&
    !hidden &&
    visibleType
  );
  context.patchMessageId = _pr89PatchOptionalString(message?.id);
  context.patchMessageKey = context.patchMessageId || "assistant-current";
  context.patchContentType = contentType;
  context.patchFinishReason = _pr89BrowserStreamFinishReason(message);

  if (!context.patchAssistantActive) return;

  const full = _pr89BrowserStreamVisibleAssistantText(message);
  if (!full || !full.text) {
    if (!context.patchTextByKey.has(context.patchMessageKey)) {
      context.patchTextByKey.set(context.patchMessageKey, "");
    }
    return;
  }

  context.patchTextByKey.set(context.patchMessageKey, full.text);
  await _pr89BrowserStreamRecordAssistant(context, full);
}

async function _pr89PatchAppendText(context, token) {
  _pr89PatchEnsureState(context);
  if (
    context.patchAssistantActive !== true ||
    context.patchRecipient !== "all" ||
    typeof token !== "string" ||
    token.length === 0
  ) {
    return;
  }

  const key = context.patchMessageKey || "assistant-current";
  const previous = context.patchTextByKey.get(key) || "";
  const text = previous + token;
  context.patchTextByKey.set(key, text);
  context.patchTextDeltaCount += 1;

  await _pr89BrowserStreamRecordAssistant(context, {
    messageKey: key,
    messageId: context.patchMessageId,
    contentType: context.patchContentType || "text",
    text,
    finishReason: context.patchFinishReason
  });
}

function _pr89PatchApplyMetadata(context, metadata) {
  _pr89PatchEnsureState(context);
  if (!metadata || typeof metadata !== "object") return;
  context.patchMetadataUpdateCount += 1;
  const finishReason = _pr89PatchMetadataFinishReason(metadata);
  if (finishReason) context.patchFinishReason = finishReason;
}

async function _pr89PatchApplyPayload(context, payload) {
  _pr89PatchEnsureState(context);
  if (!payload || typeof payload !== "object") return false;

  const hasPatchEnvelope = (
    Object.prototype.hasOwnProperty.call(payload, "v") ||
    Object.prototype.hasOwnProperty.call(payload, "p")
  );
  if (!hasPatchEnvelope) return false;

  context.patchProtocolEventCount += 1;
  const value = payload.v;
  const path = payload.p;

  if (value && typeof value === "object" && !Array.isArray(value)) {
    const message = value.message;
    if (message && typeof message === "object") {
      await _pr89PatchSelectMessage(context, message);
    }
    return true;
  }

  if (typeof value === "string") {
    if (path == null || path === "/message/content/parts/0") {
      await _pr89PatchAppendText(context, value);
    }
    return true;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      if (!item || typeof item !== "object") continue;
      if (item.p === "/message/content/parts/0" && typeof item.v === "string") {
        await _pr89PatchAppendText(context, item.v);
      } else if (item.p === "/message/metadata") {
        _pr89PatchApplyMetadata(context, item.v);
      }
    }
    return true;
  }

  if (payload.type === "server_ste_metadata") {
    _pr89PatchApplyMetadata(context, payload.metadata);
  }
  return true;
}

async function _pr89BaseBrowserStreamProcessSseEvent(context, block) {
    const lines = String(block || "").split(/\r?\n/);
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    context.sseEventCount += 1;

    const data = dataLines.join("\n").trim();
    if (!data || data === "[DONE]") return;

    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      context.nonJsonSseEventCount += 1;
      return;
    }
    context.jsonEventCount += 1;

    const patchHandled = await _pr89PatchApplyPayload(context, payload);
    if (patchHandled) return;

    // Retain the original full-envelope compatibility path for any route that
    // emits complete message objects rather than p/v patches.
    const candidates = [];
    _pr89BrowserStreamCollectAssistantMessages(payload, candidates);
    for (const candidate of candidates) {
      await _pr89BrowserStreamRecordAssistant(context, candidate);
    }
}

function _pr89BrowserStreamSafeResult(context) {
    _pr89PatchEnsureState(context);
    return {
      ..._pr89BrowserStreamSafeResultCore(context),
      patchProtocolEventCount: context.patchProtocolEventCount,
      patchTextDeltaCount: context.patchTextDeltaCount,
      patchMessageSkeletonCount: context.patchMessageSkeletonCount,
      patchMetadataUpdateCount: context.patchMetadataUpdateCount,
      patchAssistantMessageIdObserved: Boolean(context.patchMessageId)
    };
}


let _pr89DeliveryRequestId = null;

function _pr89DeliveryEventType(kind) {
  if (kind === "SNAPSHOT") return "assistant_text_snapshot";
  if (kind === "DELTA") return "assistant_text_delta";
  return "assistant_text_revision";
}

async function _pr89BaseBrowserStreamRecordAssistant(context, candidate) {
  const text = candidate?.text;
  const key = candidate?.messageKey;
  if (typeof text !== "string" || typeof key !== "string" || !key) {
    return _pr89BrowserStreamRecordAssistantCore(context, candidate);
  }

  const previous = context.lastTextByKey.get(key);
  if (previous === text) return;

  let kind = "SNAPSHOT";
  let delta = null;
  if (previous != null) {
    if (text.startsWith(previous)) {
      kind = "DELTA";
      delta = text.slice(previous.length);
    } else {
      kind = "REVISION";
    }
  }

  await _pr89BrowserStreamRecordAssistantCore(context, candidate);

  const requestId = _pr89DeliveryRequestId;
  if (typeof requestId !== "string" || !requestId) return;

  const channel = candidate?.channel === "final" || candidate?.channel === "commentary"
    ? candidate.channel
    : null;
  const event = {
    type: _pr89DeliveryEventType(kind),
    sequence: context.assistantTextEventCount,
    observed_at_ms: _pr89BrowserStreamElapsedMs(context),
    message_id: candidate.messageId || null,
    content_type: candidate.contentType || null,
    channel,
    text_length: text.length,
    finish_reason: candidate.finishReason || null,
    before_network_complete: context.loadingFinishedMs === null
  };
  if (kind === "DELTA") event.delta = delta || "";
  else event.text = text;

  postNative({
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "turn_event",
    request_id: requestId,
    event
  });
}

async function _executeNativeTurnWithRevisionSafeTextDelivery(message, next) {
  if (message?.streamTextObservations !== true) {
    return next(message);
  }
  const requestId = typeof message?.request_id === "string" ? message.request_id.trim() : "";
  if (!requestId) throw new Error("PR8_9_STREAM_DELIVERY_REQUEST_ID_REQUIRED");
  if (_pr89DeliveryRequestId !== null) {
    throw new Error("PR8_9_STREAM_DELIVERY_ALREADY_ACTIVE");
  }

  const alreadyCharacterizing = message?.characterizeSafeBrowserResponseStreaming === true;
  _pr89DeliveryRequestId = requestId;
  try {
    const result = await next(
      alreadyCharacterizing
        ? message
        : { ...message, characterizeSafeBrowserResponseStreaming: true }
    );
    if (alreadyCharacterizing || !result || typeof result !== "object") return result;
    const { safeBrowserResponseStreaming: _diagnosticOnly, ...productionResult } = result;
    return productionResult;
  } finally {
    _pr89DeliveryRequestId = null;
  }
};
