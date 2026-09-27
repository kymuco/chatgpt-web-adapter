// PR15.30 explicit Native Messaging router.
//
// Historical source-order composition was:
//
//   UI liveness -> canonical read v2 -> runtime-tab release -> Gemini Notebook
//   characterization -> URL-source mutation -> hosted capability -> product state -> base turn
//
// Preserve that exact outer-to-inner routing without import-time hook reassignment.

async function onNativeMessage(message, port) {
  return _cwaOnNativeMessageWithUiLiveness(
    message,
    port,
    (uiMessage, uiPort) =>
      _cwaOnNativeMessageWithCanonicalRead(
        uiMessage,
        uiPort,
        (canonicalMessage, canonicalPort) =>
          _pr88OnNativeMessageWithBrowserAuthorityLease(
            canonicalMessage,
            canonicalPort,
            (releaseMessage, releasePort) =>
              _cwaOnNativeMessageWithGeminiNotebook(
                releaseMessage,
                releasePort,
                (notebookMessage, notebookPort) =>
                  _cwaOnNativeMessageWithGeminiNotebookUrlSource(
                    notebookMessage,
                    notebookPort,
                    (notebookMutationMessage, notebookMutationPort) =>
                      _cwaOnNativeMessageWithGoogleTranslate(
                        notebookMutationMessage,
                        notebookMutationPort,
                        (capabilityMessage, capabilityPort) =>
                          _cwaOnNativeMessageWithProductState(
                            capabilityMessage,
                            capabilityPort,
                            _cwaBaseOnNativeMessage
                          )
                      )
                  )
              )
          )
      )
  );
}
