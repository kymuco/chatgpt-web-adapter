// PR15.23 explicit production owner for PR8.13 Temporary product behavior.
//
// Consolidates Temporary write/lifecycle authority, live SSE session identity,
// and fresh-session identity normalization. Startup-readiness and the explicit
// Temporary native lifecycle remain separate outer layers.
//
// A Temporary conversation id is session-local routing metadata only. It never
// grants continuation authority without the live lifecycle token/tab binding.

const PR813_TEMPORARY_RUNTIME_TAB_KEY = "browserNativeTemporaryRuntimeTabIdV1";
const PR813_TEMPORARY_PROOF_TIMEOUT_MS = 10_000;
const _pr813PriorEnsureRuntimeTab = ensureRuntimeTab;
const _pr813PriorSubmitOfficialPageTurn = submitOfficialPageTurn;

let _pr813LiveTemporaryLifecycle = null;
let _pr813TemporaryTurnContext = null;

function _pr813TemporaryToken(value) {
  const token = typeof value === "string" ? value.trim() : "";
  return token || null;
}

function _pr813ConversationIdCore(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  return conversationId || null;
}

async function _pr813StoredTemporaryTabId() {
  const value = await chrome.storage.local.get(PR813_TEMPORARY_RUNTIME_TAB_KEY);
  const tabId = value?.[PR813_TEMPORARY_RUNTIME_TAB_KEY];
  return Number.isInteger(tabId) ? tabId : null;
}

async function _pr813StoreTemporaryTabId(tabId) {
  if (!Number.isInteger(tabId)) throw new Error("PR8_13_TEMPORARY_TAB_ID_REQUIRED");
  await chrome.storage.local.set({ [PR813_TEMPORARY_RUNTIME_TAB_KEY]: tabId });
}

async function _pr813ClearStoredTemporaryTabId(expectedTabId = null) {
  const stored = await _pr813StoredTemporaryTabId();
  if (expectedTabId !== null && stored !== expectedTabId) return;
  await chrome.storage.local.remove(PR813_TEMPORARY_RUNTIME_TAB_KEY);
}

async function _pr813ConfirmTemporaryTabAbsent(tabId) {
  if (!Number.isInteger(tabId)) return false;
  try {
    const tabs = await chrome.tabs.query({});
    if (!Array.isArray(tabs)) return false;
    return !tabs.some((tab) => tab?.id === tabId);
  } catch {
    return false;
  }
}

async function _pr813CloseTemporaryTab(tabId) {
  if (!Number.isInteger(tabId)) {
    return { ended: false, proof: null };
  }

  let removeSucceeded = false;
  try {
    await chrome.tabs.remove(tabId);
    removeSucceeded = true;
  } catch {
    // A remove error is ambiguous: the tab may still exist or may already be gone.
    // Only a fresh full tab observation may prove resource retirement.
  }

  if (!(await _pr813ConfirmTemporaryTabAbsent(tabId))) {
    return { ended: false, proof: null };
  }
  return {
    ended: true,
    proof: removeSucceeded
      ? "OWNED_TAB_REMOVED_AND_CONFIRMED_ABSENT"
      : "OWNED_TAB_ALREADY_ABSENT_CONFIRMED",
  };
}

async function _pr813RetireOwnedTemporaryTab() {
  const liveTabId = Number.isInteger(_pr813LiveTemporaryLifecycle?.tabId)
    ? _pr813LiveTemporaryLifecycle.tabId
    : null;
  const storedTabId = await _pr813StoredTemporaryTabId();
  const tabId = liveTabId ?? storedTabId;
  _pr813LiveTemporaryLifecycle = null;

  if (!Number.isInteger(tabId)) {
    await _pr813ClearStoredTemporaryTabId();
    return { ended: true, proof: "NO_OWNED_TAB_RECORDED" };
  }

  const retirement = await _pr813CloseTemporaryTab(tabId);
  if (retirement.ended !== true || typeof retirement.proof !== "string") {
    throw new Error(
      "PR8_13_TEMPORARY_LIFECYCLE_END_NOT_PROVEN:OWNED_TAB_ABSENCE_UNPROVEN"
    );
  }
  await _pr813ClearStoredTemporaryTabId(tabId);
  return retirement;
}

async function _pr813CreateTemporaryTab() {
  // A new Temporary lifecycle never reuses a prior CWA Temporary tab. The tab
  // id may survive a worker restart only so the next fresh lifecycle can clean
  // it up; it is never sufficient to restore write authority.
  await _pr813RetireOwnedTemporaryTab();
  const tab = await chrome.tabs.create({
    url: `${CHATGPT_ORIGIN}/?temporary-chat=true`,
    active: false,
  });
  if (!Number.isInteger(tab?.id)) throw new Error("PR8_13_TEMPORARY_TAB_CREATE_FAILED");
  await _pr813StoreTemporaryTabId(tab.id);
  return waitForTabComplete(tab.id, 45_000);
}

async function _pr813RequireLiveTemporaryTab(context) {
  const tab = await chrome.tabs.get(context.tabId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR8_13_TEMPORARY_LIFECYCLE_TAB_NOT_CHATGPT");
  }
  return tab;
}

function _pr813NewProofPromise(context) {
  if (context.proofPromise) return context.proofPromise;
  context.proofPromise = new Promise((resolve, reject) => {
    context.resolveProof = resolve;
    context.rejectProof = reject;
  });
  return context.proofPromise;
}

function _pr813RejectProof(context, error) {
  if (context.proofSettled) return;
  context.proofSettled = true;
  if (typeof context.rejectProof === "function") context.rejectProof(error);
}

function _pr813ResolveProof(context, evidence) {
  if (context.proofSettled) return;
  context.proofSettled = true;
  context.prewriteProof = evidence;
  if (typeof context.resolveProof === "function") context.resolveProof(evidence);
}

function _pr813InspectPausedConversationRequest(context, request) {
  if (!request || !isConversationWrite(request.url || "", request.method || "")) {
    return { relevant: false };
  }
  if (typeof request.postData !== "string" || !request.postData) {
    return { relevant: true, proven: false, reason: "REQUEST_POST_DATA_MISSING" };
  }

  let payload;
  try {
    payload = JSON.parse(request.postData);
  } catch {
    return { relevant: true, proven: false, reason: "REQUEST_POST_DATA_NOT_JSON" };
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { relevant: true, proven: false, reason: "REQUEST_PAYLOAD_NOT_OBJECT" };
  }
  if (payload.history_and_training_disabled !== true) {
    return {
      relevant: true,
      proven: false,
      reason: "HISTORY_AND_TRAINING_DISABLED_NOT_TRUE",
    };
  }

  const payloadConversationId = _pr813ConversationId(payload.conversation_id);
  if (context.expectedConversationId === null) {
    if (payloadConversationId !== null) {
      return {
        relevant: true,
        proven: false,
        reason: "FRESH_TEMPORARY_REQUEST_HAS_CONVERSATION_ID",
      };
    }
  } else if (payloadConversationId !== context.expectedConversationId) {
    return {
      relevant: true,
      proven: false,
      reason: "TEMPORARY_CONTINUATION_CONVERSATION_MISMATCH",
    };
  }

  return {
    relevant: true,
    proven: true,
    evidence: {
      proofKind: "FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE",
      continuationIdentityProven: context.expectedConversationId !== null,
    },
  };
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  const context = _pr813TemporaryTurnContext;
  if (context === null || method !== "Fetch.requestPaused" || source?.tabId !== context.tabId) {
    return;
  }

  const inspection = _pr813InspectPausedConversationRequest(context, params?.request);
  if (inspection.relevant !== true) {
    chrome.debugger.sendCommand(source, "Fetch.continueRequest", { requestId: params.requestId })
      .catch(() => {});
    return;
  }

  context.pausedConversationWriteCount += 1;
  if (inspection.proven !== true) {
    context.modeViolation = inspection.reason || "TEMPORARY_MODE_NOT_PROVEN";
    chrome.debugger.sendCommand(source, "Fetch.failRequest", {
      requestId: params.requestId,
      errorReason: "Aborted",
    }).catch(() => {});
    _pr813RejectProof(
      context,
      new Error(`PR8_13_TEMPORARY_PREWRITE_PROOF_FAILED:${context.modeViolation}`)
    );
    return;
  }

  chrome.debugger.sendCommand(source, "Fetch.continueRequest", { requestId: params.requestId })
    .then(() => {
      if (!context.prewriteProof) context.prewriteProof = inspection.evidence;
      _pr813ResolveProof(context, inspection.evidence);
    })
    .catch((error) => {
      _pr813RejectProof(
        context,
        new Error(`PR8_13_TEMPORARY_REQUEST_CONTINUE_FAILED:${String(error)}`)
      );
    });
});

ensureRuntimeTab = async function _pr813EnsureRuntimeTab(conversationId) {
  const context = _pr813TemporaryTurnContext;
  if (context === null) return _pr813PriorEnsureRuntimeTab(conversationId);

  const requestedConversationId = _pr813ConversationId(conversationId);
  if (requestedConversationId !== context.expectedConversationId) {
    throw new Error("PR8_13_TEMPORARY_RUNTIME_CONVERSATION_MISMATCH");
  }
  return _pr813RequireLiveTemporaryTab(context);
};

submitOfficialPageTurn = async function _pr813SubmitOfficialPageTurn(debuggee, timeoutMs) {
  const context = _pr813TemporaryTurnContext;
  if (context === null || debuggee?.tabId !== context.tabId) {
    return _pr813PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
  }

  const proofPromise = _pr813NewProofPromise(context);
  await sendCommand(debuggee, "Fetch.enable", {
    patterns: [
      {
        urlPattern: "*://chatgpt.com/backend-api/*conversation*",
        requestStage: "Request",
      },
    ],
  });

  const submit = await _pr813PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
  await Promise.race([
    proofPromise,
    new Promise((_, reject) => setTimeout(
      () => reject(new Error("PR8_13_TEMPORARY_PREWRITE_PROOF_TIMEOUT")),
      Math.min(PR813_TEMPORARY_PROOF_TIMEOUT_MS, Math.max(1000, timeoutMs))
    )),
  ]);
  if (!context.prewriteProof || context.modeViolation) {
    throw new Error(
      `PR8_13_TEMPORARY_PREWRITE_PROOF_FAILED:${context.modeViolation || "UNPROVEN"}`
    );
  }
  return submit;
};

async function _pr813EndTemporaryLifecycle(message) {
  const token = _pr813TemporaryToken(message?.temporaryLifecycleToken);
  if (!token) {
    throw new Error("PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE");
  }

  const live = _pr813LiveTemporaryLifecycle;
  if (live === null) {
    // MV3 may restart the extension service worker after a successful Temporary
    // turn. That destroys live continuation authority by design, while the
    // CWA-owned Temporary tab id may remain in chrome.storage for cleanup.
    // Explicit close is a resource-revocation operation, not continuation
    // authority: retire the owned tab if present and prove its absence before
    // declaring cleanup complete. Never recreate or accept write authority here.
    const retirement = await _pr813RetireOwnedTemporaryTab();
    return {
      conversationMode: "temporary",
      conversationId: _pr813ConversationId(message?.conversationId),
      temporaryLifecycleState: "ENDED",
      temporaryLifecycleEnded: true,
      temporaryLiveWriteAuthorityProven: false,
      temporaryLifecycleEndRecovered: true,
      temporaryLifecycleEndProof: retirement.proof,
    };
  }

  if (live.token !== token || live.state !== "LIVE") {
    // A different live lifecycle must never be closed by a stale token.
    throw new Error("PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE");
  }

  const conversationId = live.conversationId;
  const tabId = live.tabId;
  live.state = "ENDED";
  _pr813LiveTemporaryLifecycle = null;

  const retirement = await _pr813CloseTemporaryTab(tabId);
  if (retirement.ended !== true || typeof retirement.proof !== "string") {
    throw new Error(
      "PR8_13_TEMPORARY_LIFECYCLE_END_NOT_PROVEN:OWNED_TAB_ABSENCE_UNPROVEN"
    );
  }
  await _pr813ClearStoredTemporaryTabId(tabId);
  return {
    conversationMode: "temporary",
    conversationId,
    temporaryLifecycleState: "ENDED",
    temporaryLifecycleEnded: true,
    temporaryLiveWriteAuthorityProven: false,
    temporaryLifecycleEndRecovered: false,
    temporaryLifecycleEndProof: retirement.proof,
  };
}

async function _pr813ExecuteTemporaryTurn(message, next) {
  const token = _pr813TemporaryToken(message?.temporaryLifecycleToken);
  if (!token) throw new Error("PR8_13_TEMPORARY_LIFECYCLE_TOKEN_REQUIRED");

  const expectedConversationId = _pr813ConversationId(message?.conversationId);
  let tab;
  if (expectedConversationId === null) {
    tab = await _pr813CreateTemporaryTab();
    _pr813LiveTemporaryLifecycle = {
      token,
      tabId: tab.id,
      conversationId: null,
      state: "LIVE",
    };
  } else {
    const live = _pr813LiveTemporaryLifecycle;
    if (
      !live ||
      live.state !== "LIVE" ||
      live.token !== token ||
      live.conversationId !== expectedConversationId ||
      !Number.isInteger(live.tabId)
    ) {
      throw new Error("PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE");
    }
    tab = await _pr813RequireLiveTemporaryTab({ tabId: live.tabId });
  }

  const context = {
    token,
    tabId: tab.id,
    expectedConversationId,
    proofPromise: null,
    resolveProof: null,
    rejectProof: null,
    proofSettled: false,
    prewriteProof: null,
    modeViolation: null,
    pausedConversationWriteCount: 0,
  };

  if (_pr813TemporaryTurnContext !== null) {
    throw new Error("PR8_13_TEMPORARY_TURN_ALREADY_ACTIVE");
  }
  _pr813TemporaryTurnContext = context;

  let delegated = false;
  try {
    const result = await next({
      ...message,
      conversationMode: "temporary",
    });
    delegated = context.prewriteProof !== null;
    if (!delegated || context.modeViolation) {
      throw new Error("PR8_13_TEMPORARY_PREWRITE_PROOF_NOT_RETAINED");
    }

    const resolvedConversationId = _pr813ConversationId(result?.conversationId);
    if (!resolvedConversationId) throw new Error("PR8_13_TEMPORARY_CONVERSATION_ID_MISSING");
    if (expectedConversationId && resolvedConversationId !== expectedConversationId) {
      throw new Error("PR8_13_TEMPORARY_RETURN_CONVERSATION_MISMATCH");
    }

    const live = _pr813LiveTemporaryLifecycle;
    if (!live || live.token !== token || live.tabId !== tab.id || live.state !== "LIVE") {
      throw new Error("PR8_13_TEMPORARY_LIFECYCLE_LOST_AFTER_WRITE");
    }
    live.conversationId = resolvedConversationId;

    return {
      ...result,
      conversationMode: "temporary",
      temporaryModeProven: true,
      temporaryPrewriteProof: context.prewriteProof.proofKind,
      temporaryContinuationIdentityProven: (
        context.prewriteProof.continuationIdentityProven === true
      ),
      temporaryLifecycleToken: token,
      temporaryLifecycleState: "LIVE",
      temporaryLiveWriteAuthorityProven: true,
      temporaryPausedConversationWriteCount: context.pausedConversationWriteCount,
    };
  } catch (error) {
    delegated = delegated || context.prewriteProof !== null;
    const live = _pr813LiveTemporaryLifecycle;
    if (live && live.token === token) {
      // Once a Temporary request may have reached the server, conversational
      // recovery cannot recreate authority. Invalidate the lifecycle and retain
      // the owned tab only for visible inspection/next-fresh cleanup.
      live.state = "ENDED";
      _pr813LiveTemporaryLifecycle = null;
    }
    if (!delegated) {
      const retirement = await _pr813CloseTemporaryTab(tab.id);
      if (retirement.ended === true) {
        await _pr813ClearStoredTemporaryTabId(tab.id);
      }
    }
    throw error;
  } finally {
    _pr813TemporaryTurnContext = null;
  }
}

async function _pr813ExecuteNativeTurn(message, next) {
  if (message?.endTemporaryLifecycle === true) {
    return _pr813EndTemporaryLifecycle(message);
  }
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  if (mode !== "temporary") return next(message);
  return _pr813ExecuteTemporaryTurn(message, next);
};

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const live = _pr813LiveTemporaryLifecycle;
  if (live && live.tabId === tabId) {
    live.state = "ENDED";
    _pr813LiveTemporaryLifecycle = null;
  }
  const stored = await _pr813StoredTemporaryTabId();
  if (stored === tabId) await _pr813ClearStoredTemporaryTabId(tabId);
});


const PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL = "__cwa_pr813_live_temporary_identity_pending__";
function _pr813FreshIdentityFromLiveContext() {
  const active = _pr813TemporaryTurnContext;
  const activeId = _pr813ConversationIdCore(
    active?.ephemeralConversationId
  );
  if (activeId) return activeId;

  const liveId = _pr813ConversationIdCore(
    _pr813LiveTemporaryLifecycle?.conversationId
  );
  return liveId || null;
}

function _pr813ConversationId(value) {
  if (value === PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL) {
    return _pr813FreshIdentityFromLiveContext();
  }
  return _pr813ConversationIdCore(value);
};

async function _pr813ExecuteNativeTurnWithFreshIdentityFlush(message, next) {
  const mode = typeof message?.conversationMode === "string"
    ? message.conversationMode.trim().toLowerCase()
    : "normal";
  const freshTemporary = (
    mode === "temporary" &&
    _pr813ConversationIdCore(message?.conversationId) === null
  );

  if (!freshTemporary) {
    return next(message);
  }

  const result = await next({
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


const _pr813SessionIdentityUpstreamProcessSseEvent = _pr89BrowserStreamProcessSseEvent;

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

async function _pr813ProcessSseWithTemporarySessionIdentity(context, block) {
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

  return _pr813SessionIdentityUpstreamProcessSseEvent(context, block);
}

async function _pr813ExecuteOfficialPageTurnWithSessionIdentity(args, next) {
  const result = await next(args);
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

_pr89BrowserStreamProcessSseEvent = _pr813ProcessSseWithTemporarySessionIdentity;
