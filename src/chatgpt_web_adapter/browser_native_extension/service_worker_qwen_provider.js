
const CWA_QWEN_PROVIDER_ID = "qwen";
const CWA_QWEN_ORIGIN = "https://chat.qwen.ai";
const CWA_QWEN_RUNTIME_TAB_KEY = "qwenWebRuntimeTabIdV1";
const CWA_QWEN_ROUTE_MAP_KEY = "qwenWebConversationRoutesV1";
// DOM quiet time is an observation heuristic, not authoritative server finality.
// Never shorten it just because Qwen briefly hides the Stop button.
// UI-idle finality is only a heuristic. Avoid the old 9-second extra wait
// while retaining a window longer than Qwen's observed short phase gaps.
const CWA_QWEN_STABLE_MS = 3500;
const CWA_QWEN_PRE_SUBMIT_READY_MS = 1500;

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

async function _cwaQwenEnsureTab(conversationId, foregroundTab = false) {
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
    tab = await chrome.tabs.create({url: CWA_QWEN_ORIGIN + "/", active: foregroundTab === true});
  }
  if (!tab || !Number.isInteger(tab.id)) {
    throw new Error(conversationId === null
      ? "QWEN_NEW_CHAT_TAB_NOT_OPEN: open a new Qwen chat and finish account setup yourself"
      : "QWEN_CONTINUATION_TAB_NOT_OPEN: open the existing conversation in Qwen");
  }
  if (foregroundTab === true && tab.active !== true) {
    // Explicit opt-in to avoid background-tab throttling during a turn.
    // Activation changes only the selected Chrome tab; never open a new user
    // prompt or send anything while performing the activation.
    tab = await chrome.tabs.update(tab.id, {active: true});
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
    // Dual-response feedback is a required choice in Qwen, not a final reply.
    // Never type a new user turn while the previous one awaits that choice.
    const pageText = document.body?.innerText || "";
    const dualPending = pageText.includes("This feedback will help us evaluate and improve Qwen's performance.") &&
      pageText.includes("Which response do you prefer?");
    if (dualPending) return {found: false, dualPending: true};
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
    // Only coarse UI states leave this DOM evaluation; never expose prompt text,
    // message content beyond normal stream, cookies, or page HTML in diagnostics.
    const composer = Array.from(document.querySelectorAll(
      "textarea.message-input-textarea,textarea[placeholder='How can I help you today?']"
    )).find(visible);
    const editorState = !composer ? "missing" : composer.value === prompt
      ? "prompt_present" : !composer.value ? "empty" : "different";
    const control = Array.from(document.querySelectorAll(
      "button.send-button,.chat-prompt-send-button button,div.message-input-right-button-send button"
    )).find(visible);
    const sendState = !control ? "missing" :
      control.disabled || control.getAttribute("aria-disabled") === "true"
        ? "disabled" : "enabled";
    const pageVisibility = document.visibilityState === "hidden" ? "hidden" : "visible";
    const pageText = document.body?.innerText || "";
    const dualPending = pageText.includes("This feedback will help us evaluate and improve Qwen's performance.") &&
      pageText.includes("Which response do you prefer?");
    // Keep answer candidates on Qwen's page. No inferred canonical index and
    // no automatic feedback vote or persistence of user conversations.
    return {url: location.href, texts, generating, answerCount: answers.length,
      editorState, sendState, pageVisibility, dualPending};
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
  // Read the age dialog without mutating it. Synthetic Element.click() is not a
  // reliable substitute for an actual pointer interaction in the Qwen UI.
  const expression = function(year, allow, submitted) {
    const dialog = document.querySelector('.age-confirmation-modal[role="dialog"]');
    if (!dialog || dialog.getAttribute?.("aria-hidden") === "true" ||
        getComputedStyle(dialog).display === "none" ||
        getComputedStyle(dialog).visibility === "hidden") return "absent";
    const rect = dialog.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return "absent";
    if (!allow) return "required";
    if (submitted) return "waiting";
    const target = (element, action) => {
      if (!element || element.disabled || element.getAttribute?.("aria-disabled") === "true") {
        return "age_control_unavailable";
      }
      const r = element.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return "age_control_unavailable";
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 ||
          x >= window.innerWidth || y >= window.innerHeight) return "age_control_unavailable";
      return {action, x, y};
    };
    const selected = dialog.querySelector('.age-confirmation-year .qwen-chat-v2-dropdown-menu-select-label');
    if (!selected) return "year_selector_missing";
    if (selected.textContent.trim() !== String(year)) {
      const menu = document.querySelector('.qwen-chat-v2-dropdown-menu-popup[role="menu"]');
      if (menu) {
        const option = Array.from(menu.querySelectorAll('[role="menuitem"]')).find(
          el => el.textContent.trim() === String(year));
        return option ? target(option, "select_year") : "year_unavailable";
      }
      return target(
        dialog.querySelector('.age-confirmation-year .qwen-chat-v2-dropdown-menu-trigger'),
        "open_years"
      );
    }
    const button = Array.from(dialog.querySelectorAll('button')).find(el =>
      /^(continue|продолжить|continuer|继续|繼續)$/i.test(el.textContent.trim()));
    if (!button) return "continue_button_missing";
    return target(button, "confirm_age");
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(year) + "," + (allow === true) + "," + (submitted === true) + ")";
}

async function _cwaQwenAgeTrustedClick(debuggee, target) {
  if (!target || !["open_years", "select_year", "confirm_age"].includes(target.action) ||
      !Number.isFinite(target.x) || !Number.isFinite(target.y) ||
      target.x < 0 || target.y < 0) {
    throw new Error("QWEN_AGE_CLICK_TARGET_INVALID");
  }
  const point = {x: target.x, y: target.y};
  // CDP input uses Chrome's input pipeline. No Qwen API calls, age bypass, or
  // second submission of the user's text. Only the explicit age dialog.
  await _cwaBaseSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseMoved", ...point, button: "none"
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mousePressed", ...point, button: "left", clickCount: 1
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchMouseEvent", {
    type: "mouseReleased", ...point, button: "left", clickCount: 1
  });
}

// Age verification can appear before or after Send. An apparent click is not
// confirmation; the dialog must actually disappear before the turn proceeds.
async function _cwaQwenHandleAgeGate(debuggee, message, state) {
  const age = await _cwaQwenEvaluate(
    debuggee,
    _cwaQwenAgeExpression(message.birthYear, message.autoConfirmAge, state.submitted === true)
  );
  if (age === "absent") {
    state.since = null;
    state.submitted = false;
    state.lastAction = null;
    return false;
  }
  if (age === "required") throw new Error("QWEN_AGE_CONFIRMATION_REQUIRED: confirm on Qwen or explicitly provide --auto-confirm-age --birth-year");
  if (age === "year_unavailable") throw new Error("QWEN_BIRTH_YEAR_UNAVAILABLE");
  if (age === "year_selector_missing" || age === "continue_button_missing") {
    throw new Error("QWEN_AGE_DIALOG_STRUCTURE_CHANGED: manual confirmation on Qwen required");
  }
  const now = performance.now();
  if (state.since === null || state.since === undefined) state.since = now;
  if (now - state.since >= 12000) {
    throw new Error("QWEN_AGE_CONFIRMATION_STALLED: age dialog remains open after click; open the Qwen tab for manual verification; no prompt was resent");
  }
  if (age && typeof age === "object" && age.action) {
    if (!["open_years", "select_year", "confirm_age"].includes(age.action)) {
      throw new Error("QWEN_AGE_DIALOG_STRUCTURE_CHANGED");
    }
    // Avoid repeatedly clicking a still-rendering dropdown. Never repeat the
    // final Continue action: verification could be in flight.
    if (age.action === "confirm_age") {
      state.submitted = true;
      await _cwaQwenAgeTrustedClick(debuggee, age);
    } else if (state.lastAction !== age.action ||
               now - (state.lastActionAt ?? -Infinity) >= 1000) {
      state.lastAction = age.action;
      state.lastActionAt = now;
      await _cwaQwenAgeTrustedClick(debuggee, age);
    }
  } else if (age !== "waiting" && age !== "age_control_unavailable") {
    throw new Error("QWEN_AGE_DIALOG_STRUCTURE_CHANGED");
  }
  return true;
}

async function _cwaQwenWaitForComposer(debuggee, deadlineAt, message = {}, ageState = {}, settleMs = CWA_QWEN_PRE_SUBMIT_READY_MS) {
  // A newly created background tab may mount the age modal shortly AFTER the
  // textarea. Do not type or click Send until both remain ready for a while.
  let readySince = null;
  while (performance.now() < deadlineAt) {
    try {
      if (await _cwaQwenHandleAgeGate(debuggee, message, ageState)) {
        readySince = null;
        await sleep(250);
        continue;
      }
      const snapshot = await _cwaQwenEvaluate(debuggee, _cwaQwenComposerExpression());
      if (snapshot?.dualPending === true) {
        throw new Error("QWEN_DUAL_RESPONSE_SELECTION_REQUIRED: choose Response 1 or Response 2 in Qwen before continuing; neither is canonical yet");
      }
      if (snapshot?.found === true) {
        if (readySince === null) readySince = performance.now();
        if (performance.now() - readySince >= settleMs) return;
      } else {
        readySince = null;
      }
    } catch (error) {
      if (!_cwaQwenDebuggerDetached(error)) throw error;
      readySince = null;
      await _cwaQwenReattachForObservation(debuggee, deadlineAt);
    }
    await sleep(250);
  }
  throw new Error("QWEN_COMPOSER_NOT_READY");
}

function _cwaQwenSubmitExpression(text, execute = false) {
  // The send button's DOM click is intentional: CDP mouse dispatch on an
  // inactive Chrome tab was acknowledged yet never started a Qwen turn.
  // Keep the readiness check side-effect-free; the write call happens once.
  const expression = function(requestedText, commit) {
    const visible = (el) => {
      if (!(el instanceof Element)) return false;
      const r = el.getBoundingClientRect(), style = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const dialog = document.querySelector('.age-confirmation-modal[role="dialog"]');
    if (dialog && visible(dialog)) return {ready: false, reason: "age_dialog_active"};
    const pageText = document.body?.innerText || "";
    if (pageText.includes("This feedback will help us evaluate and improve Qwen's performance.") &&
        pageText.includes("Which response do you prefer?")) {
      return {ready: false, reason: "dual_response_selection_required"};
    }
    const composer = Array.from(document.querySelectorAll(
      "textarea.message-input-textarea,textarea[placeholder='How can I help you today?']"
    )).find(visible);
    if (!composer) return {ready: false, reason: "composer_not_found"};
    if (composer.value !== requestedText) {
      return {ready: false, reason: "composer_value_mismatch"};
    }
    if (Array.from(document.querySelectorAll("button.stop-button")).some(visible)) {
      return {ready: false, reason: "generation_active"};
    }
    const control = Array.from(document.querySelectorAll(
      "button.send-button,.chat-prompt-send-button button,div.message-input-right-button-send button"
    )).find(el => visible(el) && !el.disabled && el.getAttribute("aria-disabled") !== "true");
    if (!control) return {ready: false, reason: "send_control_not_ready"};
    if (!commit) return {ready: true};
    // The control can become detached in between checking and executing.
    if (!control.isConnected || !composer.isConnected) {
      return {ready: false, reason: "composer_remounted_before_send"};
    }
    control.click();
    return {ready: true, submitted: true, mechanism: "dom_click"};
  };
  return "(" + expression.toString() + ")(" + JSON.stringify(text) + "," + (execute === true) + ")";
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

// Passive POST metadata only; never inspect request bodies or issue a fetch.
// This establishes whether the browser even attempted a Qwen API write.
// DOM visibility is not evidence that a message was actually sent.
async function _cwaQwenObserveWriteLifecycle(debuggee) {
  const watched = new Map();
  let enabled = false;
  let kind = "none", status = "unobserved", responseCode = null;
  const listener = (source, method, params) => {
    if (source?.tabId !== debuggee.tabId) return;
    if (method === "Network.requestWillBeSent") {
      try {
        const request = params?.request;
        if (request?.method !== "POST" || typeof request.url !== "string") return;
        const url = new URL(request.url);
        if (url.origin !== CWA_QWEN_ORIGIN) return;
        const path = url.pathname.endsWith("/") ? url.pathname.slice(0, -1) : url.pathname;
        const nextKind = path === "/api/v2/chat/completions"
          ? "completion" : path === "/api/v2/chats/new" ? "create" : null;
        if (!nextKind) return;
        watched.set(params.requestId, nextKind);
        kind = nextKind;
        status = "requested";
        responseCode = null;
      } catch {}
    } else if (watched.has(params?.requestId)) {
      if (method === "Network.responseReceived") {
        const code = params?.response?.status;
        responseCode = Number.isInteger(code) && code >= 100 && code <= 599 ? code : null;
        status = "responded";
      } else if (method === "Network.loadingFinished") {
        status = "finished";
      } else if (method === "Network.loadingFailed") {
        status = "failed";
      }
    }
  };
  chrome.debugger.onEvent.addListener(listener);
  try {
    await _cwaBaseSendCommand(debuggee, "Network.enable");
    enabled = true;
  } catch {
    chrome.debugger.onEvent.removeListener(listener);
  }
  return {
    snapshot() {
      return enabled ? {kind, status, responseCode} :
        {kind:"unknown", status:"unavailable", responseCode:null};
    },
    close() {
      if (enabled) chrome.debugger.onEvent.removeListener(listener);
      watched.clear();
    }
  };
}

async function _cwaQwenSubmitOnce(debuggee, text, deadlineAt, message = {}, ageState = {}, readyConfirmed = false) {
  // The caller that captured the baseline has ALREADY awaited a stable
  // composer. Do not pay another 1.5-second fence per message.
  if (!readyConfirmed) {
    await _cwaQwenWaitForComposer(debuggee, deadlineAt, message, ageState);
  } else if (await _cwaQwenHandleAgeGate(debuggee, message, ageState)) {
    throw new Error("QWEN_PRE_SUBMIT_AGE_GATE_REAPPEARED: wait for age verification before typing");
  }
  const written = await _cwaQwenEvaluate(debuggee, _cwaQwenComposerExpression(text));
  if (written?.written !== true) throw new Error("QWEN_COMPOSER_WRITE_FAILED");

  // The send control may become enabled slightly after React handles input.
  // A reset/mismatched composer is a PRE-click failure, not a reason to
  // spin for the entire bridge timeout or silently type into a new page.
  const sendDeadlineAt = Math.min(deadlineAt, performance.now() + 6000);
  while (performance.now() < sendDeadlineAt) {
    const gate = await _cwaQwenHandleAgeGate(debuggee, message, ageState);
    if (gate) {
      throw new Error(
        "QWEN_PRE_SUBMIT_AGE_GATE_REAPPEARED: age verification changed the page after typing; no Send click was attempted"
      );
    }
    const submit = await _cwaQwenEvaluate(debuggee, _cwaQwenSubmitExpression(text));
    if (submit?.ready === true) {
      // Single send attempt through the site's own DOM control; unlike a
      // background-tab pointer event, this works without tab activation.
      // Evaluate may click before its response is lost: never replay it.
      let committed;
      try {
        committed = await _cwaQwenEvaluate(
          debuggee, _cwaQwenSubmitExpression(text, true)
        );
      } catch (error) {
        throw _cwaQwenPostSubmitAmbiguousError(error);
      }
      if (committed?.submitted === true && committed?.mechanism === "dom_click") return;
      throw new Error(
        "QWEN_PRE_SUBMIT_" + (committed?.reason || "COMMIT_UNCONFIRMED").toUpperCase()
      );
    }
    if (submit?.reason !== "send_control_not_ready") {
      throw new Error("QWEN_PRE_SUBMIT_" + (submit?.reason || "STATE_UNKNOWN").toUpperCase());
    }
    await sleep(150);
  }
  throw new Error("QWEN_PRE_SUBMIT_SEND_CONTROL_NOT_READY");
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

async function _cwaQwenWaitForFinalText(debuggee, text, baseline, deadlineAt, onText = null, message = {}, ageState = {}, writeObserver = null) {
  let lastText = null;
  let stableSince = null;
  let idleSince = null;
  let unobservedSince = null;
  while (performance.now() < deadlineAt) {
    let snapshot;
    let gateActive = false;
    try {
      // The gate can open after Send and cause navigation/debugger detachment.
      // Recover observation, but never replay the submitted prompt.
      gateActive = await _cwaQwenHandleAgeGate(debuggee, message, ageState);
      if (!gateActive) {
        snapshot = await _cwaQwenEvaluate(debuggee, _cwaQwenSnapshotExpression(text));
      }
    } catch (error) {
      if (!_cwaQwenDebuggerDetached(error)) throw error;
      await _cwaQwenReattachForObservation(debuggee, deadlineAt);
      await sleep(250);
      continue;
    }
    if (gateActive) {
      idleSince = null;
      stableSince = null;
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
    // Two candidates and a required feedback choice are not one assistant
    // response. Never stream an arbitrary last DOM node as authoritative.
    if (snapshot?.dualPending === true) {
      throw new Error("QWEN_DUAL_RESPONSE_SELECTION_REQUIRED: Qwen displayed Response 1 and Response 2; choose one in the tab to establish the continuation; no automatic vote or text replay");
    }
    const candidate = _cwaQwenLatestNewText(snapshot, baseline);
    // A route change proves the UI navigated, NOT that the answer is being
    // generated. A blank new-chat route must not mask an absent answer for the
    // rest of the 120-second turn deadline.
    if (candidate !== null || snapshot?.generating === true) {
      unobservedSince = null;
    } else if (snapshot?.generating === false && candidate === null) {
      if (unobservedSince === null) unobservedSince = performance.now();
      const network = writeObserver?.snapshot?.() ||
        {kind:"unknown", status:"unavailable", responseCode:null};
      const networkObserved = network.kind === "create" || network.kind === "completion";
      const routeAdvanced = typeof snapshot?.url === "string" &&
        snapshot.url !== baseline?.initialUrl;
      // No observed POST and no route change: fail promptly. A Qwen POST or
      // navigation gets a longer window for background-page remounts.
      const limit = networkObserved || routeAdvanced ? 20000 :
        network.kind === "none" ? 8000 : 15000;
      if (performance.now() - unobservedSince >= limit) {
        const editor = ["prompt_present","empty","different","missing"].includes(snapshot?.editorState)
          ? snapshot.editorState : "unknown";
        const send = ["enabled","disabled","missing"].includes(snapshot?.sendState)
          ? snapshot.sendState : "unknown";
        const visibility = ["visible","hidden"].includes(snapshot?.pageVisibility)
          ? snapshot.pageVisibility : "unknown";
        const stage = networkObserved || routeAdvanced ?
          "QWEN_POST_SUBMIT_UI_UNOBSERVED_AFTER_WRITE_OR_NAVIGATION" :
          "QWEN_POST_SUBMIT_START_UNOBSERVED";
        throw new Error(
          stage + ": no response DOM or generation observed; " +
          "write=" + network.kind + " network=" + network.status +
          " http=" + (network.responseCode || "unknown") +
          " routeChanged=" + routeAdvanced +
          " editor=" + editor + " send=" + send +
          " visibility=" + visibility +
          "; no automatic replay; inspect Qwen before another send"
        );
      }
    }
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
  const tab = await _cwaQwenEnsureTab(conversationId, message.foregroundTab === true);
  const initialUrl = tab.url || CWA_QWEN_ORIGIN + "/";
  const debuggee = { tabId: tab.id };
  let attached = false;
  let networkStream = null;
  let writeObserver = null;
  const ageState = {};

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    // New tabs need a longer age-dialog fence; existing confirmed chats can
    // reuse their mounted composer without the full onboarding delay.
    await _cwaQwenWaitForComposer(
      debuggee, deadlineAt, message, ageState,
      conversationId === null ? CWA_QWEN_PRE_SUBMIT_READY_MS : 350
    );

    const before = await _cwaQwenEvaluate(debuggee, _cwaQwenSnapshotExpression(message.text));
    const baseline = {
      answerCount: before?.answerCount || 0,
      initialUrl: before?.url || initialUrl
    };

    // Enable passive write metadata before the one-and-only Send.
    writeObserver = await _cwaQwenObserveWriteLifecycle(debuggee);
    if (message.streamNetwork === true) networkStream = await _cwaQwenObserveStream(debuggee, message);
    await _cwaQwenSubmitOnce(debuggee, message.text, deadlineAt, message, ageState, true);
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
        }) : null,
        message,
        ageState,
        writeObserver
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
    if (writeObserver) writeObserver.close();
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

registerProductProviderTurnHandler(
  CWA_QWEN_PROVIDER_ID,
  _cwaQwenHandleTurn
);
