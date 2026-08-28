// PR9.2 schema-17 complete page-turn deadline closure.
//
// Loaded after schema 16. This immutable layer closes the two fresh exact-head
// review findings without changing text-only behavior or write authority:
//   1. every pre-submit page-turn setup operation is raced against the same
//      outer rich-turn deadline, including late debugger-attach ownership;
//   2. after Network.loadingFinished proves the protected request completed,
//      response metadata, UI readiness, and final-tab refresh are optional,
//      short-budget diagnostics which cannot consume the RPC deadline or rewrite
//      the already-submitted outcome.

const _pr92Schema17PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema17PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA17_REPAIR_SCHEMA = 17;
const PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS = 1_000;
const PR92_SCHEMA17_RPC_RETURN_RESERVE_MS = 500;

function _pr92Schema17BestEffortDetach(debuggee) {
  try {
    const pending = chrome.debugger.detach(debuggee);
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

async function _pr92Schema17AttachWithinDeadline(debuggee, context) {
  _pr92RemainingTurnMs(context, "SCHEMA17_PAGE_TURN_DEBUGGER_ATTACH");
  let attachPending;
  try {
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
  } catch (error) {
    throw error;
  }
  if (attachPending && typeof attachPending.catch === "function") {
    attachPending.catch(() => {});
  }

  try {
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA17_PAGE_TURN_DEBUGGER_ATTACH",
      () => attachPending
    );
    return true;
  } catch (error) {
    // chrome.debugger.attach is non-cancellable. If it succeeds only after the
    // local deadline has already won, relinquish ownership best-effort without
    // extending or changing the reported timeout outcome.
    if (attachPending && typeof attachPending.then === "function") {
      attachPending.then(
        () => _pr92Schema17BestEffortDetach(debuggee),
        () => {}
      );
    }
    throw error;
  }
}

async function _pr92Schema17RunUntil(context, stage, operation) {
  _pr92RemainingTurnMs(context, stage);
  return _pr92Schema7RunUntil(context.deadlineAt, stage, operation);
}

async function _pr92Schema17OptionalPostWrite(
  context,
  stage,
  operation,
  capMs = PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS
) {
  const remaining = _pr92RemainingTurnMsOrZero(context);
  const usable = remaining - PR92_SCHEMA17_RPC_RETURN_RESERVE_MS;
  if (!Number.isFinite(usable) || usable <= 0) {
    return { ok: false, value: null };
  }

  const localBudget = Math.max(1, Math.min(Number(capMs) || 1, usable));
  const localDeadlineAt = Math.min(
    context.deadlineAt - PR92_SCHEMA17_RPC_RETURN_RESERVE_MS,
    performance.now() + localBudget
  );
  try {
    const value = await _pr92Schema7RunUntil(localDeadlineAt, stage, operation);
    return { ok: true, value };
  } catch {
    // Optional post-write work has no authority over the submitted result.
    return { ok: false, value: null };
  }
}

async function _pr92Schema17ExecuteOfficialPageTurn({ tabId, text, timeoutMs }) {
  if (!Number.isInteger(tabId)) throw new Error("TAB_ID_REQUIRED");
  if (typeof text !== "string" || !text.trim()) throw new Error("TEXT_REQUIRED");
  if (text.length > 200_000) throw new Error("TEXT_TOO_LARGE_FOR_BROWSER_NATIVE_TURN");

  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92Schema17PriorExecuteOfficialPageTurn({ tabId, text, timeoutMs });
  }

  const startedAt = performance.now();
  const debuggee = { tabId };
  const tab = await _pr92Schema17RunUntil(
    context,
    "SCHEMA17_PAGE_TURN_TAB_LOOKUP",
    () => chrome.tabs.get(tabId)
  );
  if (!isChatGPTUrl(tab?.url || "")) throw new Error("RUNTIME_TAB_IS_NOT_CHATGPT");

  let latestUrl = tab.url || "";
  const diagnostics = {
    tabId,
    tabWasActive: Boolean(tab.active),
    composerStrategy: null,
    submitStrategy: null,
    submitButtonSelector: null,
    submitAckMs: null,
    responseStatus: null,
    responseMimeType: null,
    conversationRequestSeen: false,
    conversationResponseSeen: false,
    loadingFinished: false,
    completionReadyWaitMs: null,
    debuggerAttachedAfter: null,
    elapsedMs: null
  };

  let attached = false;
  let eventListener = null;
  let tabUpdateListener = null;
  try {
    attached = await _pr92Schema17AttachWithinDeadline(debuggee, context);

    await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_NETWORK_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Network.enable")
    );
    await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    const readyBudget = Math.min(
      _pr92RemainingTurnMs(context, "SCHEMA17_PAGE_TURN_COMPOSER_READY"),
      DEFAULT_READY_TIMEOUT_MS
    );
    await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_COMPOSER_READY",
      () => waitForComposerReady(debuggee, readyBudget)
    );

    let conversationRequestId = null;
    let resolveRequestSeen;
    let resolveCompleted;
    let rejectCompleted;
    const requestSeen = new Promise((resolve) => {
      resolveRequestSeen = resolve;
    });
    const completed = new Promise((resolve, reject) => {
      resolveCompleted = resolve;
      rejectCompleted = reject;
    });

    eventListener = (source, method, params) => {
      if (source.tabId !== tabId) return;
      if (method === "Network.requestWillBeSent") {
        const request = params?.request;
        if (!conversationRequestId && isConversationWrite(request?.url || "", request?.method || "")) {
          conversationRequestId = params.requestId;
          diagnostics.conversationRequestSeen = true;
          resolveRequestSeen(params.requestId);
        }
        return;
      }
      if (!conversationRequestId || params?.requestId !== conversationRequestId) return;
      if (method === "Network.responseReceived") {
        diagnostics.conversationResponseSeen = true;
        diagnostics.responseStatus = params?.response?.status ?? null;
        diagnostics.responseMimeType = params?.response?.mimeType ?? null;
        return;
      }
      if (method === "Network.loadingFailed") {
        rejectCompleted(new Error(`CHATGPT_CONVERSATION_REQUEST_FAILED:${params?.errorText || "unknown"}`));
        return;
      }
      if (method === "Network.loadingFinished") {
        diagnostics.loadingFinished = true;
        resolveCompleted(conversationRequestId);
      }
    };
    chrome.debugger.onEvent.addListener(eventListener);

    // Track route changes synchronously while the request is live. This removes
    // final chrome.tabs.get from conversation-id authority on the success path;
    // the later final-tab read is only an optional bounded refresh.
    tabUpdateListener = (updatedTabId, changeInfo, updatedTab) => {
      if (updatedTabId !== tabId) return;
      if (typeof changeInfo?.url === "string" && changeInfo.url) {
        latestUrl = changeInfo.url;
      } else if (typeof updatedTab?.url === "string" && updatedTab.url) {
        latestUrl = updatedTab.url;
      }
    };
    chrome.tabs.onUpdated.addListener(tabUpdateListener);

    diagnostics.composerStrategy = await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_COMPOSER_FOCUS",
      () => locateAndFocusComposer(debuggee)
    );
    await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_COMPOSER_CLEAR",
      () => clearComposer(debuggee)
    );
    await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_PAGE_TURN_TEXT_INSERT",
      () => chrome.debugger.sendCommand(debuggee, "Input.insertText", { text })
    );

    const submitStartedAt = performance.now();
    const submit = await submitOfficialPageTurn(
      debuggee,
      Math.min(
        _pr92RemainingTurnMs(context, "SCHEMA17_PROTECTED_SUBMIT"),
        Number.isFinite(timeoutMs) ? Math.max(1, Number(timeoutMs)) : DEFAULT_SUBMIT_READY_TIMEOUT_MS,
        DEFAULT_SUBMIT_READY_TIMEOUT_MS
      )
    );
    diagnostics.submitStrategy = submit.strategy;
    diagnostics.submitButtonSelector = submit.selector;

    const submitAckBudget = Math.min(
      _pr92RemainingTurnMs(context, "SCHEMA17_SUBMIT_OBSERVATION"),
      DEFAULT_SUBMIT_ACK_TIMEOUT_MS
    );
    await Promise.race([
      requestSeen,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error(`CHATGPT_SUBMIT_NOT_OBSERVED:${submit.strategy}`)),
        submitAckBudget
      ))
    ]);
    diagnostics.submitAckMs = elapsedMs(submitStartedAt);

    const requestId = await _pr92Schema17RunUntil(
      context,
      "SCHEMA17_CONVERSATION_REQUEST_COMPLETION",
      () => completed
    );

    // The protected request is complete. Everything below is optional metadata
    // or UI diagnostics. Each operation gets at most a short local budget and is
    // skipped before the reserved RPC-return window. None may throw into success.
    let safeMetadata = { conversationId: null, turnExchangeId: null };
    const responseBodyAttempt = _pr92Schema17OptionalPostWrite(
      context,
      "SCHEMA17_POSTWRITE_RESPONSE_BODY",
      () => chrome.debugger.sendCommand(debuggee, "Network.getResponseBody", { requestId })
    );
    const finalTabAttempt = _pr92Schema17OptionalPostWrite(
      context,
      "SCHEMA17_POSTWRITE_FINAL_TAB",
      () => chrome.tabs.get(tabId),
      500
    );
    const [responseBodyResult, finalTabResult] = await Promise.all([
      responseBodyAttempt,
      finalTabAttempt
    ]);

    if (responseBodyResult.ok === true) {
      const response = responseBodyResult.value;
      safeMetadata = extractSafeStreamMetadata(
        response?.body,
        Boolean(response?.base64Encoded)
      );
    }
    if (finalTabResult.ok === true && typeof finalTabResult.value?.url === "string") {
      latestUrl = finalTabResult.value.url || latestUrl;
    }

    const readinessBudget = Math.min(
      Math.max(1, _pr92RemainingTurnMsOrZero(context) - PR92_SCHEMA17_RPC_RETURN_RESERVE_MS),
      PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS,
      DEFAULT_READY_TIMEOUT_MS
    );
    if (_pr92RemainingTurnMsOrZero(context) > PR92_SCHEMA17_RPC_RETURN_RESERVE_MS) {
      const readinessResult = await _pr92Schema17OptionalPostWrite(
        context,
        "SCHEMA17_POSTWRITE_COMPOSER_READINESS",
        () => waitForComposerReady(debuggee, readinessBudget)
      );
      if (readinessResult.ok === true) {
        diagnostics.completionReadyWaitMs = readinessResult.value;
      }
    }

    const urlConversationId = conversationIdFromUrl(latestUrl);
    diagnostics.elapsedMs = elapsedMs(startedAt);
    return {
      diagnostics,
      finalUrl: latestUrl,
      conversationId: safeMetadata.conversationId || urlConversationId,
      turnExchangeId: safeMetadata.turnExchangeId
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (tabUpdateListener) chrome.tabs.onUpdated.removeListener(tabUpdateListener);

    if (diagnostics.conversationRequestSeen === true) {
      // Post-write debugger teardown remains schema-16 best-effort authority.
      if (attached) _pr92Schema16DispatchPostWriteDebuggerTeardown(debuggee);
      diagnostics.debuggerAttachedAfter = null;
    } else {
      if (attached) {
        try {
          await _pr92Schema17RunUntil(
            context,
            "SCHEMA17_PREWRITE_PAGE_TURN_DEBUGGER_DETACH",
            () => chrome.debugger.detach(debuggee)
          );
          attached = false;
        } catch {
          _pr92Schema17BestEffortDetach(debuggee);
        }
      }
      try {
        const targets = await _pr92Schema17RunUntil(
          context,
          "SCHEMA17_PREWRITE_PAGE_TURN_DEBUGGER_TARGETS",
          () => chrome.debugger.getTargets()
        );
        diagnostics.debuggerAttachedAfter = Boolean(
          targets.find((target) => target.tabId === tabId)?.attached
        );
      } catch {
        diagnostics.debuggerAttachedAfter = null;
      }
    }
  }
}

executeOfficialPageTurn = async function _pr92Schema17ExecuteOfficialPageTurnWithinTurn(args) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema17PriorExecuteOfficialPageTurn(args);
  const outerContext = _pr92ActiveTurnContext;
  if (outerContext === null) {
    throw new Error("PR9_2_RICH_INPUT_TURN_CONTEXT_REQUIRED");
  }
  return _pr92Schema17ExecuteOfficialPageTurn({
    ...args,
    timeoutMs: _pr92CapTimeoutToTurn(
      outerContext,
      args?.timeoutMs,
      "SCHEMA17_PROTECTED_PAGE_DISPATCH"
    )
  });
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema17Repair(message) {
  const result = await _pr92Schema17PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA17_REPAIR_SCHEMA,
    pageTurnPrewriteSetupDeadlineBounded: true,
    latePageTurnDebuggerAttachAutoDetached: true,
    postWriteResponseBodyDeadlineBounded: true,
    postWriteComposerReadinessDeadlineBounded: true,
    postWriteFinalTabReadDeadlineBounded: true,
    postWriteOptionalReadsNonAuthoritative: true,
    postWriteOptionalReadsCanRewriteSubmittedOutcome: false,
    postWriteRpcReturnReserveMs: PR92_SCHEMA17_RPC_RETURN_RESERVE_MS
  };
};
