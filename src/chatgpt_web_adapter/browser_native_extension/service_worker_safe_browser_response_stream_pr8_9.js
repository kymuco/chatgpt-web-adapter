// PR8.9 Candidate B: bounded safe browser response-stream characterization.
//
// Diagnostic-only. It never changes request payloads, never pauses or fulfills
// network requests, and never exports raw response bytes, headers, cookies,
// credentials, or protection material. It observes only the one official
// conversation response already owned by the page and reduces it browser-locally
// to revision-safe assistant-text metadata.

const PR89_BROWSER_STREAM_SCHEMA_VERSION = 1;
const PR89_BROWSER_STREAM_MAX_OBSERVATIONS = 64;
const PR89_BROWSER_STREAM_MAX_PREVIEW_CHARS = 160;
const PR89_BROWSER_STREAM_MAX_SSE_BUFFER_CHARS = 262144;

const _pr89BrowserStreamPriorExecuteNativeTurn = executeNativeTurn;
const _pr89BrowserStreamPriorExecuteOfficialPageTurn = executeOfficialPageTurn;

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

function _pr89BrowserStreamVisibleAssistantText(message) {
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

async function _pr89BrowserStreamRecordAssistant(context, candidate) {
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

async function _pr89BrowserStreamProcessSseEvent(context, block) {
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

function _pr89BrowserStreamSafeResult(context) {
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

executeOfficialPageTurn = async function _executeOfficialPageTurnWithSafeBrowserStream(args) {
  const context = _pr89BrowserStreamContext;
  if (context === null) return _pr89BrowserStreamPriorExecuteOfficialPageTurn(args);

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
    return await _pr89BrowserStreamPriorExecuteOfficialPageTurn(args);
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

executeNativeTurn = async function _executeNativeTurnWithSafeBrowserStream(message) {
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
    return _pr89BrowserStreamPriorExecuteNativeTurn(message);
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
    const result = await _pr89BrowserStreamPriorExecuteNativeTurn(message);
    await context.processing;
    return {
      ...result,
      safeBrowserResponseStreaming: _pr89BrowserStreamSafeResult(context)
    };
  } finally {
    _pr89BrowserStreamContext = null;
  }
};