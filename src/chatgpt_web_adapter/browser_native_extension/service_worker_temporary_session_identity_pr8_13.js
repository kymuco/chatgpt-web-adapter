// PR8.13 follow-up: recover Temporary backend routing identity from the already
// observed live SSE stream without reopening the conversation or waiting for the
// complete response body.
//
// A Temporary product conversation id is session-local routing metadata only.
// It is not a durable conversation handle and never grants continuation authority
// without the live PR8.13 lifecycle token/tab binding.

const _pr813SessionIdentityPriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr813SessionIdentityPriorExecuteOfficialPageTurn = executeOfficialPageTurn;

function _pr813SessionIdentityFromSseBlock(block) {
  const lines = String(block || "").split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;

  const data = dataLines.join("\n").trim();
  if (!data || data === "[DONE]") return null;

  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return null;
  }
  if (!payload || payload.type !== "stream_handoff") return null;

  const conversationId = _pr813ConversationId(payload.conversation_id);
  if (!conversationId) return null;
  const turnExchangeId = typeof payload.turn_exchange_id === "string" && payload.turn_exchange_id.trim()
    ? payload.turn_exchange_id.trim()
    : null;
  return { conversationId, turnExchangeId };
}

_pr89BrowserStreamProcessSseEvent = async function _pr813ProcessSseWithTemporarySessionIdentity(
  context,
  block
) {
  const temporaryContext = _pr813TemporaryTurnContext;
  if (temporaryContext !== null) {
    const identity = _pr813SessionIdentityFromSseBlock(block);
    if (identity !== null) {
      if (
        temporaryContext.expectedConversationId !== null &&
        identity.conversationId !== temporaryContext.expectedConversationId
      ) {
        temporaryContext.modeViolation = "TEMPORARY_STREAM_HANDOFF_CONVERSATION_MISMATCH";
      } else {
        temporaryContext.ephemeralConversationId = identity.conversationId;
        if (identity.turnExchangeId) {
          temporaryContext.ephemeralTurnExchangeId = identity.turnExchangeId;
        }
      }
    }
  }

  return _pr813SessionIdentityPriorProcessSseEvent(context, block);
};

executeOfficialPageTurn = async function _pr813ExecuteOfficialPageTurnWithSessionIdentity(args) {
  const result = await _pr813SessionIdentityPriorExecuteOfficialPageTurn(args);
  const temporaryContext = _pr813TemporaryTurnContext;
  if (temporaryContext === null || !result || typeof result !== "object") return result;

  const conversationId = _pr813ConversationId(result.conversationId)
    || _pr813ConversationId(temporaryContext.ephemeralConversationId);
  const turnExchangeId = (
    typeof result.turnExchangeId === "string" && result.turnExchangeId.trim()
      ? result.turnExchangeId.trim()
      : typeof temporaryContext.ephemeralTurnExchangeId === "string" &&
        temporaryContext.ephemeralTurnExchangeId.trim()
        ? temporaryContext.ephemeralTurnExchangeId.trim()
        : null
  );

  return {
    ...result,
    conversationId,
    turnExchangeId,
  };
};
