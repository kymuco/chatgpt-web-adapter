// Explicit model-selection and phase-timing native-turn composition owner.
//
// Historical selection layers used import-order monkeypatching of executeNativeTurn.
// Their lower-level picker, composer, page-turn, and timing hooks remain in the
// original modules; native-turn lifecycle ownership is composed here explicitly.
//
// Order is outer -> inner and matches the pre-consolidation wrapper chain.
const CWA_SELECTION_LIFECYCLE_LAYERS = Object.freeze([
  ["model-profile-selection", _executeNativeTurnWithModelProfile],
  ["instant-selection-repair", _executeNativeTurnWithInstantSelectionRepair],
  ["instant-mode-observation", _executeNativeTurnWithInstantModeObservation],
  ["phase-timing", _executeNativeTurnWithPhaseTiming]
]);

async function _cwaRunSelectionLifecycleLayer(index, message, next) {
  if (index >= CWA_SELECTION_LIFECYCLE_LAYERS.length) {
    return next(message);
  }

  const [name, layer] = CWA_SELECTION_LIFECYCLE_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`CWA_SELECTION_LIFECYCLE_LAYER_MISSING:${name}`);
  }

  return layer(
    message,
    (nextMessage) => _cwaRunSelectionLifecycleLayer(index + 1, nextMessage, next)
  );
}

async function _executeNativeTurnWithSelectionLifecycle(message, next) {
  return _cwaRunSelectionLifecycleLayer(0, message, next);
}
