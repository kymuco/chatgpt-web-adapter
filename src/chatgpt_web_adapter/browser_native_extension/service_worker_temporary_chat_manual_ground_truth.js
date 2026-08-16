importScripts("service_worker_temporary_chat_history_probe.js");

// PR8.7 manual ground-truth characterization:
// Automated activation produced an ordinary durable chat and therefore cannot
// serve as Temporary evidence. This diagnostic intentionally DOES NOT click the
// Temporary control. The human operator must first enable Temporary Chat in the
// visible product UI and leave that fresh new-chat tab selected in Chrome.
//
// The probe then writes exactly one smoke turn through that already prepared
// page, captures bounded identity/finality metadata, verifies bounded visible
// turn evidence without exporting message text/DOM, detaches, and leaves the
// source tab open. It performs no canonical read and no history probe itself so
// later experiments can observe history BEFORE any direct-id readback.

const _pr87ManualPriorExecuteNativeTurn = executeNativeTurn;
const PR87_MANUAL_DEFAULT_TIMEOUT_MS = 150_000;
const PR87_MANUAL_MAX_TIMEOUT_MS = 300_000;

function _pr87ManualClampTimeoutMs(value) {
  if (!Number.isFinite(value)) return PR87_MANUAL_DEFAULT_TIMEOUT_MS;
  return Math.max(10_000, Math.min(Number(value), PR87_MANUAL_MAX_TIMEOUT_MS));
}

function _pr87ManualUrlEvidence(url) {
  try {
    const parsed = new URL(url);
    const normalized = `${parsed.pathname} ${parsed.search} ${parsed.hash}`.toLowerCase();
    const urlConversationId = conversationIdFromUrl(url || "");
    return {
      kind: _pr87TurnProbeUrlKind(url),
      temporaryMarker: normalized.includes("temporary"),
      temporaryQueryTrue: parsed.searchParams.get("temporary-chat") === "true",
      conversationIdPresent: typeof urlConversationId === "string" && urlConversationId.length > 0
    };
  } catch {
    return {
      kind: "invalid",
      temporaryMarker: false,
      temporaryQueryTrue: false,
      conversationIdPresent: false
    };
  }
}

function _pr87ManualTurnSurfaceExpression(userText, expectedAssistantText) {
  const encodedUserText = JSON.stringify(userText);
  const encodedExpectedAssistantText = JSON.stringify(expectedAssistantText || "");
  return `(() => {
    const expectedUser = ${encodedUserText};
    const expectedAssistant = ${encodedExpectedAssistantText};
    const normalize = (value) => typeof value === 'string'
      ? value.trim().replace(/\\s+/g, ' ')
      : '';
    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const cleanedText = (element) => {
      if (!(element instanceof Element)) return '';
      const clone = element.cloneNode(true);
      for (const removable of Array.from(clone.querySelectorAll(
        'button,nav,[role="toolbar"],script,style,[aria-hidden="true"]'
      ))) {
        removable.remove();
      }
      return normalize(clone.innerText || clone.textContent || '');
    };

    const main = document.querySelector('main');
    if (!main) {
      return {
        surfaceReady: false,
        turnCount: 0,
        userMatchCount: 0,
        assistantCandidateCount: 0,
        assistantExpectedMatchCount: 0,
        userMessageVisible: false,
        assistantMessageVisible: false,
        assistantExactExpectedReplyVisible: false,
        orderedUserThenAssistant: false,
        selectorKind: 'none'
      };
    }

    let selectorKind = 'conversation-testid';
    let turns = Array.from(main.querySelectorAll('[data-testid^="conversation-turn-"]'));
    if (turns.length === 0) {
      selectorKind = 'article-fallback';
      turns = Array.from(main.querySelectorAll('article'));
    }
    turns = Array.from(new Set(turns)).filter((element) => {
      if (!isVisible(element)) return false;
      if (element.closest('form')) return false;
      return true;
    });

    const userNormalized = normalize(expectedUser);
    const assistantNormalized = normalize(expectedAssistant);
    const turnTexts = turns.map((element) => cleanedText(element));
    const userIndexes = [];
    for (let index = 0; index < turnTexts.length; index += 1) {
      const text = turnTexts[index];
      if (userNormalized && text.includes(userNormalized)) userIndexes.push(index);
    }

    const firstUserIndex = userIndexes.length > 0 ? userIndexes[0] : -1;
    const assistantCandidateIndexes = [];
    const assistantExpectedIndexes = [];
    if (firstUserIndex >= 0) {
      for (let index = firstUserIndex + 1; index < turnTexts.length; index += 1) {
        const text = turnTexts[index];
        if (text) assistantCandidateIndexes.push(index);
        if (assistantNormalized && text === assistantNormalized) {
          assistantExpectedIndexes.push(index);
        }
      }
    }

    const assistantMessageVisible = assistantCandidateIndexes.length > 0;
    const assistantExactExpectedReplyVisible = assistantExpectedIndexes.length > 0;
    return {
      surfaceReady: true,
      turnCount: turns.length,
      userMatchCount: userIndexes.length,
      assistantCandidateCount: assistantCandidateIndexes.length,
      assistantExpectedMatchCount: assistantExpectedIndexes.length,
      userMessageVisible: userIndexes.length > 0,
      assistantMessageVisible,
      assistantExactExpectedReplyVisible,
      orderedUserThenAssistant: firstUserIndex >= 0 && assistantMessageVisible,
      selectorKind
    };
  })()`;
}

async function _pr87ManualTurnSurfaceSnapshot(debuggee, userText, expectedAssistantText) {
  try {
    const result = await _pr87RawSendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr87ManualTurnSurfaceExpression(userText, expectedAssistantText),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (value && typeof value === "object") return value;
  } catch {
    // Visible-turn evidence is diagnostic. Failure stays INCONCLUSIVE.
  }
  return {
    surfaceReady: false,
    turnCount: 0,
    userMatchCount: 0,
    assistantCandidateCount: 0,
    assistantExpectedMatchCount: 0,
    userMessageVisible: false,
    assistantMessageVisible: false,
    assistantExactExpectedReplyVisible: false,
    orderedUserThenAssistant: false,
    selectorKind: "unavailable"
  };
}

async function _pr87ManualPreparedTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const candidates = tabs.filter((tab) => {
    if (!Number.isInteger(tab?.id) || typeof tab?.url !== "string") return false;
    try {
      return new URL(tab.url).origin === CHATGPT_ORIGIN;
    } catch {
      return false;
    }
  });
  if (candidates.length !== 1) {
    throw new Error(`TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_TAB_COUNT:${candidates.length}`);
  }
  const tab = candidates[0];
  const parsed = new URL(tab.url);
  if (parsed.pathname !== "/" && parsed.pathname !== "") {
    throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_REQUIRES_FRESH_NEW_CHAT");
  }
  if (parsed.searchParams.get("temporary-chat") !== "true") {
    throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_REQUIRES_TEMPORARY_URL");
  }
  return tab;
}

async function _pr87ManualGroundTruthTurn(message) {
  const text = typeof message?.text === "string" ? message.text : "";
  if (!text.trim()) throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_TEXT_REQUIRED");
  if (text.length > 20_000) throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_TEXT_TOO_LARGE");
  if (message?.manualTemporaryConfirmed !== true) {
    throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_CONFIRMATION_REQUIRED");
  }
  const expectedAssistantText = typeof message?.expectedAssistantText === "string"
    ? message.expectedAssistantText.trim()
    : "";
  if (expectedAssistantText.length > 20_000) {
    throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_EXPECTED_TEXT_TOO_LARGE");
  }

  const timeoutMs = _pr87ManualClampTimeoutMs(message?.timeoutMs);
  const startedAt = performance.now();
  const tab = await _pr87ManualPreparedTab();
  const tabId = tab.id;
  const initialUrlEvidence = _pr87ManualUrlEvidence(tab.url || "");
  const debuggee = { tabId };
  let attached = false;
  let eventListener = null;
  let conversationRequestId = null;
  let conversationWriteCount = 0;
  let responseStatus = null;
  let responseMimeType = null;

  let resolveRequestSeen;
  let resolveCompleted;
  let rejectCompleted;
  const requestSeen = new Promise((resolve) => { resolveRequestSeen = resolve; });
  const completed = new Promise((resolve, reject) => {
    resolveCompleted = resolve;
    rejectCompleted = reject;
  });

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _pr87RawSendCommand(debuggee, "Network.enable");
    await _pr87RawSendCommand(debuggee, "Runtime.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );
    const beforeSurface = await _pr87ManualTurnSurfaceSnapshot(
      debuggee,
      text,
      expectedAssistantText
    );

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
          `TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_REQUEST_FAILED:${params?.errorText || "unknown"}`
        ));
        return;
      }
      if (method === "Network.loadingFinished") resolveCompleted(conversationRequestId);
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
        () => reject(new Error(`TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_SUBMIT_NOT_OBSERVED:${submit.strategy}`)),
        Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_SUBMIT_ACK_TIMEOUT_MS)
      ))
    ]);
    const submitAckMs = elapsedMs(submitStartedAt);

    const requestId = await Promise.race([
      completed,
      new Promise((_, reject) => setTimeout(
        () => reject(new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_TIMEOUT")),
        remainingMs(startedAt, timeoutMs)
      ))
    ]);

    let safeMetadata = { conversationId: null, turnExchangeId: null };
    try {
      const response = await _pr87RawSendCommand(debuggee, "Network.getResponseBody", { requestId });
      safeMetadata = extractSafeStreamMetadata(response?.body, Boolean(response?.base64Encoded));
    } catch {
      // Identity metadata is optional; raw response data never leaves this context.
    }

    await sleep(500);
    const completionReadyWaitMs = await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );
    const afterSurface = await _pr87ManualTurnSurfaceSnapshot(
      debuggee,
      text,
      expectedAssistantText
    );
    const afterTurn = await _pr87TemporaryControlSnapshot(debuggee);
    const finalTab = await chrome.tabs.get(tabId);
    const finalUrlEvidence = _pr87ManualUrlEvidence(finalTab.url || "");
    const urlConversationId = conversationIdFromUrl(finalTab.url || "");
    const resolvedConversationId = safeMetadata.conversationId || urlConversationId;
    const sameSourceTab = finalTab.id === tabId;
    const turnCountGrowth = Number.isInteger(afterSurface?.turnCount) && Number.isInteger(beforeSurface?.turnCount)
      ? afterSurface.turnCount - beforeSurface.turnCount
      : null;
    const visibleTurnGroundTruthProven = Boolean(
      afterSurface?.surfaceReady === true &&
      afterSurface?.userMessageVisible === true &&
      afterSurface?.assistantMessageVisible === true &&
      afterSurface?.orderedUserThenAssistant === true &&
      turnCountGrowth != null && turnCountGrowth >= 2 &&
      (!expectedAssistantText || afterSurface?.assistantExactExpectedReplyVisible === true)
    );

    if (!Number.isInteger(responseStatus) || responseStatus < 200 || responseStatus >= 300) {
      throw new Error(`TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_HTTP_STATUS:${responseStatus}`);
    }
    if (conversationWriteCount !== 1) {
      throw new Error(`TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_WRITE_COUNT:${conversationWriteCount}`);
    }

    return {
      probeContext: "manual_temporary_ground_truth_turn",
      manualTemporaryConfirmed: true,
      sourceTabId: tabId,
      sourceTabLeftOpen: true,
      sameSourceTab,
      initialUrlKind: initialUrlEvidence.kind,
      initialUrlTemporaryMarker: initialUrlEvidence.temporaryMarker,
      initialUrlTemporaryQueryTrue: initialUrlEvidence.temporaryQueryTrue,
      initialUrlConversationIdPresent: initialUrlEvidence.conversationIdPresent,
      conversationWriteCount,
      conversationId: typeof resolvedConversationId === "string" ? resolvedConversationId : null,
      turnExchangeId: typeof safeMetadata.turnExchangeId === "string" ? safeMetadata.turnExchangeId : null,
      responseStatus,
      responseMimeType: typeof responseMimeType === "string" ? responseMimeType : null,
      finalUrlKind: finalUrlEvidence.kind,
      finalUrlTemporaryMarker: finalUrlEvidence.temporaryMarker,
      finalUrlTemporaryQueryTrue: finalUrlEvidence.temporaryQueryTrue,
      urlConversationIdPresent: finalUrlEvidence.conversationIdPresent,
      submitStrategy: submit.strategy,
      submitAckMs,
      completionReadyWaitMs,
      conversationTurnCountBefore: Number.isInteger(beforeSurface?.turnCount) ? beforeSurface.turnCount : null,
      conversationTurnCountAfter: Number.isInteger(afterSurface?.turnCount) ? afterSurface.turnCount : null,
      turnCountGrowth,
      matchingUserMessageCount: Number.isInteger(afterSurface?.userMatchCount)
        ? afterSurface.userMatchCount
        : 0,
      assistantMessageCandidateCount: Number.isInteger(afterSurface?.assistantCandidateCount)
        ? afterSurface.assistantCandidateCount
        : 0,
      matchingExpectedAssistantMessageCount: Number.isInteger(afterSurface?.assistantExpectedMatchCount)
        ? afterSurface.assistantExpectedMatchCount
        : 0,
      userMessageVisibleAfterTurn: afterSurface?.userMessageVisible === true,
      assistantMessageVisibleAfterTurn: afterSurface?.assistantMessageVisible === true,
      assistantExactExpectedReplyVisible: afterSurface?.assistantExactExpectedReplyVisible === true,
      visibleTurnGroundTruthProven,
      turnSurfaceEvidenceStatus: visibleTurnGroundTruthProven ? "PROVEN" : "INCONCLUSIVE",
      turnSurfaceSelectorKind: typeof afterSurface?.selectorKind === "string"
        ? afterSurface.selectorKind
        : "unavailable",
      uiModeMarkerObservedAfterTurn: afterTurn?.modeMarkerObserved === true,
      postTurnUiModeSignals: Array.isArray(afterTurn?.modeMarkerSignals)
        ? afterTurn.modeMarkerSignals.filter((value) => typeof value === "string")
        : [],
      elapsedMs: elapsedMs(startedAt)
    };
  } finally {
    if (eventListener) chrome.debugger.onEvent.removeListener(eventListener);
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    // Intentionally do NOT close or activate the manually prepared source tab.
  }
}

executeNativeTurn = async function _executeNativeTurnWithManualTemporaryGroundTruth(message) {
  if (message?.characterizeManualTemporaryGroundTruth !== true) {
    return _pr87ManualPriorExecuteNativeTurn(message);
  }
  if (
    message?.probeTemporaryMode === true ||
    message?.characterizeTemporaryTurn === true ||
    message?.probeTemporaryHistoryPresence === true ||
    message?.conversationId != null
  ) {
    throw new Error("TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_FLAG_CONFLICT");
  }
  return _pr87ManualGroundTruthTurn(message);
};
