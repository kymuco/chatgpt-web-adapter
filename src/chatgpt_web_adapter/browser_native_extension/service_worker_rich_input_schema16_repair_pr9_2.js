// PR9.2 schema-16 outer-deadline / post-write teardown closure.
//
// Loaded after schema 15. This immutable layer closes three remaining gaps in
// the original PR9.2 wrapper without changing text-only product semantics:
//   1. the mandatory durable-fence read is raced against the one outer turn
//      deadline, so a stalled storage read cannot keep the worker turn busy;
//   2. rich runtime-tab acquisition is raced as one complete helper operation,
//      covering its raw storage/tabs calls as well as the already-bounded load;
//   3. once Network.requestWillBeSent proves the protected conversation POST,
//      inherited debugger detach/getTargets teardown becomes best-effort and can
//      no longer convert an already-submitted write into a response-lost timeout.

const _pr92Schema16PriorEnsureRuntimeTab = ensureRuntimeTab;
const _pr92Schema16PriorExecuteOfficialPageTurn = executeOfficialPageTurn;
const _pr92Schema16PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA16_REPAIR_SCHEMA = 16;

_pr92ReadDirtyAttachmentFence = async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline() {
  const context = _pr92ActiveTurnContext;
  try {
    const stored = context === null
      ? await chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY)
      : await _pr92Schema7RunUntil(
          context.deadlineAt,
          "SCHEMA16_STALE_ATTACHMENT_FENCE_READ",
          () => chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY)
        );
    const record = stored?.[PR92_DIRTY_ATTACHMENT_STORAGE_KEY];
    const tabId = Number.isInteger(record?.tabId) ? record.tabId : null;
    _pr92DirtyAttachmentTabId = tabId;
    return tabId;
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) throw error;
    // A non-timeout storage failure still means we cannot prove clean state.
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_READ_FAILED");
  }
};

ensureRuntimeTab = async function _pr92Schema16EnsureRuntimeTabWithinRichDeadline(
  conversationId
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92Schema16PriorEnsureRuntimeTab(conversationId);
  }
  return _pr92Schema7RunUntil(
    context.deadlineAt,
    "SCHEMA16_RUNTIME_TAB_ACQUISITION",
    () => _pr92Schema16PriorEnsureRuntimeTab(conversationId)
  );
};

function _pr92Schema16DispatchPostWriteDebuggerTeardown(debuggee) {
  // After the POST is observed, teardown has no authority over the submitted
  // outcome. Dispatch both diagnostics operations best-effort and never await
  // them; the durable attachment fence remains the next-turn recovery authority.
  try {
    const detachPending = chrome.debugger.detach(debuggee);
    if (detachPending && typeof detachPending.catch === "function") {
      detachPending.catch(() => {});
    }
  } catch {}
  try {
    const targetsPending = chrome.debugger.getTargets();
    if (targetsPending && typeof targetsPending.catch === "function") {
      targetsPending.catch(() => {});
    }
  } catch {}
}

async function _pr92Schema16ExecuteOfficialPageTurn({ tabId, text, timeoutMs }) {
  if (!Number.isInteger(tabId)) throw new Error("TAB_ID_REQUIRED");
  if (typeof text !== "string" || !text.trim()) throw new Error("TEXT_REQUIRED");
  if (text.length > 200_000) throw new Error("TEXT_TOO_LARGE_FOR_BROWSER_NATIVE_TURN");

  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92Schema16PriorExecuteOfficialPageTurn({ tabId, text, timeoutMs });
  }

  const startedAt = performance.now();
  const tab = await chrome.tabs.get(tabId);
  if (!isChatGPTUrl(tab.url || "")) throw new Error("RUNTIME_TAB_IS_NOT_CHATGPT");
  const debuggee = { tabId };
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
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await sendCommand(debuggee, "Network.enable");
    await sendCommand(debuggee, "Runtime.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
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

    diagnostics.composerStrategy = await locateAndFocusComposer(debuggee);
    await clearComposer(debuggee);
    await sendCommand(debuggee, "Input.insertText", { text });

    const submitStartedAt = performance.now();
    const submit = await submitOfficialPageTurn(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_READY_TIMEOUT_MS)
    );
    diagnostics.submitStrategy = submit.strategy;
    diagnostics.submitButtonSelector = submit.selector;

    await Promise.race([
      requestSeen,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error(`CHATGPT_SUBMIT_NOT_OBSERVED:${submit.strategy}`)),
        Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_ACK_TIMEOUT_MS)
      ))
    ]);
    diagnostics.submitAckMs = elapsedMs(submitStartedAt);

    const requestId = await Promise.race([
      completed,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("CHATGPT_TURN_TIMEOUT")),
        remainingMs(startedAt, timeoutMs)
      ))
    ]);

    let safeMetadata = { conversationId: null, turnExchangeId: null };
    try {
      const response = await sendCommand(debuggee, "Network.getResponseBody", { requestId });
      safeMetadata = extractSafeStreamMetadata(response?.body, Boolean(response?.base64Encoded));
    } catch {
      // Optional safe metadata only.
    }

    diagnostics.completionReadyWaitMs = await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );

    const finalTab = await chrome.tabs.get(tabId);
    const urlConversationId = conversationIdFromUrl(finalTab.url || "");
    diagnostics.elapsedMs = elapsedMs(startedAt);
    return {
      diagnostics,
      finalUrl: finalTab.url || "",
      conversationId: safeMetadata.conversationId || urlConversationId,
      turnExchangeId: safeMetadata.turnExchangeId
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);

    if (diagnostics.conversationRequestSeen === true) {
      // The write has already crossed the protected boundary. Never await the
      // inherited teardown operations or let them rewrite this submitted outcome.
      if (attached) _pr92Schema16DispatchPostWriteDebuggerTeardown(debuggee);
      diagnostics.debuggerAttachedAfter = null;
    } else {
      // Before write proof exists, debugger release remains governed by the same
      // outer deadline. Failure cleanup is non-authoritative after that deadline.
      if (attached) {
        try {
          await _pr92Schema7RunUntil(
            context.deadlineAt,
            "SCHEMA16_PREWRITE_PAGE_TURN_DEBUGGER_DETACH",
            () => chrome.debugger.detach(debuggee)
          );
        } catch {}
      }
      try {
        const targets = await _pr92Schema7RunUntil(
          context.deadlineAt,
          "SCHEMA16_PREWRITE_PAGE_TURN_DEBUGGER_TARGETS",
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

executeOfficialPageTurn = async function _pr92Schema16ExecuteOfficialPageTurnWithinTurn(args) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) return _pr92Schema16PriorExecuteOfficialPageTurn(args);
  const outerContext = _pr92ActiveTurnContext;
  if (outerContext === null) {
    throw new Error("PR9_2_RICH_INPUT_TURN_CONTEXT_REQUIRED");
  }
  return _pr92Schema16ExecuteOfficialPageTurn({
    ...args,
    timeoutMs: _pr92CapTimeoutToTurn(
      outerContext,
      args?.timeoutMs,
      "SCHEMA16_PROTECTED_PAGE_DISPATCH"
    )
  });
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema16Repair(message) {
  const result = await _pr92Schema16PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA16_REPAIR_SCHEMA,
    durableFenceReadDeadlineBounded: true,
    runtimeTabAcquisitionDeadlineBounded: true,
    inheritedPageTurnPostWriteTeardownNonBlocking: true,
    postWriteDebuggerDetachBestEffort: true,
    postWriteDebuggerTargetsProbeBestEffort: true,
    postWriteTeardownCanRewriteSubmittedOutcome: false
  };
};