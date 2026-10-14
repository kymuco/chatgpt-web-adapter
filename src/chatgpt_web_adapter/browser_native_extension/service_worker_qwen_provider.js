
const CWA_QWEN_PROVIDER_ID = "qwen";
const CWA_QWEN_ORIGIN = "https://chat.qwen.ai";
const CWA_QWEN_RUNTIME_TAB_KEY = "qwenWebRuntimeTabIdV1";
const CWA_QWEN_ROUTE_MAP_KEY = "qwenWebConversationRoutesV1";
const CWA_QWEN_STABLE_MS = 9000;

function _cwaQwenIsUrl(url) {
  try {
    return new URL(url).origin === CWA_QWEN_ORIGIN;
  } catch {
    return false;
  }
}

function _cwaQwenIsConversationRoute(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CWA_QWEN_ORIGIN) return false;
    const match = /^\/c\/([^/]+)\/?$/.exec(parsed.pathname);
    return !!match && !["new-chat", "guest"].includes(match[1]);
  } catch {
    return false;
  }
}

async function _cwaQwenStorageGet(key) {
  const result = await chrome.storage.local.get(key);
  return result?.[key];
}

async function _cwaQwenStorageSet(key, value) {
  await chrome.storage.local.set({ [key]: value });
}

async function _cwaQwenStoredRoutes() {
  const value = await _cwaQwenStorageGet(CWA_QWEN_ROUTE_MAP_KEY);
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

async function _cwaQwenStoreRoute(conversationId, url) {
  if (!_cwaQwenIsConversationRoute(url)) throw new Error("QWEN_ROUTE_IDENTITY_INVALID");
  const routes = await _cwaQwenStoredRoutes();
  routes[conversationId] = url;
  await _cwaQwenStorageSet(CWA_QWEN_ROUTE_MAP_KEY, routes);
}

async function _cwaQwenRouteForConversation(conversationId) {
  const routes = await _cwaQwenStoredRoutes();
  const value = routes?.[conversationId];
  return typeof value === "string" && _cwaQwenIsConversationRoute(value) ? value : null;
}

async function _cwaQwenExistingTab() {
  const stored = await _cwaQwenStorageGet(CWA_QWEN_RUNTIME_TAB_KEY);
  if (!Number.isInteger(stored)) return null;
  try {
    const tab = await chrome.tabs.get(stored);
    return _cwaQwenIsUrl(tab?.url || "") ? tab : null;
  } catch {
    return null;
  }
}

async function _cwaQwenEnsureTab(conversationId) {
  let targetUrl = CWA_QWEN_ORIGIN + "/";
  if (conversationId !== null) {
    const storedRoute = await _cwaQwenRouteForConversation(conversationId);
    if (storedRoute === null) throw new Error("QWEN_CONTINUATION_ROUTE_UNKNOWN");
    targetUrl = storedRoute;
  }

  let tab = await _cwaQwenExistingTab();
  if (tab === null) {
    tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab?.id)) throw new Error("QWEN_RUNTIME_TAB_CREATE_FAILED");
    await _cwaQwenStorageSet(CWA_QWEN_RUNTIME_TAB_KEY, tab.id);
  } else if (tab.url !== targetUrl) {
    tab = await chrome.tabs.update(tab.id, { url: targetUrl, active: false });
  }

  tab = await _cwaBaseWaitForTabComplete(tab.id, 45000);
  if (!_cwaQwenIsUrl(tab?.url || "")) throw new Error("QWEN_RUNTIME_TAB_ORIGIN_CHANGED");
  return tab;
}

function _cwaQwenComposerExpression(text) {
  const expression = function(requestedText) {
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const r = el.getBoundingClientRect(), style = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const composer = Array.from(document.querySelectorAll(
      "textarea.message-input-textarea,textarea[placeholder='How can I help you today?']"
    )).find((el) => visible(el) && !el.disabled);
    if (!composer) return {found: false};
    if (requestedText === null) return {found: true};
    composer.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    if (typeof setter === "function") setter.call(composer, requestedText);
    else composer.value = requestedText;
    composer.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: requestedText}));
    composer.dispatchEvent(new Event("change", {bubbles: true}));
    return {found: true, written: composer.value === requestedText};
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(text === undefined ? null : text) + ")";
}

function _cwaQwenSnapshotExpression(promptText) {
  const expression = function(prompt) {
    const normalize = (s) => String(s || "").replace(/\s+/g, " ").trim();
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const r = el.getBoundingClientRect(), style = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    // Answer-phase only; thinking/search text is not a completed answer.
    const answers = Array.from(document.querySelectorAll("div.response-message-content.phase-answer")).filter(visible);
    const texts = answers.map((el) => normalize(el.innerText || el.textContent)).filter(Boolean).slice(-80);
    // Qwen retains awaiting-response classes after completion, so use only stop-button.
    const generating = Array.from(document.querySelectorAll("button.stop-button")).some(visible);
    return {url: location.href, texts, generating};
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(promptText) + ")";
}

async function _cwaQwenEvaluate(debuggee, expression) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.exceptionDetails) throw new Error("QWEN_PAGE_EVALUATION_FAILED");
  return result?.result?.value;
}

async function _cwaQwenWaitForComposer(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaQwenEvaluate(debuggee, _cwaQwenComposerExpression());
    if (snapshot?.found === true) return;
    await sleep(250);
  }
  throw new Error("QWEN_COMPOSER_NOT_READY");
}

function _cwaQwenSubmitExpression(text) {
  const expression = function(requestedText) {
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const r = el.getBoundingClientRect(), style = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const composer = Array.from(document.querySelectorAll(
      "textarea.message-input-textarea,textarea[placeholder='How can I help you today?']"
    )).find(visible);
    if (!composer) return {found: false, submitted: false};
    if (composer.value !== requestedText) return {found: true, submitted: false, reason: "composer_value_mismatch"};
    if (Array.from(document.querySelectorAll("button.stop-button")).some(visible)) {
      return {found: true, submitted: false, reason: "generation_active"};
    }
    const control = Array.from(document.querySelectorAll(
      "button.send-button,.chat-prompt-send-button button,div.message-input-right-button-send button"
    )).find((el) => visible(el) && el.disabled !== true && el.getAttribute("aria-disabled") !== "true");
    if (!control) return {found: true, submitted: false, reason: "send_control_not_ready"};
    control.click();
    return {found: true, submitted: true};
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(text) + ")";
}

function _cwaQwenDebuggerDetached(error) {
  const message = String(error?.message || error || "");
  return message.includes("Debugger is not attached to the tab");
}

async function _cwaQwenReattachForObservation(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    try {
      await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
      await _cwaBaseSendCommand(debuggee, "Runtime.enable");
      return;
    } catch {
      await sleep(150);
    }
  }
  throw new Error(
    "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "POST_SUBMIT_DEBUGGER_REATTACH_FAILED"
  );
}

function _cwaQwenPostSubmitAmbiguousError(error) {
  const message = String(error?.message || error || "UNKNOWN");
  if (message.startsWith(
    "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
  )) {
    return error;
  }
  return new Error(
    "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "POST_SUBMIT_OBSERVATION_FAILED:" +
    message
  );
}

async function _cwaQwenSubmitOnce(debuggee, text, deadlineAt) {
  const written = await _cwaQwenEvaluate(debuggee, _cwaQwenComposerExpression(text));
  if (written?.written !== true) throw new Error("QWEN_COMPOSER_WRITE_FAILED");

  while (performance.now() < deadlineAt) {
    try {
      const submit = await _cwaQwenEvaluate(debuggee, _cwaQwenSubmitExpression(text));
      if (submit?.submitted === true) return;
    } catch (error) {
      if (_cwaQwenDebuggerDetached(error)) {
        // A navigation may detach CDP after the single click. Never replay the write.
        return;
      }
      // This Runtime.evaluate can execute control.click() before its result is
      // lost. Any non-detach failure here is therefore post-submit ambiguous.
      throw _cwaQwenPostSubmitAmbiguousError(error);
    }
    await sleep(150);
  }
  throw new Error("QWEN_SUBMIT_CONTROL_NOT_READY");
}

function _cwaQwenLatestNewText(snapshot, baseline) {
  if (!Array.isArray(snapshot?.texts)) return null;
  for (let index = snapshot.texts.length - 1; index >= 0; index -= 1) {
    const text = snapshot.texts[index];
    if (typeof text === "string" && text.trim() && !baseline.has(text)) return text.trim();
  }
  return null;
}

async function _cwaQwenWaitForFinalText(debuggee, text, baseline, deadlineAt) {
  let lastText = null;
  let stableSince = null;
  while (performance.now() < deadlineAt) {
    let snapshot;
    try {
      snapshot = await _cwaQwenEvaluate(debuggee, _cwaQwenSnapshotExpression(text));
    } catch (error) {
      if (!_cwaQwenDebuggerDetached(error)) throw error;
      await _cwaQwenReattachForObservation(debuggee, deadlineAt);
      await sleep(250);
      continue;
    }
    const candidate = _cwaQwenLatestNewText(snapshot, baseline);
    if (candidate !== null && candidate === lastText) {
      if (stableSince === null) stableSince = performance.now();
    } else {
      lastText = candidate;
      stableSince = candidate === null ? null : performance.now();
    }
    if (candidate !== null && snapshot?.generating !== true &&
        stableSince !== null && performance.now() - stableSince >= CWA_QWEN_STABLE_MS) {
      return { text: candidate, url: snapshot.url };
    }
    await sleep(250);
  }
  throw new Error(
    "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "PAGE_FINALITY_TIMEOUT"
  );
}

async function _cwaQwenHandleTurn(message) {
  if (message?.type !== "turn") throw new Error("QWEN_TURN_TYPE_REQUIRED");
  if (typeof message?.text !== "string" || !message.text.trim()) throw new Error("QWEN_TEXT_REQUIRED");
  if ((Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0) ||
      message?.conversationMode != null || message?.modelProfile != null ||
      message?.browserAuthorityLeaseId != null) {
    throw new Error("QWEN_MINIMAL_PROOF_UNSUPPORTED_OPTION");
  }

  const conversationId =
    typeof message?.conversationId === "string" && message.conversationId.trim()
      ? message.conversationId.trim()
      : null;
  const timeoutMs = Math.max(5000, Math.min(Number(message?.timeoutMs) || 120000, 180000));
  const deadlineAt = performance.now() + timeoutMs;
  const startedAt = performance.now();
  const tab = await _cwaQwenEnsureTab(conversationId);
  const initialUrl = tab.url || CWA_QWEN_ORIGIN + "/";
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    await _cwaQwenWaitForComposer(debuggee, deadlineAt);

    const before = await _cwaQwenEvaluate(debuggee, _cwaQwenSnapshotExpression(message.text));
    const baseline = new Set(Array.isArray(before?.texts) ? before.texts : []);

    await _cwaQwenSubmitOnce(debuggee, message.text, deadlineAt);
    try {
      const final = await _cwaQwenWaitForFinalText(
        debuggee,
        message.text,
        baseline,
        deadlineAt
      );
      const finalTab = await chrome.tabs.get(tab.id);
      const finalUrl = typeof finalTab?.url === "string" ? finalTab.url : final.url;
      if (!_cwaQwenIsConversationRoute(finalUrl)) throw new Error("QWEN_FINAL_ROUTE_INVALID");

      let resolvedConversationId = conversationId;
      if (resolvedConversationId === null) {
        if (finalUrl === initialUrl) {
          throw new Error("QWEN_NEW_CHAT_ROUTE_IDENTITY_UNPROVEN");
        }
        resolvedConversationId = crypto.randomUUID();
      }
      await _cwaQwenStoreRoute(resolvedConversationId, finalUrl);

      return {
        providerId: CWA_QWEN_PROVIDER_ID,
        conversationId: resolvedConversationId,
        responseText: final.text,
        finalUrl,
        tabId: tab.id,
        elapsedMs: Math.round(performance.now() - startedAt),
        finalityEvidence: "PAGE_DOM_STABLE_COMPLETION",
        canonicalCompletionProven: false,
        routeIdentityProven: true,
        automaticWriteRetry: false
      };
    } catch (error) {
      throw _cwaQwenPostSubmitAmbiguousError(error);
    }
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

registerProductProviderTurnHandler(
  CWA_QWEN_PROVIDER_ID,
  _cwaQwenHandleTurn
);
