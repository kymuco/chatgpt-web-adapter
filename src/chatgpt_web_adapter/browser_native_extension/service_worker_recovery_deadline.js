// PR15.44 explicit recovery/deadline owner.
//
// The recovery primitives originate in the base worker / PR8.11 recovery layer.
// PR9.2 contributes only bounded rich-turn deadline behavior and post-recovery
// attachment staging. Keep those stages explicit without captured-prior aliases
// or source-order reassignment.

async function waitForTabComplete(tabId, timeoutMs = 45_000) {
  return _pr92WaitForTabCompleteWithinTurn(tabId, timeoutMs);
}

async function _pr811ReloadRuntimeTabAndWait(tabId, expectedConversationId) {
  return _pr92ReloadRuntimeTabWithinTurn(tabId, expectedConversationId);
}

async function _pr811MaybeRecoverStaleRuntimeUi(message) {
  return _pr92RecoverThenStage(message);
}
