// PR15.30 explicit Native Messaging router.
//
// Historical source-order composition was:
//
//   UI liveness -> canonical read v2 -> runtime-tab release -> product state -> base turn
//
// Preserve that exact outer-to-inner routing without import-time hook reassignment.

async function onNativeMessage(message, port) {
  return _cwaOnNativeMessageWithGoogleTranslate(
    message,
    port,
    (capabilityMessage, capabilityPort) =>
      _cwaOnNativeMessageWithUiLiveness(
        capabilityMessage,
        capabilityPort,
    (uiMessage, uiPort) =>
      _cwaOnNativeMessageWithCanonicalRead(
        uiMessage,
        uiPort,
        (canonicalMessage, canonicalPort) =>
          _pr88OnNativeMessageWithBrowserAuthorityLease(
            canonicalMessage,
            canonicalPort,
            (releaseMessage, releasePort) =>
              _cwaOnNativeMessageWithProductState(
                releaseMessage,
                releasePort,
                _cwaBaseOnNativeMessage
              )
          )
      )
  );
  );
}
