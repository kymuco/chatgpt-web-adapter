// PR15.41 explicit request-inspection owner.
//
// Schema 29 owns the request-correlation authority. The request-text-shape and
// browser-indent compatibility layers only adapt already-textual evidence before
// delegating back into schema 29.

function _pr92Schema29InspectRequestPostData(
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) {
  return _cwaBrowserIndentInspect(
    postData,
    expectedText,
    expectedAttachmentCount,
    expectedConversationId
  );
}
