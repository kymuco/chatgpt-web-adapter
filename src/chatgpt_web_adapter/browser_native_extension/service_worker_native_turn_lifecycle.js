// Single active native-turn composition owner.
//
// All domain modules expose (message, next) layers. The runtime assembles them
// once, after every domain has loaded, preserving the exact historical
// outer-to-inner order while eliminating import-order executeNativeTurn
// reassignment as a composition mechanism.

const _cwaNativeTurnBaseExecute = executeNativeTurn;

const CWA_NATIVE_TURN_LAYERS = Object.freeze([
  ["ordinary-text-identity", _cwaOrdinaryIdentityExecuteNativeTurn],
  ["rich-input", _executeNativeTurnWithRichInputLifecycle],
  ["browser-authority-lease", _executeNativeTurnWithBrowserAuthorityLease],
  ["temporary", _executeNativeTurnWithTemporaryLifecycle],
  ["response", _executeNativeTurnWithResponseLifecycle],
  ["selection", _executeNativeTurnWithSelectionLifecycle],
  ["stale-ui-recovery", _executeNativeTurnWithStaleUiRecovery]
]);

async function _cwaRunNativeTurnLayer(index, message) {
  if (index >= CWA_NATIVE_TURN_LAYERS.length) {
    return _cwaNativeTurnBaseExecute(message);
  }

  const [name, layer] = CWA_NATIVE_TURN_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`CWA_NATIVE_TURN_LAYER_MISSING:${name}`);
  }

  return layer(
    message,
    (nextMessage) => _cwaRunNativeTurnLayer(index + 1, nextMessage)
  );
}

executeNativeTurn = async function _executeNativeTurnWithRuntimeLifecycle(message) {
  return _cwaRunNativeTurnLayer(0, message);
};
