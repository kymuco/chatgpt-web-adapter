// PR9.2 schema-18 post-write conversation-identity closure.
//
// Loaded after schema 17. This immutable layer closes the fresh exact-head P1
// where a completed new-chat write could still be converted into an ambiguous
// failure if optional response-body/final-tab reads timed out before the SPA
// route exposed its generated conversation id.
//
// Schema 18 preserves two separate authorities:
//   * protected write completion remains Network.requestWillBeSent +
//     Network.loadingFinished;
//   * a successful new-chat transport return additionally requires a real
//     conversation id derived from the ChatGPT /c/<id> route (or the already
//     captured schema-17 safe stream metadata).
//
// Optional schema-17 post-write diagnostics are rebound to leave a dedicated
// identity-resolution reserve. If identity still cannot be established, the
// extension returns an explicit WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED
// state; the Python provider maps that to readback-incomplete semantics rather
// than WRITE_OUTCOME_UNKNOWN. No write retry or second submit path is added.

const _pr92Schema18PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema18PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA18_REPAIR_SCHEMA = 18;
const PR92_SCHEMA18_IDENTITY_RESERVE_MS = 2_500;
const PR92_SCHEMA18_RPC_RETURN_RESERVE_MS = 500;
const PR92_SCHEMA18_IDENTITY_POLL_MS = 50;
const PR92_SCHEMA18_IDENTITY_TAB_READ_CAP_MS = 250;
const PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";

// Schema 17's optional diagnostics are intentionally non-authoritative. Leave a
// larger reserve so they can never consume the time needed to resolve the new
// conversation identity before the transport reports success.
_pr92Schema17OptionalPostWrite = async function _pr92Schema18OptionalPostWriteWithIdentityReserve(
  context,
  stage,
  operation,
  capMs = PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS
) {
  const remaining = _pr92RemainingTurnMsOrZero(context);
  const usable = remaining - PR92_SCHEMA18_IDENTITY_RESERVE_MS;
  if (!Number.isFinite(usable) || usable <= 0) {
    return { ok: false, value: null };
  }

  const localBudget = Math.max(1, Math.min(Number(capMs) || 1, usable));
  const localDeadlineAt = Math.min(
    context.deadlineAt - PR92_SCHEMA18_IDENTITY_RESERVE_MS,
    performance.now() + localBudget
  );
  try {
    const value = await _pr92Schema7RunUntil(localDeadlineAt, stage, operation);
    return { ok: true, value };
  } catch {
    return { ok: false, value: null };
  }
};

function _pr92Schema18ConversationIdentityFromUrl(url) {
  const conversationId = conversationIdFromUrl(url || "");
  return typeof conversationId === "string" && conversationId.trim()
    ? conversationId.trim()
    : null;
}

async function _pr92Schema18ResolvePostWriteConversationIdentity(
  tabId,
  initialUrl,
  context
) {
  let latestUrl = typeof initialUrl === "string" ? initialUrl : "";
  let conversationId = _pr92Schema18ConversationIdentityFromUrl(latestUrl);
  if (conversationId) return { conversationId, finalUrl: latestUrl };

  let resolveRoute;
  const routeObserved = new Promise((resolve) => {
    resolveRoute = resolve;
  });
  const routeListener = (updatedTabId, changeInfo, updatedTab) => {
    if (updatedTabId !== tabId) return;
    const candidateUrl =
      typeof changeInfo?.url === "string" && changeInfo.url
        ? changeInfo.url
        : (typeof updatedTab?.url === "string" ? updatedTab.url : "");
    const candidateId = _pr92Schema18ConversationIdentityFromUrl(candidateUrl);
    if (!candidateId) return;
    latestUrl = candidateUrl;
    resolveRoute({ conversationId: candidateId, finalUrl: candidateUrl });
  };
  chrome.tabs.onUpdated.addListener(routeListener);

  try {
    while (true) {
      const remaining = _pr92RemainingTurnMsOrZero(context);
      const usable = remaining - PR92_SCHEMA18_RPC_RETURN_RESERVE_MS;
      if (!Number.isFinite(usable) || usable <= 0) break;

      const tabReadBudget = Math.max(
        1,
        Math.min(PR92_SCHEMA18_IDENTITY_TAB_READ_CAP_MS, usable)
      );
      const tabReadDeadlineAt = Math.min(
        context.deadlineAt - PR92_SCHEMA18_RPC_RETURN_RESERVE_MS,
        performance.now() + tabReadBudget
      );
      try {
        const currentTab = await _pr92Schema7RunUntil(
          tabReadDeadlineAt,
          "SCHEMA18_POSTWRITE_CONVERSATION_ID_TAB_READ",
          () => chrome.tabs.get(tabId)
        );
        if (typeof currentTab?.url === "string" && currentTab.url) {
          latestUrl = currentTab.url;
          conversationId = _pr92Schema18ConversationIdentityFromUrl(latestUrl);
          if (conversationId) {
            return { conversationId, finalUrl: latestUrl };
          }
        }
      } catch {
        // A stalled/failed tab read has no write authority. Keep observing the
        // route until the reserved identity budget is exhausted.
      }

      const remainingAfterRead = _pr92RemainingTurnMsOrZero(context);
      const waitUsable = remainingAfterRead - PR92_SCHEMA18_RPC_RETURN_RESERVE_MS;
      if (!Number.isFinite(waitUsable) || waitUsable <= 0) break;
      const waitMs = Math.max(
        1,
        Math.min(PR92_SCHEMA18_IDENTITY_POLL_MS, waitUsable)
      );
      const observed = await Promise.race([
        routeObserved,
        new Promise((resolve) => setTimeout(() => resolve(null), waitMs))
      ]);
      if (observed?.conversationId) return observed;
    }
  } finally {
    chrome.tabs.onUpdated.removeListener(routeListener);
  }

  // The protected request is already known to have completed, so this is not an
  // unknown write outcome. Surface an explicit committed/readback-incomplete
  // state; the provider maps it without allowing any automatic retry.
  throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);
}

executeOfficialPageTurn = async function _pr92Schema18ExecuteOfficialPageTurnWithIdentityAuthority(
  args
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema18PriorExecuteOfficialPageTurn(args);

  const result = await _pr92Schema18PriorExecuteOfficialPageTurn(args);
  if (typeof result?.conversationId === "string" && result.conversationId.trim()) {
    return result;
  }

  // A missing id is only eligible for post-write identity reconciliation after
  // schema 17 has already proven the protected conversation request completed.
  if (
    result?.diagnostics?.conversationRequestSeen !== true ||
    result?.diagnostics?.loadingFinished !== true
  ) {
    throw new Error("PR9_2_CONVERSATION_ID_MISSING_WITHOUT_WRITE_COMPLETION_PROOF");
  }

  const resolved = await _pr92Schema18ResolvePostWriteConversationIdentity(
    args?.tabId,
    result?.finalUrl,
    context
  );
  return {
    ...result,
    finalUrl: resolved.finalUrl || result.finalUrl,
    conversationId: resolved.conversationId
  };
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema18Repair(message) {
  const result = await _pr92Schema18PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA18_REPAIR_SCHEMA,
    newChatConversationIdentityRequiredBeforeSuccess: true,
    postWriteConversationIdentityResolutionDeadlineBounded: true,
    postWriteConversationIdentityDedicatedReserveMs: PR92_SCHEMA18_IDENTITY_RESERVE_MS,
    missingConversationIdentityCanReturnTransportSuccess: false,
    unresolvedConversationIdentitySignalsCommittedReadbackIncomplete: true,
    automaticWriteRetryAfterIdentityFailure: false
  };
};
