// Single observability/response page-turn composition owner.
//
// Recovery provides the terminal page-turn implementation. The six
// observability layers expose (args, next) functions and are composed here once
// in the exact historical outer-to-inner order.
const CWA_OBSERVABILITY_PAGE_TURN_LAYERS = Object.freeze([
  ["early-completion-repair", _pr8111RepairExecuteOfficialPageTurn],
  ["early-completion", _pr8111ExecuteOfficialPageTurn],
  ["post-answer-tail-timing", _executeOfficialPageTurnWithPostAnswerTailTiming],
  ["safe-browser-stream", _executeOfficialPageTurnWithSafeBrowserStream],
  ["instant-observation", _executeOfficialPageTurnWithInstantObservation],
  ["phase-timing", _executeOfficialPageTurnWithPhaseTiming]
]);

async function _cwaRunObservabilityPageTurnLayer(index, args) {
  if (index >= CWA_OBSERVABILITY_PAGE_TURN_LAYERS.length) {
    return _executeOfficialPageTurnWithEarlyTerminalBoundary(args);
  }

  const [name, layer] = CWA_OBSERVABILITY_PAGE_TURN_LAYERS[index];
  if (typeof layer !== "function") {
    throw new Error(`CWA_OBSERVABILITY_PAGE_TURN_LAYER_MISSING:${name}`);
  }

  return layer(
    args,
    (nextArgs) => _cwaRunObservabilityPageTurnLayer(index + 1, nextArgs)
  );
}

async function _executeOfficialPageTurnWithObservabilityLifecycle(args) {
  return _cwaRunObservabilityPageTurnLayer(0, args);
}
