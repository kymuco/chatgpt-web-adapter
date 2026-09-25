// PR15.36 explicit conversation-write predicate owner.
//
// The base URL/method classifier is intentionally separate from rich-input
// submit authority. Schema 20 gates the public predicate until the protected
// page-side arm marker has been observed, while schema 29 still needs the
// ungated structural classifier when recording requests that are already post-arm.

function isConversationWrite(url, method) {
  return _pr92Schema20SubmitBoundConversationWrite(url, method);
}
