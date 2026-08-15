importScripts("service_worker_temporary_chat_semantic_notice.js");

// PR8.7 live characterization #4:
// Pre-write DOM, aria-label, Accessibility Tree, and page-level semantic
// observations did not expose a durable selected-state proof for the current
// Temporary control. Add an explicitly diagnostic one-shot write experiment.
//
// This is NOT the production Temporary Chat path. It requires a dedicated
// request flag, uses a disposable new-chat tab, never reuses the production
// runtime tab, never retries an ambiguous write, and exports only bounded safe
// metadata. Raw prompt/assistant text, request headers, request bodies, response
// bodies, cookies, protection material, and raw DOM/AX data stay browser-local.

const _pr87TurnProbePriorExecuteNativeTurn = executeNativeTurn;

function _pr87TurnProbeUrlKind(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return "non_chatgpt";
    if (/^\/c\/[^/]+/.test(parsed.pathname)) return "conversation";
    if (parsed.pathname === "/" || parsed.pathname === "") return "new_chat_root";
    return "other_chatgpt";
  } catch {
    return "invalid";
  }
}

async function _pr87TurnProbeExecute(message) {
  const text = typeof message?.text === "string" ? message.text : "";
  if (!text.trim()) throw new Error("TEMPORARY_CHAT_TURN_PROBE_TEXT_REQUIRED");
  if (text.length > 20_000) throw new Error("TEMPORARY_CHAT_TURN_PROBE_TEXT_TOO_LARGE");

  const timeoutMs = _pr87ClampProbeTimeoutMs(message?.timeoutMs);
  const startedAt = performance.now();
  let tabId = null;
  let debuggee = null;
  let attached = false;
  let eventListener = null;
  let activationListener = null;
  let tabWasActive = false;
  let tabActiveAfter = null;
  let tabActivatedDuringProbe = false;
  let probeTabClosed = false;
  let result = null;

  const activatedTabIds = new Set();
  activationListener = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(activationListener);

  try {
    const tab = await chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false });
    if (!Number.isInteger(tab?.id)) {
      throw new Error("TEMPORARY_CHAT_TURN_PROBE_TAB_CREATE_FAILED");
    }
    tabId = tab.id;
    tabWasActive = Boolean(tab.active);
    await waitForTabComplete(tabId, Math.min(timeoutMs, 45_000));

    debuggee = { tabId };
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _pr87RawSendCommand(debuggee, "Network.enable");
    await _pr87RawSendCommand(debuggee, "Runtime.enable");
    await _pr87RawSendCommand(debuggee, "Accessibility.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );

    const before = await _pr87TemporaryControlSnapshot(debuggee);
    if (!before?.controlFound) {
      throw new Error("TEMPORARY_CHAT_TURN_PROBE_CONTROL_NOT_FOUND");
    }
    if (before?.ambiguous || before?.candidateCount !== 1) {
      throw new Error("TEMPORARY_CHAT_TURN_PROBE_CONTROL_AMBIGUOUS");
    }
    if (!before?.point || !Number.isFinite(before.point.x) || !Number.isFinite(before.point.y)) {
      throw new Error("TEMPORARY_CHAT_TURN_PROBE_CONTROL_POINT_UNAVAILABLE");
    }

    let activationAction = "already_proven_selected";
    if (before.selected !== true) {
      activationAction = before.selected === false
        ? "click_known_unselected_control"
        : "click_unique_control_without_selected_state_proof";
      await _pr87ClickPoint(debuggee, before.point);
    }

    const afterActivation = await _pr87TemporaryControlSnapshot(debuggee);
    const selectionProvenBeforeWrite = afterActivation?.selected === true;
    const preWriteProofSignals = Array.isArray(afterActivation?.proofSignals)
      ? afterActivation.proofSignals.filter((value) => typeof value === "string")
      : [];

    let conversationRequestId = null;
    let conversationWriteCount = 0;
    let responseStatus = null;
    let responseMimeType = null;
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
      if (source?.tabId !== tabId) return;
      const request = params?.request;
      if (method === "Network.requestWillBeSent" &&
          isConversationWrite(request?.url || "", request?.method || "")) {
        conversationWriteCount += 1;
        if (!conversationRequestId) {
          conversationRequestId = params.requestId;
          resolveRequestSeen(params.requestId);
        }
        return;
      }
      if (!conversationRequestId || params?.requestId !== conversationRequestId) return;
      if (method === "Network.responseReceived") {
        responseStatus = params?.response?.status ?? null;
        responseMimeType = params?.response?.mimeType ?? null;
        return;
      }
      if (method === "Network.loadingFailed") {
        rejectCompleted(new Error(
          `TEMPORARY_CHAT_TURN_PROBE_REQUEST_FAILED:${params?.errorText || "unknown"}`
        ));
        return;
      }
      if (method === "Network.loadingFinished") {
        resolveCompleted(conversationRequestId);
      }
    };
    chrome.debugger.onEvent.addListener(eventListener);

    await locateAndFocusComposer(debuggee);
    await clearComposer(debuggee);
    await _pr87RawSendCommand(debuggee, "Input.insertText", { text });

    const submitStartedAt = performance.now();
    const submit = await submitOfficialPageTurn(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_READY_TIMEOUT_MS)
    );

    await Promise.race([
      requestSeen,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error(`TEMPORARY_CHAT_TURN_PROBE_SUBMIT_NOT_OBSERVED:${submit.strategy}`)),
        Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_ACK_TIMEOUT_MS)
      ))
    ]);
    const submitAckMs = elapsedMs(submitStartedAt);

    const requestId = await Promise.race([
      completed,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("TEMPORARY_CHAT_TURN_PROBE_TIMEOUT")),
        remainingMs(startedAt, timeoutMs)
      ))
    ]);

    let safeMetadata = { conversationId: null, turnExchangeId: null };
    try {
      const response = await _pr87RawSendCommand(
        debuggee,
        "Network.getResponseBody",
        { requestId }
      );
      safeMetadata = extractSafeStreamMetadata(
        response?.body,
        Boolean(response?.base64Encoded)
      );
    } catch {
      // Safe identity metadata is optional characterization evidence.
    }

    await sleep(500);
    const completionReadyWaitMs = await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );

    const afterTurn = await _pr87TemporaryControlSnapshot(debuggee);
    const finalTab = await chrome.tabs.get(tabId);
    const urlConversationId = conversationIdFromUrl(finalTab.url || "");
    const resolvedConversationId = safeMetadata.conversationId || urlConversationId;

    if (!Number.isInteger(responseStatus) || responseStatus < 200 || responseStatus >= 300) {
      throw new Error(`TEMPORARY_CHAT_TURN_PROBE_HTTP_STATUS:${responseStatus}`);
    }
    if (conversationWriteCount !== 1) {
      throw new Error(`TEMPORARY_CHAT_TURN_PROBE_WRITE_COUNT:${conversationWriteCount}`);
    }

    try {
      tabActiveAfter = Boolean((await chrome.tabs.get(tabId))?.active);
    } catch {
      tabActiveAfter = null;
    }
    tabActivatedDuringProbe = activatedTabIds.has(tabId);

    result = {
      probeContext: "isolated_new_chat_temporary_turn",
      activationAction,
      selectionProvenBeforeWrite,
      selectedBefore: typeof before?.selected === "boolean" ? before.selected : null,
      selectedAfterActivation: typeof afterActivation?.selected === "boolean"
        ? afterActivation.selected
        : null,
      selectedAfterTurn: typeof afterTurn?.selected === "boolean" ? afterTurn.selected : null,
      preWriteProofSignals,
      postTurnProofSignals: Array.isArray(afterTurn?.proofSignals)
        ? afterTurn.proofSignals.filter((value) => typeof value === "string")
        : [],
      conversationWriteCount,
      conversationId: typeof resolvedConversationId === "string" ? resolvedConversationId : null,
      turnExchangeId: typeof safeMetadata.turnExchangeId === "string"
        ? safeMetadata.turnExchangeId
        : null,
      responseStatus,
      responseMimeType: typeof responseMimeType === "string" ? responseMimeType : null,
      finalUrlKind: _pr87TurnProbeUrlKind(finalTab.url || ""),
      urlConversationIdPresent: typeof urlConversationId === "string" && urlConversationId.length > 0,
      submitStrategy: submit.strategy,
      submitAckMs,
      completionReadyWaitMs,
      tabWasActive,
      tabActiveAfter,
      tabActivatedDuringProbe,
      foregroundActivationObserved: Boolean(
        tabWasActive || tabActiveAfter === true || tabActivatedDuringProbe
      ),
      elapsedMs: elapsedMs(startedAt)
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (attached && debuggee) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // The disposable probe tab may already have disappeared.
      }
    }
    if (activationListener) chrome.tabs.onActivated.removeListener(activationListener);
    if (Number.isInteger(tabId)) {
      try {
        await chrome.tabs.remove(tabId);
        probeTabClosed = true;
      } catch {
        probeTabClosed = false;
      }
    }
  }

  if (!result) throw new Error("TEMPORARY_CHAT_TURN_PROBE_NO_RESULT");
  return {
    ...result,
    probeTabClosed,
    elapsedMs: elapsedMs(startedAt)
  };
}

executeNativeTurn = async function _executeNativeTurnWithTemporaryTurnCharacterization(message) {
  if (message?.characterizeTemporaryTurn !== true) {
    return _pr87TurnProbePriorExecuteNativeTurn(message);
  }
  if (message?.probeTemporaryMode === true) {
    throw new Error("TEMPORARY_CHAT_TURN_PROBE_FLAG_CONFLICT");
  }
  if (message?.conversationId != null) {
    throw new Error("TEMPORARY_CHAT_TURN_PROBE_REQUIRES_NEW_CHAT");
  }
  if (message?.acknowledgeDurableRisk !== true) {
    throw new Error("TEMPORARY_CHAT_TURN_PROBE_DURABLE_RISK_ACK_REQUIRED");
  }
  return _pr87TurnProbeExecute(message);
};
