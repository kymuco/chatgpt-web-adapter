// PR8.9.3: production revision-safe assistant-text event delivery.
//
// This layer reuses the proven Candidate-B CDP response observer and product
// patch-stream parser. It exports only reduced assistant text events for the
// active request_id; raw SSE, headers, cookies, request bodies and protection
// material never leave the browser worker.

const _pr89DeliveryPriorRecordAssistant = _pr89BrowserStreamRecordAssistant;
const _pr89DeliveryPriorExecuteNativeTurn = executeNativeTurn;

let _pr89DeliveryRequestId = null;

function _pr89DeliveryEventType(kind) {
  if (kind === "SNAPSHOT") return "assistant_text_snapshot";
  if (kind === "DELTA") return "assistant_text_delta";
  return "assistant_text_revision";
}

_pr89BrowserStreamRecordAssistant = async function _pr89RecordAssistantWithDelivery(context, candidate) {
  const text = candidate?.text;
  const key = candidate?.messageKey;
  if (typeof text !== "string" || typeof key !== "string" || !key) {
    return _pr89DeliveryPriorRecordAssistant(context, candidate);
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

  await _pr89DeliveryPriorRecordAssistant(context, candidate);

  const requestId = _pr89DeliveryRequestId;
  if (typeof requestId !== "string" || !requestId) return;

  const event = {
    type: _pr89DeliveryEventType(kind),
    sequence: context.assistantTextEventCount,
    observed_at_ms: _pr89BrowserStreamElapsedMs(context),
    message_id: candidate.messageId || null,
    content_type: candidate.contentType || null,
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
};

executeNativeTurn = async function _executeNativeTurnWithRevisionSafeTextDelivery(message) {
  if (message?.streamTextObservations !== true) {
    return _pr89DeliveryPriorExecuteNativeTurn(message);
  }
  const requestId = typeof message?.request_id === "string" ? message.request_id.trim() : "";
  if (!requestId) throw new Error("PR8_9_STREAM_DELIVERY_REQUEST_ID_REQUIRED");
  if (_pr89DeliveryRequestId !== null) {
    throw new Error("PR8_9_STREAM_DELIVERY_ALREADY_ACTIVE");
  }

  const alreadyCharacterizing = message?.characterizeSafeBrowserResponseStreaming === true;
  _pr89DeliveryRequestId = requestId;
  try {
    const result = await _pr89DeliveryPriorExecuteNativeTurn(
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
