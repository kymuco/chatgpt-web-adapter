// PR15.33 explicit attachment cleanup/fence owner.
//
// Historical rich-input generations progressively replaced the shared attachment
// fence persistence/clear and destructive stale-tab cleanup names. The final
// effective production generations are schema7 for fence persistence/clear and
// schema8 for destructive stale-tab cleanup.

async function _pr92PersistDirtyAttachmentFence(tabId) {
  return _pr92Schema7PersistDirtyAttachmentFence(tabId);
}

async function _pr92TryClearDirtyAttachmentFence() {
  return _pr92Schema7TryClearDirtyAttachmentFence();
}

async function _pr92ClearOfficialPageAttachments(tabId, timeoutMs) {
  return _pr92Schema8ClearFencedRuntimeTab(tabId, timeoutMs);
}
