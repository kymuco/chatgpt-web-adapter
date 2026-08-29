// PR9.2 schema-28 request-bound stream-handoff parser repair.
//
// Authenticated schema-27 validation proved the protected image write completed and
// ChatGPT produced the attachment-dependent answer, but the turn failed with
// PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED. The inherited base parser
// prefiltered SSE payload text with the serialization-specific substring
// `"type":"stream_handoff"` before JSON.parse and rejected every base64Encoded
// response body. Current ChatGPT emits valid stream-handoff JSON with ordinary
// whitespace (for example `"type": "stream_handoff"`), so exact-request identity
// could be present while the parser returned null.
//
// Schema 28 changes no identity source. New-chat identity remains exclusively the
// stream_handoff.conversation_id parsed from Network.getResponseBody for the exact
// protected requestId already proven by requestWillBeSent + loadingFinished. Route
// state remains diagnostic only. The repair parses JSON before inspecting `type`,
// decodes CDP base64 response-body representation as UTF-8, and fails closed if
// multiple stream_handoff records disagree on conversation identity.

const _pr92Schema28PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA28_REPAIR_SCHEMA = 28;
const PR92_SCHEMA28_COMMITTED_IDENTITY_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";

let _pr92Schema28LastIdentityParseDiagnostics = null;

function _pr92Schema28DecodeResponseBody(body, base64Encoded) {
  if (typeof body !== "string") return null;
  if (base64Encoded !== true) return body;
  try {
    const binary = atob(body);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  } catch {
    return null;
  }
}

function _pr92Schema28ExtractRequestBoundStreamMetadata(body, base64Encoded) {
  const decoded = _pr92Schema28DecodeResponseBody(body, base64Encoded);
  const diagnostics = {
    bodyDecoded: typeof decoded === "string",
    base64Encoded: base64Encoded === true,
    parsedJsonDataRecords: 0,
    streamHandoffCount: 0,
    conflictingConversationIds: false
  };
  if (typeof decoded !== "string") {
    return {
      conversationId: null,
      turnExchangeId: null,
      diagnostics
    };
  }

  let conversationId = null;
  let turnExchangeId = null;
  for (const rawLine of decoded.split(/\r?\n/)) {
    if (!rawLine.startsWith("data:")) continue;
    const payloadText = rawLine.slice(5).trim();
    if (!payloadText || payloadText === "[DONE]" || !payloadText.startsWith("{")) {
      continue;
    }

    let payload;
    try {
      payload = JSON.parse(payloadText);
      diagnostics.parsedJsonDataRecords += 1;
    } catch {
      continue;
    }
    if (payload?.type !== "stream_handoff") continue;
    diagnostics.streamHandoffCount += 1;

    const candidateConversationId =
      typeof payload?.conversation_id === "string" && payload.conversation_id.trim()
        ? payload.conversation_id.trim()
        : null;
    if (!candidateConversationId) continue;

    if (conversationId !== null && conversationId !== candidateConversationId) {
      diagnostics.conflictingConversationIds = true;
      conversationId = null;
      turnExchangeId = null;
      break;
    }
    conversationId = candidateConversationId;

    const candidateTurnExchangeId =
      typeof payload?.turn_exchange_id === "string" && payload.turn_exchange_id.trim()
        ? payload.turn_exchange_id.trim()
        : null;
    if (candidateTurnExchangeId) turnExchangeId = candidateTurnExchangeId;
  }

  return {
    conversationId: diagnostics.conflictingConversationIds ? null : conversationId,
    turnExchangeId: diagnostics.conflictingConversationIds ? null : turnExchangeId,
    diagnostics
  };
}

extractSafeStreamMetadata = function _pr92Schema28ExtractSafeStreamMetadata(
  body,
  base64Encoded
) {
  const parsed = _pr92Schema28ExtractRequestBoundStreamMetadata(body, base64Encoded);
  _pr92Schema28LastIdentityParseDiagnostics = { ...parsed.diagnostics };

  // Schema 19 consumes these context fields after schema 17 has read the body for
  // the exact completed requestId. Preserve that same request-bound handoff and do
  // not consult route/tab state here.
  const context = _pr92ActiveRichInputContext;
  if (context !== null) {
    context.schema19CausalConversationId =
      typeof parsed.conversationId === "string" && parsed.conversationId
        ? parsed.conversationId
        : null;
    context.schema19CausalTurnExchangeId =
      typeof parsed.turnExchangeId === "string" && parsed.turnExchangeId
        ? parsed.turnExchangeId
        : null;
  }

  return {
    conversationId: parsed.conversationId,
    turnExchangeId: parsed.turnExchangeId
  };
};

async function _pr92Schema28ReadDiagnosticTab(tabId, context) {
  if (!Number.isInteger(tabId)) return null;
  try {
    const tab = await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_TAB_READ",
      () => chrome.tabs.get(tabId)
    );
    return {
      tabId,
      url: typeof tab?.url === "string" ? tab.url : null,
      routeConversationId: conversationIdFromUrl(tab?.url || "") || null
    };
  } catch {
    return { tabId, url: null, routeConversationId: null };
  }
}

async function _pr92Schema28CommittedIdentityDiagnostic(message) {
  if (message?.text != null || message?.attachmentPaths != null) {
    throw new Error("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_WRITE_INPUT_FORBIDDEN");
  }
  if (_pr92ActiveTurnContext !== null || _pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_TURN_CONTEXT_BUSY");
  }

  const context = _pr92CreateTurnContext(message);
  _pr92ActiveTurnContext = context;
  try {
    const fenceBefore = await _pr92ReadDirtyAttachmentFence();
    let runtimeTabId = null;
    if (Number.isInteger(fenceBefore)) {
      runtimeTabId = fenceBefore;
    } else {
      try {
        runtimeTabId = await _pr92Schema7RunUntil(
          context.deadlineAt,
          "SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_RUNTIME_TAB_ID",
          () => storedRuntimeTabId()
        );
      } catch {
        runtimeTabId = null;
      }
    }

    const tabBeforeCleanup = await _pr92Schema28ReadDiagnosticTab(runtimeTabId, context);
    let cleanupAttempted = false;
    if (Number.isInteger(fenceBefore)) {
      cleanupAttempted = true;
      await _pr92RequireCleanAttachmentState(context);
    }

    const fenceAfter = await _pr92ReadDirtyAttachmentFence();
    if (Number.isInteger(fenceAfter)) {
      throw new Error("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_FENCE_REMAINS");
    }

    let fencedTabAbsentAfterCleanup = null;
    if (Number.isInteger(fenceBefore)) {
      try {
        await _pr92Schema7RunUntil(
          context.deadlineAt,
          "SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_TAB_ABSENCE",
          () => chrome.tabs.get(fenceBefore)
        );
        fencedTabAbsentAfterCleanup = false;
      } catch {
        fencedTabAbsentAfterCleanup = true;
      }
      if (fencedTabAbsentAfterCleanup !== true) {
        throw new Error("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_TAB_STILL_PRESENT");
      }
    }

    return {
      diagnosticOnly: true,
      reconciliationOnly: true,
      writePerformed: false,
      conversationWritePerformed: false,
      attachmentStagingPerformed: false,
      textInsertionPerformed: false,
      protectedSubmitAttempted: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      richInputSchemaVersion: PR92_SCHEMA28_REPAIR_SCHEMA,
      durableFencePresentBefore: Number.isInteger(fenceBefore),
      cleanupAttempted,
      cleanupProven: !Number.isInteger(fenceAfter),
      durableFenceCleared: !Number.isInteger(fenceAfter),
      fencedTabAbsentAfterCleanup,
      observedTabIdBeforeCleanup: tabBeforeCleanup?.tabId ?? null,
      observedRouteConversationIdDiagnostic:
        tabBeforeCleanup?.routeConversationId ?? null,
      observedUrlBeforeCleanup: tabBeforeCleanup?.url ?? null,
      routeConversationIdentityAuthoritative: false
    };
  } finally {
    _pr92ActiveTurnContext = null;
  }
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema28Repair(message) {
  if (message?.diagnosePr92CommittedIdentityStateSchema28 === true) {
    return _pr92Schema28CommittedIdentityDiagnostic(message);
  }

  const isPotentialNewChatRichWrite =
    Array.isArray(message?.attachmentPaths) &&
    message.attachmentPaths.length > 0 &&
    !(typeof message?.conversationId === "string" && message.conversationId.trim());
  if (isPotentialNewChatRichWrite) {
    _pr92Schema28LastIdentityParseDiagnostics = null;
  }

  let result;
  try {
    result = await _pr92Schema28PriorExecuteNativeTurn(message);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (detail.startsWith(PR92_SCHEMA28_COMMITTED_IDENTITY_ERROR)) {
      const diagnostics = _pr92Schema28LastIdentityParseDiagnostics;
      const suffix = diagnostics
        ? `:SCHEMA28:bodyDecoded=${diagnostics.bodyDecoded === true}` +
          `:base64Encoded=${diagnostics.base64Encoded === true}` +
          `:parsedJsonDataRecords=${Number(diagnostics.parsedJsonDataRecords) || 0}` +
          `:streamHandoffCount=${Number(diagnostics.streamHandoffCount) || 0}` +
          `:conflictingConversationIds=${diagnostics.conflictingConversationIds === true}`
        : ":SCHEMA28:identityParserNotReached=true";
      throw new Error(`${PR92_SCHEMA28_COMMITTED_IDENTITY_ERROR}${suffix}`);
    }
    throw error;
  }

  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA28_REPAIR_SCHEMA,
    causalStreamHandoffJsonParsedBeforeTypeFilter: true,
    causalStreamHandoffJsonWhitespaceInvariant: true,
    causalStreamHandoffBase64BodyDecodingSupported: true,
    conflictingStreamHandoffConversationIdsFailClosed: true,
    routeConversationIdentityAuthoritative: false,
    automaticWriteRetryAfterCausalIdentityFailure: false
  };
};