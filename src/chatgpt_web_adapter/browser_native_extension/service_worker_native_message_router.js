// PR15.30 explicit Native Messaging router.
//
// Historical source-order composition was:
//
//   UI liveness -> canonical read v2 -> runtime-tab release -> product state -> base turn
//
// PR17.0 adds one temporary non-chat capability wrapper outside that historical
// chat-specific chain. Preserve the existing inner ordering unchanged.

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
      )
  );
}
