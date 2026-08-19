// PR8.9.2a: product patch-stream compatibility for Candidate-B response observation.
//
// The first live Candidate-B run proved that Network.streamResourceContent exposes
// the conversation SSE reliably, but the browser-local reducer expected full
// nested message snapshots. The existing Python web-stream parser already proves
// that this product route uses a compact {p, v} patch protocol. This layer adds
// the same bounded semantics without exporting raw SSE or changing the write.

const _pr89PatchPriorSafeResult = _pr89BrowserStreamSafeResult;

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

_pr89BrowserStreamProcessSseEvent =
  async function _pr89BrowserStreamProcessSseEventWithPatchProtocol(context, block) {
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
  };

_pr89BrowserStreamSafeResult =
  function _pr89BrowserStreamSafeResultWithPatchProtocol(context) {
    _pr89PatchEnsureState(context);
    return {
      ..._pr89PatchPriorSafeResult(context),
      patchProtocolEventCount: context.patchProtocolEventCount,
      patchTextDeltaCount: context.patchTextDeltaCount,
      patchMessageSkeletonCount: context.patchMessageSkeletonCount,
      patchMetadataUpdateCount: context.patchMetadataUpdateCount,
      patchAssistantMessageIdObserved: Boolean(context.patchMessageId)
    };
  };