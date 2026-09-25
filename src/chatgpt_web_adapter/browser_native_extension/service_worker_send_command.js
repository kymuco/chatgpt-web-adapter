// PR15.39 explicit sendCommand owner.
//
// The production command path composes immutable base CDP transport, the
// mouse-release submit fallback hotfix, and ordinary-text commit-boundary
// observation without source-ordered reassignment.

function sendCommand(debuggee, method, params = undefined) {
  return _cwaOrdinaryIdentitySendCommand(debuggee, method, params);
}
