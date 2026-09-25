// PR15.50 final explicit browser response-stream hook owner.
//
// Historical shipping load order produced:
//   Temporary session identity
//   → PR8.12 response activity / answer channel
//   → PR8.11 early-completion / tail timing
//   → PR8.9 base stream primitives.
//
// Keep the public hooks as normal declarations while retaining that exact
// outer-to-inner behavior.

async function _pr89BrowserStreamProcessSseEvent(context, block) {
  return _pr813ProcessSseWithTemporarySessionIdentity(context, block);
}

function _pr89BrowserStreamVisibleAssistantText(message) {
  return _pr812VisibleAssistantTextOwner(message);
}

async function _pr89BrowserStreamRecordAssistant(context, candidate) {
  return _pr812RecordAssistantOwner(context, candidate);
}
