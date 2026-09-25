// PR15.31 explicit attachment-staging owner.
//
// Historical rich-input schema generations progressively replaced the same
// staging hook. Schema 13 is the final effective production implementation.

async function _pr92StageOfficialPageAttachments(tabId, attachmentPaths, context) {
  return _pr92Schema13FullyBoundedStage(tabId, attachmentPaths, context);
}
