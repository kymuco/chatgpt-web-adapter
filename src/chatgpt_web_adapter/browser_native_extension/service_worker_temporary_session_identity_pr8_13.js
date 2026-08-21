// PR8.13 follow-up: recover Temporary backend routing identity from the already
// observed live SSE stream without reopening the conversation or waiting for the
// complete response body.
//
// A Temporary product conversation id is session-local routing metadata only.
// It is not a durable conversation handle and never grants continuation authority
// without the live PR8.13 lifecycle token/tab binding.

const _pr813SessionIdentityPriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr813SessionIdentityPriorExecuteOfficialPageTurn = executeOfficialPageTurn;

function _pr813SessionIdentityDirect(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const conversationId = _pr813ConversationId(
    value.conversation_id ?? value.conversationId
  );
  if (!conversationId) return null;
  const turnExchangeId = typeof (value.turn_exchange_id ?? value.turnExchangeId) === "string" &&
    (value.turn_exchange_id ?? value.turnExchangeId).trim()
    ? (value.turn_exchange_id ?? value.turnExchangeId).trim()
    : null;
  return { conversationId, turnExchangeId };
}

function _pr813SessionIdentityFromPayload(payload) {
  const direct = _pr813SessionIdentityDirect(payload);
  if (direct) return direct;

  // Bounded envelope traversal only. Do not recursively inspect arbitrary tool,
  // message, metadata, or attachment objects for conversation-shaped strings.
  for (const key of ["payload", "data", "result", "turn"]) {
    const nested = _pr813SessionIdentityDirect(payload?.[key]);
    if (nested) return nested;
  }
  return null;
}

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
  if (!payload || typeof payload !== "object") return null;
  return _pr813SessionIdentityFromPayload(payload);
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
        temporaryContext.modeViolation = "TEMPORARY_STREAM_IDENTITY_CONVERSATION_MISMATCH";
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
