// PR15.38 explicit raw submit primitive owner.
//
// Historical source-order composition wrapped the base mouse/Enter primitives
// with deadline-aware rich-input behavior and then a closure guard that forbids
// raw CDP submission during an active rich turn. Keep that call graph explicit
// while preserving text-only fallback through the deadline helper to the base.

async function clickSendButton(debuggee, point) {
  return _pr92ClosureRejectRawMouseSubmit(debuggee, point);
}

async function submitWithEnter(debuggee) {
  return _pr92ClosureRejectRawEnterSubmit(debuggee);
}
