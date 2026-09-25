// PR15.47 explicit dirty-attachment-fence read owner.
//
// The base PR9.2 overlay owns durable-fence decoding/fail-closed behavior.
// Schema16 adds the active-turn outer-deadline race. Keep the public read seam
// explicit without source-order reassignment.

async function _pr92ReadDirtyAttachmentFence() {
  return _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline();
}
