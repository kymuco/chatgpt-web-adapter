// Explicit Temporary production native-turn composition owner.
//
// The PR8.13 modules retain their lower-level tab, prewrite proof, session
// identity, SSE, and startup-readiness hooks. Native-turn ownership is composed
// here explicitly instead of being defined by import-order reassignment.
//
// Order is outer -> inner and matches the historical wrapper chain.
const CWA_TEMPORARY_LIFECYCLE_LAYERS = Object.freeze([
  ["startup-readiness", _pr8132ExecuteNativeTurnWithStartupDiagnostics],
  ["fresh-identity-flush", _pr813ExecuteNativeTurnWithFreshIdentityFlush],
  ["temporary-production", _pr813ExecuteNativeTurn]
]);

async function _cwaRunTemporaryLifecycleLayer(index, message, next) {
  if (index >= CWA_TEMPORARY_LIFECYCLE_LAYERS.length) {
    return next(message);
  }

  const [name, layer] = CWA_TEMPORARY_LIFECYCLE_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`CWA_TEMPORARY_LIFECYCLE_LAYER_MISSING:${name}`);
  }

  return layer(
    message,
    (nextMessage) => _cwaRunTemporaryLifecycleLayer(index + 1, nextMessage, next)
  );
}

async function _executeNativeTurnWithTemporaryLifecycle(message, next) {
  return _cwaRunTemporaryLifecycleLayer(0, message, next);
}
