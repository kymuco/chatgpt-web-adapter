// PR15.49 explicit Temporary characterization snapshot-expression owner.
//
// This chain is detached historical PR8.7 characterization evidence; it is not
// imported by production runtime assembly. The base expression remains usable
// standalone, while the aria-action state helper becomes the effective policy
// whenever service_worker_temporary_chat_state_semantics.js has been loaded.

function _pr87TemporaryControlSnapshotExpression() {
  if (
    typeof _pr87TemporaryControlSnapshotExpressionWithAriaActionState === "function"
  ) {
    return _pr87TemporaryControlSnapshotExpressionWithAriaActionState();
  }
  return _pr87BaseTemporaryControlSnapshotExpression();
}
