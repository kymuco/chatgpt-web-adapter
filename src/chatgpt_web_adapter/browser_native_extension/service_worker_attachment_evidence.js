// PR15.32 explicit attachment-evidence owner.
//
// Historical rich-input schema generations progressively replaced the shared
// attachment-evidence expression. Schema 27 is the final effective production
// generation; later schemas do not replace this capability.

function _pr92ClosureAttachmentEvidenceExpression(expectedNames) {
  return _pr92Schema27AttachmentEvidenceExpression(expectedNames);
}
