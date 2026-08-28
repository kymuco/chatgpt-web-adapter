// PR9.2 schema-19 request-bound conversation-identity closure.
//
// Loaded after schema 18. The schema-18 route reconciliation was still able to
// accept an unrelated /c/<id> if the persistent runtime tab was manually
// navigated during the post-write window. Schema 19 removes route state from
// new-chat identity authority entirely.
//
// For a rich new-chat write, the only accepted conversation id is the
// `stream_handoff.conversation_id` parsed from Network.getResponseBody for the
// exact requestId whose Network.requestWillBeSent + Network.loadingFinished
// already proved the protected conversation POST and its completion. A route
// may remain diagnostic UI state, but it can neither satisfy nor override the
// request-bound identity. If the causal stream metadata is unavailable before
// the outer deadline, the existing committed/readback-incomplete marker is
// returned and automatic write retry remains forbidden.

const _pr92Schema19PriorCreateTurnContext = _pr92CreateTurnContext;
const _pr92Schema19PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;
const _pr92Schema19PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema19PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema19PriorOptionalPostWrite = _pr92Schema17OptionalPostWrite;
const PR92_SCHEMA19_REPAIR_SCHEMA = 19;
const PR92_SCHEMA19_CAUSAL_RESPONSE_BODY_CAP_MS = 2_000;
const PR92_SCHEMA19_RPC_RETURN_RESERVE_MS = 500;
const PR92_SCHEMA19_IDENTITY_AUTHORITY = "NETWORK_REQUEST_BOUND_STREAM_HANDOFF";

_pr92CreateTurnContext = function _pr92Schema19CreateTurnContext(message) {
  const context = _pr92Schema19PriorCreateTurnContext(message);
  const requestedConversationId =
    typeof message?.conversationId === "string" && message.conversationId.trim()
      ? message.conversationId.trim()
      : null;
  context.schema19RequestedConversationId = requestedConversationId;
  context.schema19CausalConversationId = null;
  context.schema19CausalTurnExchangeId = null;
  return context;
};

extractSafeStreamMetadata = function _pr92Schema19ExtractRequestBoundStreamMetadata(
  body,
  base64Encoded
) {
  const metadata = _pr92Schema19PriorExtractSafeStreamMetadata(body, base64Encoded);
  const context = _pr92ActiveRichInputContext;
  if (context !== null) {
    if (typeof metadata?.conversationId === "string" && metadata.conversationId.trim()) {
      context.schema19CausalConversationId = metadata.conversationId.trim();
    }
    if (typeof metadata?.turnExchangeId === "string" && metadata.turnExchangeId.trim()) {
      context.schema19CausalTurnExchangeId = metadata.turnExchangeId.trim();
    }
  }
  return metadata;
};

// For a new chat, response-body metadata is no longer optional identity
// decoration: it is the sole causal identity source. Give that exact-request
// read the schema-18 identity reserve while preserving the final 500 ms for the
// Native Messaging RPC return. Other post-write diagnostics keep schema-18's
// stricter optional/non-authoritative budget.
_pr92Schema17OptionalPostWrite = async function _pr92Schema19OptionalPostWrite(
  context,
  stage,
  operation,
  capMs = PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS
) {
  const isNewChatCausalIdentityRead =
    stage === "SCHEMA17_POSTWRITE_RESPONSE_BODY" &&
    context?.schema19RequestedConversationId == null;
  if (!isNewChatCausalIdentityRead) {
    return _pr92Schema19PriorOptionalPostWrite(context, stage, operation, capMs);
  }

  const remaining = _pr92RemainingTurnMsOrZero(context);
  const usable = remaining - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS;
  if (!Number.isFinite(usable) || usable <= 0) {
    return { ok: false, value: null };
  }

  const localBudget = Math.max(
    1,
    Math.min(PR92_SCHEMA19_CAUSAL_RESPONSE_BODY_CAP_MS, usable)
  );
  const localDeadlineAt = Math.min(
    context.deadlineAt - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS,
    performance.now() + localBudget
  );
  try {
    const value = await _pr92Schema7RunUntil(localDeadlineAt, stage, operation);
    return { ok: true, value };
  } catch {
    return { ok: false, value: null };
  }
};

function _pr92Schema19CanonicalConversationUrl(conversationId) {
  return `${CHATGPT_ORIGIN}/c/${encodeURIComponent(conversationId)}`;
}

executeOfficialPageTurn = async function _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity(
  args
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema19PriorExecuteOfficialPageTurn(args);

  // Continuations already carry an explicit conversation identity before the
  // write and retain the complete schema-18 path. Schema 19 changes only the
  // missing-identity/new-chat case addressed by the exact-head review finding.
  if (context.schema19RequestedConversationId !== null) {
    return _pr92Schema19PriorExecuteOfficialPageTurn(args);
  }

  // Bypass schema 18's route-based fallback while retaining schema 17's exact
  // request tracking, completion proof, bounded response-body read, attachment
  // authority, and protected-submit invariants.
  const result = await _pr92Schema18PriorExecuteOfficialPageTurn(args);
  if (
    result?.diagnostics?.conversationRequestSeen !== true ||
    result?.diagnostics?.loadingFinished !== true
  ) {
    throw new Error("PR9_2_CONVERSATION_ID_MISSING_WITHOUT_WRITE_COMPLETION_PROOF");
  }

  const causalConversationId =
    typeof context.schema19CausalConversationId === "string" &&
    context.schema19CausalConversationId.trim()
      ? context.schema19CausalConversationId.trim()
      : null;
  if (!causalConversationId) {
    throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);
  }

  const routeConversationId = conversationIdFromUrl(result?.finalUrl || "");
  const causalTurnExchangeId =
    typeof context.schema19CausalTurnExchangeId === "string" &&
    context.schema19CausalTurnExchangeId.trim()
      ? context.schema19CausalTurnExchangeId.trim()
      : null;

  return {
    ...result,
    finalUrl:
      routeConversationId === causalConversationId
        ? result.finalUrl
        : _pr92Schema19CanonicalConversationUrl(causalConversationId),
    conversationId: causalConversationId,
    turnExchangeId: causalTurnExchangeId || result?.turnExchangeId || null,
    diagnostics: {
      ...result.diagnostics,
      conversationIdentityAuthority: PR92_SCHEMA19_IDENTITY_AUTHORITY,
      routeConversationIdentityAuthoritative: false,
      routeConversationId: routeConversationId || null,
      causalConversationId
    }
  };
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema19Repair(message) {
  const result = await _pr92Schema19PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA19_REPAIR_SCHEMA,
    newChatConversationIdentityAuthority: PR92_SCHEMA19_IDENTITY_AUTHORITY,
    responseBodyConversationIdentityRequestBound: true,
    routeConversationIdentityAuthoritative: false,
    manualRouteNavigationCanSatisfyNewChatIdentity: false,
    causalConversationIdentityReadDeadlineBounded: true,
    causalConversationIdentityRpcReturnReserveMs: PR92_SCHEMA19_RPC_RETURN_RESERVE_MS,
    missingRequestBoundConversationIdentitySignalsCommittedReadbackIncomplete: true,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};
