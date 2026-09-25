// PR15.46 explicit submit-readiness owner.
//
// The base worker owns the bounded send-button polling primitive. PR9.2 schema12
// adds only the active rich-turn outer-deadline race. Keep that composition
// explicit without captured-prior aliases or source-order reassignment.

async function waitForSendButtonPoint(
  debuggee,
  timeoutMs = DEFAULT_SUBMIT_READY_TIMEOUT_MS
) {
  return _pr92Schema12DeadlineBoundedSendReadiness(debuggee, timeoutMs);
}
