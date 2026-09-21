// Explicit rich-input native-turn composition owner.
//
// Historical rich-input generations used import-order monkeypatching of
// executeNativeTurn. Their lower-level attachment, submit, page-turn, identity,
// and diagnostic hooks remain in the original modules; native-turn lifecycle
// ownership is composed here explicitly.
//
// Order is outer -> inner and matches the pre-consolidation wrapper chain.
const _cwaRichInputLifecyclePriorExecuteNativeTurn = executeNativeTurn;

const CWA_RICH_INPUT_LIFECYCLE_LAYERS = Object.freeze([
  ["schema29", _executeNativeTurnWithPr92Schema29Repair],
  ["schema28", _executeNativeTurnWithPr92Schema28Repair],
  ["schema18", _executeNativeTurnWithPr92Schema18Repair],
  ["schema14", _executeNativeTurnWithPr92Schema14CompositionGuard],
  ["closure", _executeNativeTurnWithPr92ClosureRepair],
  ["base-rich-input", _executeNativeTurnWithPr92RichInput]
]);

async function _cwaRunRichInputLifecycleLayer(index, message) {
  if (index >= CWA_RICH_INPUT_LIFECYCLE_LAYERS.length) {
    return _cwaRichInputLifecyclePriorExecuteNativeTurn(message);
  }

  const [name, layer] = CWA_RICH_INPUT_LIFECYCLE_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`CWA_RICH_INPUT_LIFECYCLE_LAYER_MISSING:${name}`);
  }

  return layer(
    message,
    (nextMessage) => _cwaRunRichInputLifecycleLayer(index + 1, nextMessage)
  );
}

executeNativeTurn = async function _executeNativeTurnWithRichInputLifecycle(message) {
  return _cwaRunRichInputLifecycleLayer(0, message);
};
