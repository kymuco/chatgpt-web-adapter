
const CWA_QWEN_PROVIDER_ID = "qwen";
const CWA_QWEN_ORIGIN = "https://chat.qwen.ai";
const CWA_QWEN_RUNTIME_TAB_KEY = "qwenWebRuntimeTabIdV1";
const CWA_QWEN_ROUTE_MAP_KEY = "qwenWebConversationRoutesV1";
// DOM quiet time is an observation heuristic, not authoritative server finality.
// Never shorten it just because Qwen briefly hides the Stop button.
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

function _cwaQwenIsEmptyChatRoute(url) {
  try {
    const parsed = new URL(url);
    return parsed.origin === CWA_QWEN_ORIGIN &&
      (parsed.pathname === "/" || parsed.pathname === "/c/new-chat") &&
      !parsed.searchParams.has("chat_id");
  } catch {
    return false;
  }
}

async function _cwaQwenEnsureTab(conversationId) {
  // Reuse an empty tab or create a background tab; never replace an existing chat.
  // This prevents new Qwen onboarding/age-verification windows on every send.
  const expectedRoute = conversationId === null
    ? null
    : await _cwaQwenRouteForConversation(conversationId);
  if (conversationId !== null && expectedRoute === null) {
    throw new Error("QWEN_CONTINUATION_ROUTE_UNKNOWN");
  }

  const existing = await chrome.tabs.query({url: CWA_QWEN_ORIGIN + "/*"});
  const stored = await _cwaQwenExistingTab();
  const available = [...existing];
  if (stored && !available.some(tab => tab.id === stored.id)) {
    available.push(stored);
  }
  let tab = conversationId === null
    ? available.find(candidate => _cwaQwenIsEmptyChatRoute(candidate.url || ""))
    : available.find(candidate => candidate.url === expectedRoute);
  if (!tab && conversationId === null) {
    tab = await chrome.tabs.create({url: CWA_QWEN_ORIGIN + "/", active: false});
  }
  if (!tab || !Number.isInteger(tab.id)) {
    throw new Error(conversationId === null
      ? "QWEN_NEW_CHAT_TAB_NOT_OPEN: open a new Qwen chat and finish account setup yourself"
      : "QWEN_CONTINUATION_TAB_NOT_OPEN: open the existing conversation in Qwen");
  }
  await _cwaQwenStorageSet(CWA_QWEN_RUNTIME_TAB_KEY, tab.id);
  const ready = await _cwaBaseWaitForTabComplete(tab.id, 45000);
  if (!_cwaQwenIsUrl(ready?.url || "")) {
    throw new Error("QWEN_RUNTIME_TAB_ORIGIN_CHANGED");
  }
  if (conversationId === null && !_cwaQwenIsEmptyChatRoute(ready.url)) {
    throw new Error("QWEN_NEW_CHAT_ROUTE_CHANGED_BEFORE_SUBMIT");
  }
  if (conversationId !== null && ready.url !== expectedRoute) {
    throw new Error("QWEN_CONTINUATION_ROUTE_CHANGED_BEFORE_SUBMIT");
  }
  return ready;
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
    return {url: location.href, texts, generating, answerCount: answers.length};
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

function _cwaQwenAgeExpression(year, allow, submitted) {
  const expression = function(year, allow, submitted) {
    const dialog = document.querySelector('.age-confirmation-modal[role="dialog"]');
    if (!dialog || !dialog.getBoundingClientRect().height) return "absent";
    if (!allow) return "required";
    if (submitted) return "waiting";
    const selected = dialog.querySelector('.age-confirmation-year .qwen-chat-v2-dropdown-menu-select-label');
    if (selected?.textContent.trim() !== String(year)) {
      const menu = document.querySelector('.qwen-chat-v2-dropdown-menu-popup[role="menu"]');
      if (menu) {
        const option = Array.from(menu.querySelectorAll('[role="menuitem"]')).find(el => el.textContent.trim() === String(year));
        if (!option) return "year_unavailable";
        option.click();
      } else dialog.querySelector('.age-confirmation-year .qwen-chat-v2-dropdown-menu-trigger')?.click();
      return "selecting";
    }
    const button = Array.from(dialog.querySelectorAll('button')).find(el => el.textContent.trim() === "Continue");
    if (!button || button.disabled) return "waiting";
    button.click();
    return "submitted";
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(year) + "," + (allow === true) + "," + (submitted === true) + ")";
}

async function _cwaQwenWaitForComposer(debuggee, deadlineAt, message = {}) {
  let ageSubmitted = false;
  while (performance.now() < deadlineAt) {
    const age = await _cwaQwenEvaluate(debuggee, _cwaQwenAgeExpression(message.birthYear || 2000, message.autoConfirmAge, ageSubmitted));
    if (age === "required") throw new Error("QWEN_AGE_CONFIRMATION_REQUIRED: confirm on Qwen or configure auto_confirm_age and birth_year");
    if (age === "year_unavailable") throw new Error("QWEN_BIRTH_YEAR_UNAVAILABLE");
    if (age === "submitted") ageSubmitted = true;
    if (age !== "absent") { await sleep(250); continue; }
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

async function _cwaQwenSubmitOnce(debuggee, text, deadlineAt, message = {}) {
  const written = await _cwaQwenEvaluate(debuggee, _cwaQwenComposerExpression(text));
  if (written?.written !== true) throw new Error("QWEN_COMPOSER_WRITE_FAILED");

  while (performance.now() < deadlineAt) {
    await _cwaQwenWaitForComposer(debuggee, deadlineAt, message);
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
  if (Number.isInteger(baseline?.answerCount)) {
    if (snapshot.answerCount <= baseline.answerCount) return null;
    return snapshot.texts.at(-1) || null;
  }
  for (let index = snapshot.texts.length - 1; index >= 0; index -= 1) {
    const text = snapshot.texts[index];
    if (typeof text === "string" && text.trim() && !baseline.has(text)) return text.trim();
  }
  return null;
}

async function _cwaQwenWaitForFinalText(debuggee, text, baseline, deadlineAt, onText = null) {
  let lastText = null;
  let stableSince = null;
  let idleSince = null;
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
    // An absent Stop button can be a temporary phase transition.
    // Only explicit idle observations count towards a continuous quiet window.
    if (snapshot?.generating === false) {
      if (idleSince === null) idleSince = performance.now();
    } else {
      idleSince = null;
    }
    const candidate = _cwaQwenLatestNewText(snapshot, baseline);
    if (candidate !== null && candidate === lastText) {
      if (stableSince === null) stableSince = performance.now();
    } else {
      if (candidate !== null && onText) onText(candidate);
      lastText = candidate;
      stableSince = candidate === null ? null : performance.now();
    }
    const quietlySettled = candidate !== null &&
      idleSince !== null && stableSince !== null &&
      performance.now() - Math.max(idleSince, stableSince) >= CWA_QWEN_STABLE_MS;
    if (snapshot?.generating === false && quietlySettled) {
      return { text: candidate, url: snapshot.url };
    }
    await sleep(250);
  }
  throw new Error(
    "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "PAGE_FINALITY_TIMEOUT"
  );
}


function _cwaQwenAuthProbeExpression() {
  return "(() => {" +
    "let state=null;" +
    "try{state=JSON.parse(localStorage.getItem('qwen_access_token_state')||'null');}catch{}" +
    "const token=[state?.access_token,state?.accessToken,state?.token,state?.value," +
      "state?.state?.token,localStorage.getItem('token')].find(" +
      "value=>typeof value==='string'&&value.length>8)||null;" +
    "const expiresAt=[state?.expires_at,state?.expiresAt,state?.at_expire_time," +
      "localStorage.getItem('at_expire_time')].find(value=>value!=null)||null;" +
    "return {token,expiresAt,userAgent:navigator.userAgent,language:navigator.language};" +
  "})()";
}

async function _cwaQwenExportAuth(message) {
  if (message?.allowAuthExport !== true || message?.operation !== "export_auth") {
    throw new Error("QWEN_AUTH_EXPORT_NOT_AUTHORIZED");
  }
  const candidates = await chrome.tabs.query({url: CWA_QWEN_ORIGIN + "/*"});
  const tab = candidates.find(tab => tab.active) || candidates[0];
  if (!tab || !Number.isInteger(tab.id) || !_cwaQwenIsUrl(tab.url || "")) {
    throw new Error("QWEN_AUTH_TAB_REQUIRED");
  }
  const debuggee = {tabId: tab.id};
  let attached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    let probe = await _cwaQwenEvaluate(debuggee, _cwaQwenAuthProbeExpression());
    let snapshotExpiry = Number(probe?.expiresAt);
    if (snapshotExpiry > 0 && snapshotExpiry < 1e12) snapshotExpiry *= 1000;
    if (snapshotExpiry > 0 && snapshotExpiry <= Date.now() + 60000) {
      const previousToken = probe?.token;
      await chrome.tabs.reload(tab.id);
      const renewDeadline = Date.now() + 15000;
      let renewed = false;
      while (Date.now() < renewDeadline) {
        await new Promise(resolve => setTimeout(resolve, 250));
        try {
          const next = await _cwaQwenEvaluate(debuggee, _cwaQwenAuthProbeExpression());
          let expiry = Number(next?.expiresAt);
          if (expiry > 0 && expiry < 1e12) expiry *= 1000;
          if (next?.token && next.token !== previousToken && expiry > Date.now() + 60000) {
            probe = next;
            renewed = true;
            break;
          }
        } catch {}
      }
      if (!renewed) throw new Error("QWEN_AUTH_RENEWAL_REQUIRES_USER");
    }
    if (typeof probe?.token !== "string" || !probe.token) {
      throw new Error("QWEN_AUTH_ACCESS_TOKEN_UNAVAILABLE");
    }
    // Scoped to the Qwen site. Neither Google nor other Chrome cookies are read.
    const cookieResponse = await _cwaBaseSendCommand(
      debuggee, "Network.getCookies", {urls: [CWA_QWEN_ORIGIN + "/"]}
    );
    const cookies = {};
    for (const cookie of cookieResponse?.cookies || []) {
      if (typeof cookie?.name !== "string" || typeof cookie?.value !== "string") continue;
      if (!["chat.qwen.ai", ".chat.qwen.ai", ".qwen.ai", "qwen.ai"].includes(cookie.domain)) continue;
      cookies[cookie.name] = cookie.value;
    }
    let expiresAt = Number(probe.expiresAt);
    if (!Number.isFinite(expiresAt) || expiresAt <= 0) expiresAt = null;
    else if (expiresAt > 1e12) expiresAt /= 1000;
    return {
      providerId: CWA_QWEN_PROVIDER_ID,
      operation: "auth_snapshot",
      accessToken: probe.token,
      cookies,
      expiresAt,
      headers: {"user-agent":probe.userAgent || "", "accept-language":probe.language || "en-US", "origin":CWA_QWEN_ORIGIN, "referer":CWA_QWEN_ORIGIN + "/"}
    };
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _cwaQwenHandleTurn(message) {
  if (message?.operation === "export_auth") return _cwaQwenExportAuth(message);
  if (message?.type !== "turn") throw new Error("QWEN_TURN_TYPE_REQUIRED");
  if (typeof message?.text !== "string" || !message.text.trim()) throw new Error("QWEN_TEXT_REQUIRED");
  if ((Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0) ||
      message?.conversationMode != null || message?.modelProfile != null ||
      message?.browserAuthorityLeaseId != null) {
    throw new Error("QWEN_BROWSER_UNSUPPORTED_OPTION");
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
  let networkStream = null;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    await _cwaQwenWaitForComposer(debuggee, deadlineAt, message);

    const before = await _cwaQwenEvaluate(debuggee, _cwaQwenSnapshotExpression(message.text));
    const baseline = {answerCount: before?.answerCount || 0};

    if (message.streamNetwork === true) networkStream = await _cwaQwenObserveStream(debuggee, message);
    await _cwaQwenSubmitOnce(debuggee, message.text, deadlineAt, message);
    try {
      const final = await _cwaQwenWaitForFinalText(
        debuggee,
        message.text,
        baseline,
        deadlineAt,
        message.streamTextObservations === true ? (text) => postNative({
          protocol: BRIDGE_PROTOCOL_VERSION,
          type: "turn_event",
          request_id: message.request_id,
          event: {providerId: CWA_QWEN_PROVIDER_ID, type: "text_snapshot", text}
        }) : null
      );
      if (networkStream) await networkStream.verify();
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
        automaticWriteRetry: false,
        networkStreamVerified: networkStream !== null
      };
    } catch (error) {
      throw _cwaQwenPostSubmitAmbiguousError(error);
    }
  } finally {
    if (networkStream) networkStream.close();
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

registerProductProviderTurnHandler(
  CWA_QWEN_PROVIDER_ID,
  _cwaQwenHandleTurn
);
