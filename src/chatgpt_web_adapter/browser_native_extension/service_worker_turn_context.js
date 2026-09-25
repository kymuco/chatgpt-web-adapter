// PR15.37 explicit rich-input turn-context owner.
//
// Historical schema layers progressively extended the shared context factory:
// base deadline/staging state, schema 19 request-bound identity state, then
// schema 20 protected-submit state. Keep that composition explicit and remove
// runtime replacement / captured-prior ownership.

function _pr92CreateTurnContext(message) {
  return _pr92Schema20CreateTurnContext(message);
}
