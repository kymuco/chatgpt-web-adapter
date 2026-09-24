// PR15.27 explicit runtime-tab resolution owner.
//
// Historical source-order composition was:
//
//   schema16 -> retained conversation -> Temporary -> phase timing -> base
//
// Keep that exact outer-to-inner order without import-time hook reassignment.

async function ensureRuntimeTab(conversationId) {
  return _pr92Schema16ResolveRuntimeTabWithinRichDeadline(
    conversationId,
    (richConversationId) =>
      _pr148ResolveRuntimeTab(
        richConversationId,
        (retainedConversationId) =>
          _pr813ResolveRuntimeTab(
            retainedConversationId,
            (temporaryConversationId) =>
              _pr88ResolveRuntimeTabWithPhaseTiming(
                temporaryConversationId,
                _cwaBaseEnsureRuntimeTab
              )
          )
      )
  );
}
