// PR15.8 explicit response-lifecycle composition owner.
//
// Historical response observation layers used import-order monkeypatching of
// executeNativeTurn. Their lower-level SSE/page hooks remain in the original
// modules, but native-turn lifecycle ownership is composed here explicitly.
//
// Order is outer -> inner and intentionally matches the pre-PR15.8 wrapper chain.
const CWA_RESPONSE_LIFECYCLE_LAYERS = Object.freeze([
  ["normalized-activity-stream", _pr812ExecuteNativeTurn],
  ["early-product-completion-repair", _pr8111RepairExecuteNativeTurn],
  ["early-product-completion", _pr8111ExecuteNativeTurn],
  ["post-answer-tail-timing", _executeNativeTurnWithPostAnswerTailTiming],
  ["revision-safe-text-delivery", _executeNativeTurnWithRevisionSafeTextDelivery],
  ["safe-browser-response-stream", _executeNativeTurnWithSafeBrowserStream]
]);

async function _cwaRunResponseLifecycleLayer(index, message, next) {
  if (index >= CWA_RESPONSE_LIFECYCLE_LAYERS.length) {
    return next(message);
  }

  const [name, layer] = CWA_RESPONSE_LIFECYCLE_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`PR15_8_RESPONSE_LIFECYCLE_LAYER_MISSING:${name}`);
  }

  return layer(
    message,
    (nextMessage) => _cwaRunResponseLifecycleLayer(index + 1, nextMessage, next)
  );
}

async function _executeNativeTurnWithResponseLifecycle(message, next) {
  return _cwaRunResponseLifecycleLayer(0, message, next);
}
