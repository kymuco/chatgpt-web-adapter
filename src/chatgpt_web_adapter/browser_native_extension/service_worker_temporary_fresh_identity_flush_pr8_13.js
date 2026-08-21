// PR8.13 live repair: allow the established PR8.9 streaming reducer to finish
// processing a fresh Temporary response before the legacy ordinary-chat native
// turn boundary insists on a conversation id.
//
// The sentinel below is extension-local only. It is never written into the
// page-generated product request. For a fresh Temporary turn, the PR8.13
// conversation-id normalizer treats it as "not yet known" until the live SSE
// reducer has observed the real session-local routing identity. If the real
// identity is still unavailable after the stream reducer flushes, PR8.13 still
// fails closed.

const PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL = "__cwa_pr813_live_temporary_identity_pending__";
const _pr813FreshIdentityPriorConversationId = _pr813ConversationId;
const _pr813FreshIdentityPriorExecuteNativeTurn = executeNativeTurn;

function _pr813FreshIdentityFromLiveContext() {
  const active = _pr813TemporaryTurnContext;
  const activeId = _pr813FreshIdentityPriorConversationId(
    active?.ephemeralConversationId
  );
  if (activeId) return activeId;

  const liveId = _pr813FreshIdentityPriorConversationId(
    _pr813LiveTemporaryLifecycle?.conversationId
  );
  return liveId || null;
}

_pr813ConversationId = function _pr813ConversationIdWithFreshIdentitySentinel(value) {
  if (value === PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL) {
    return _pr813FreshIdentityFromLiveContext();
  }
  return _pr813FreshIdentityPriorConversationId(value);
};

executeNativeTurn = async function _pr813ExecuteNativeTurnWithFreshIdentityFlush(message) {
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  const freshTemporary = (
    mode === "temporary" &&
    _pr813FreshIdentityPriorConversationId(message?.conversationId) === null
  );

  if (!freshTemporary) {
    return _pr813FreshIdentityPriorExecuteNativeTurn(message);
  }

  const result = await _pr813FreshIdentityPriorExecuteNativeTurn({
    ...message,
    // This satisfies only the legacy base native-turn identity assertion. The
    // PR8.13 ensureRuntimeTab/prewrite layers normalize this sentinel back to
    // null, so the page still performs a true fresh Temporary write with no
    // conversation_id in its request payload.
    conversationId: PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL,
  });

  if (!result || typeof result !== "object") return result;
  if (result.conversationId !== PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL) {
    return result;
  }

  const resolvedConversationId = _pr813FreshIdentityFromLiveContext();
  if (!resolvedConversationId) {
    throw new Error("PR8_13_TEMPORARY_SESSION_ROUTING_IDENTITY_MISSING_AFTER_STREAM_FLUSH");
  }

  return {
    ...result,
    conversationId: resolvedConversationId,
    temporarySessionRoutingIdentitySource: "LIVE_SSE_STREAM",
  };
};
