// Minimal provider #2 proof: DeepSeek Web text turns.
//
// This module deliberately bypasses the ChatGPT native-turn lifecycle. It owns
// only page-driven text new-chat/continuation for chat.deepseek.com and registers
// one handler with the provider turn registry in service_worker.js.
//
// No undocumented DeepSeek HTTP endpoint is used. Conversation continuation is
// keyed by a local opaque id mapped to the exact final DeepSeek URL observed
// after the first completed turn.

const DEEPSEEK_WEB_ORIGIN = "https://chat.deepseek.com";
const DEEPSEEK_WEB_PROVIDER_ID = "deepseek";
const DEEPSEEK_WEB_CONVERSATION_URLS_KEY = "deepseekWebConversationUrlsV1";
const DEEPSEEK_WEB_STABLE_FINALITY_MS = 9_000;
const DEEPSEEK_WEB_POLL_MS = 1_000;
const DEEPSEEK_WEB_SUBMIT_OBSERVATION_MS = 15_000;

function _deepseekWebIsUrl(value) {
  if (typeof value !== "string" || !value.trim()) return false;
  try {
    return new URL(value).origin === DEEPSEEK_WEB_ORIGIN;
  } catch {
    return false;
  }
}

async function _deepseekWebConversationUrlMap() {
  const value = await chrome.storage.local.get(DEEPSEEK_WEB_CONVERSATION_URLS_KEY);
  const mapping = value?.[DEEPSEEK_WEB_CONVERSATION_URLS_KEY];
  if (!mapping || typeof mapping !== "object" || Array.isArray(mapping)) return {};
  const safe = {};
  for (const [key, url] of Object.entries(mapping)) {
    if (typeof key !== "string" || !key.trim() || !_deepseekWebIsUrl(url)) continue;
    safe[key] = url;
  }
  return safe;
}

async function _deepseekWebTargetUrl(conversationId) {
  if (!conversationId) return `${DEEPSEEK_WEB_ORIGIN}/`;
  const mapping = await _deepseekWebConversationUrlMap();
  const url = mapping[conversationId];
  if (!_deepseekWebIsUrl(url)) {
    throw new Error("DEEPSEEK_CONTINUATION_ID_UNKNOWN");
  }
  return url;
}

async function _deepseekWebStoreConversationUrl(conversationId, url) {
  if (typeof conversationId !== "string" || !conversationId.trim()) {
    throw new Error("DEEPSEEK_CONVERSATION_ID_REQUIRED");
  }
  if (!_deepseekWebIsUrl(url)) {
    throw new Error("DEEPSEEK_FINAL_URL_INVALID");
  }
  const mapping = await _deepseekWebConversationUrlMap();
  mapping[conversationId] = url;
  await chrome.storage.local.set({
    [DEEPSEEK_WEB_CONVERSATION_URLS_KEY]: mapping
  });
}

async function _deepseekWebSnapshot(debuggee) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const visible = (el) => {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.visibility !== "hidden" &&
          style.display !== "none";
      };

      const composerSelectors = [
        "textarea#chat-input",
        'textarea[placeholder*="DeepSeek"]',
        "textarea"
      ];
      const composer = composerSelectors
        .map((selector) => document.querySelector(selector))
        .find((el) => visible(el)) || null;

      const responseSelectorGroups = [
        ".ds-markdown.ds-assistant-message-main-content",
        ".ds-markdown.ds-markdown--block",
        ".ds-markdown"
      ];
      let responseNodes = [];
      for (const selector of responseSelectorGroups) {
        const nodes = Array.from(document.querySelectorAll(selector))
          .filter((el) => visible(el));
        if (nodes.length) {
          responseNodes = nodes;
          break;
        }
      }
      const assistantTexts = responseNodes
        .map((el) => String(el.innerText || el.textContent || "").trim())
        .filter(Boolean);

      const stopVisible = Array.from(
        document.querySelectorAll("button,[role='button']")
      ).some((el) => {
        if (!visible(el)) return false;
        const label = [
          el.getAttribute("aria-label"),
          el.getAttribute("title"),
          el.textContent
        ].filter(Boolean).join(" ").toLowerCase();
        return /(^|\\s)(stop|cancel|停止|中止)(\\s|$)/i.test(label);
      });

      const composerDisabled = composer == null ||
        composer.disabled === true ||
        composer.getAttribute("aria-disabled") === "true" ||
        composer.getAttribute("aria-busy") === "true";

      return {
        composerReady: composer != null && !composerDisabled,
        composerValue: composer && "value" in composer
          ? String(composer.value || "")
          : "",
        assistantTexts,
        stopVisible,
        href: location.href
      };
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  const value = result?.result?.value;
  return value && typeof value === "object"
    ? value
    : {
        composerReady: false,
        composerValue: "",
        assistantTexts: [],
        stopVisible: false,
        href: null
      };
}

async function _deepseekWebWaitForComposer(debuggee, timeoutMs) {
  const startedAt = performance.now();
  while (elapsedMs(startedAt) < timeoutMs) {
    const snapshot = await _deepseekWebSnapshot(debuggee);
    if (snapshot.composerReady === true) return snapshot;
    await sleep(250);
  }
  throw new Error("DEEPSEEK_COMPOSER_NOT_READY");
}

async function _deepseekWebFocusComposer(debuggee) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const visible = (el) => {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      };
      const selectors = [
        "textarea#chat-input",
        'textarea[placeholder*="DeepSeek"]',
        "textarea"
      ];
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (!visible(el)) continue;
        el.focus();
        return selector;
      }
      return null;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  const selector = result?.result?.value;
  if (typeof selector !== "string" || !selector) {
    throw new Error("DEEPSEEK_COMPOSER_NOT_FOUND");
  }
  return selector;
}

async function _deepseekWebClearComposer(debuggee) {
  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "a",
    code: "KeyA",
    modifiers: 2,
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "a",
    code: "KeyA",
    modifiers: 2,
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Backspace",
    code: "Backspace",
    windowsVirtualKeyCode: 8,
    nativeVirtualKeyCode: 8
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Backspace",
    code: "Backspace",
    windowsVirtualKeyCode: 8,
    nativeVirtualKeyCode: 8
  });
}

async function _deepseekWebSendButtonPoint(debuggee) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression: `(() => {
      const visible = (el) => {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 &&
          rect.height > 0 &&
          style.visibility !== "hidden" &&
          style.display !== "none" &&
          style.pointerEvents !== "none";
      };
      const composer = document.querySelector("textarea#chat-input") ||
        document.querySelector('textarea[placeholder*="DeepSeek"]') ||
        document.querySelector("textarea");
      if (!visible(composer)) return null;
      const composerRect = composer.getBoundingClientRect();
      const selectors = [
        "div[role='button'].ds-button--primary.ds-button--filled",
        "div[role='button'].ds-button--primary.ds-button--circle",
        "button[type='submit']"
      ];
      const candidates = [];
      for (const selector of selectors) {
        for (const button of document.querySelectorAll(selector)) {
          if (!visible(button)) continue;
          if (
            button.getAttribute("aria-disabled") === "true" ||
            button.disabled === true
          ) continue;
          const rect = button.getBoundingClientRect();
          const dx = (rect.left + rect.width / 2) -
            (composerRect.left + composerRect.width / 2);
          const dy = (rect.top + rect.height / 2) -
            (composerRect.top + composerRect.height / 2);
          candidates.push({
            selector,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            distance: Math.hypot(dx, dy)
          });
        }
      }
      candidates.sort((a, b) => a.distance - b.distance);
      return candidates[0] || null;
    })()`,
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value || null;
}

async function _deepseekWebClick(debuggee, point) {
  for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
    const payload = {
      type,
      x: point.x,
      y: point.y
    };
    if (type !== "mouseMoved") {
      payload.button = "left";
      payload.clickCount = 1;
    }
    await _cwaBaseSendCommand(debuggee, "Input.dispatchMouseEvent", payload);
  }
}

async function _deepseekWebSubmit(debuggee) {
  const point = await _deepseekWebSendButtonPoint(debuggee);
  if (
    point &&
    Number.isFinite(point.x) &&
    Number.isFinite(point.y)
  ) {
    await _deepseekWebClick(debuggee, point);
    return {
      strategy: "send_button_click",
      selector: typeof point.selector === "string" ? point.selector : null
    };
  }

  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Enter",
    code: "Enter",
    text: "\r",
    unmodifiedText: "\r",
    windowsVirtualKeyCode: 13,
    nativeVirtualKeyCode: 13
  });
  await _cwaBaseSendCommand(debuggee, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Enter",
    code: "Enter",
    windowsVirtualKeyCode: 13,
    nativeVirtualKeyCode: 13
  });
  return { strategy: "enter_fallback", selector: null };
}

function _deepseekWebLastText(snapshot) {
  const texts = Array.isArray(snapshot?.assistantTexts)
    ? snapshot.assistantTexts
    : [];
  const value = texts.length ? texts[texts.length - 1] : "";
  return typeof value === "string" ? value.trim() : "";
}

async function _deepseekWebWaitForFinalAssistant(
  debuggee,
  baselineSnapshot,
  startedAt,
  timeoutMs
) {
  const baselineTexts = Array.isArray(baselineSnapshot?.assistantTexts)
    ? baselineSnapshot.assistantTexts
    : [];
  const baselineCount = baselineTexts.length;
  const baselineLast = baselineCount
    ? String(baselineTexts[baselineCount - 1] || "").trim()
    : "";

  let firstAssistantObservedAt = null;
  let stableText = "";
  let stableSince = null;
  let lastSnapshot = baselineSnapshot;

  while (elapsedMs(startedAt) < timeoutMs) {
    const snapshot = await _deepseekWebSnapshot(debuggee);
    lastSnapshot = snapshot;
    const texts = Array.isArray(snapshot?.assistantTexts)
      ? snapshot.assistantTexts
      : [];
    const current = _deepseekWebLastText(snapshot);
    const changed = current && (
      texts.length > baselineCount ||
      current !== baselineLast
    );

    if (changed && firstAssistantObservedAt === null) {
      firstAssistantObservedAt = performance.now();
    }

    if (changed && snapshot.stopVisible !== true) {
      if (current === stableText) {
        if (stableSince === null) stableSince = performance.now();
      } else {
        stableText = current;
        stableSince = performance.now();
      }
      if (
        stableSince !== null &&
        performance.now() - stableSince >= DEEPSEEK_WEB_STABLE_FINALITY_MS
      ) {
        return {
          assistantText: current,
          snapshot,
          completionProof: "stable_assistant_dom",
          stableForMs: Math.round(performance.now() - stableSince)
        };
      }
    } else {
      stableText = "";
      stableSince = null;
    }

    if (
      firstAssistantObservedAt === null &&
      elapsedMs(startedAt) >= DEEPSEEK_WEB_SUBMIT_OBSERVATION_MS
    ) {
      throw new Error(
        "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
        "ASSISTANT_RESPONSE_NOT_OBSERVED"
      );
    }

    await sleep(DEEPSEEK_WEB_POLL_MS);
  }

  const suffix = _deepseekWebLastText(lastSnapshot)
    ? "ASSISTANT_NOT_STABLE"
    : "ASSISTANT_RESPONSE_ABSENT";
  throw new Error(
    "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" + suffix
  );
}

async function executeDeepSeekWebTurn(message) {
  const text = typeof message?.text === "string" ? message.text.trim() : "";
  if (!text) throw new Error("DEEPSEEK_TEXT_REQUIRED");
  if (text.length > 200_000) throw new Error("DEEPSEEK_TEXT_TOO_LARGE");

  const conversationId = typeof message?.conversationId === "string" &&
    message.conversationId.trim()
    ? message.conversationId.trim()
    : null;
  const timeoutMs = Number.isFinite(message?.timeoutMs)
    ? Math.max(20_000, Math.min(Number(message.timeoutMs), 300_000))
    : DEFAULT_TIMEOUT_MS;
  const targetUrl = await _deepseekWebTargetUrl(conversationId);

  const startedAt = performance.now();
  let tab = null;
  let attached = false;
  const diagnostics = {
    providerId: DEEPSEEK_WEB_PROVIDER_ID,
    continuation: conversationId !== null,
    composerSelector: null,
    submitStrategy: null,
    submitButtonSelector: null,
    completionProof: null,
    stableForMs: null,
    elapsedMs: null
  };

  try {
    tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab?.id)) {
      throw new Error("DEEPSEEK_RUNTIME_TAB_CREATE_FAILED");
    }
    tab = await _cwaBaseWaitForTabComplete(
      tab.id,
      Math.min(timeoutMs, 45_000)
    );
    if (!_deepseekWebIsUrl(tab?.url || "")) {
      throw new Error("DEEPSEEK_RUNTIME_TAB_WRONG_ORIGIN");
    }

    const debuggee = { tabId: tab.id };
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const baseline = await _deepseekWebWaitForComposer(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );
    diagnostics.composerSelector = await _deepseekWebFocusComposer(debuggee);
    await _deepseekWebClearComposer(debuggee);
    await _cwaBaseSendCommand(debuggee, "Input.insertText", { text });

    const submit = await _deepseekWebSubmit(debuggee);
    diagnostics.submitStrategy = submit.strategy;
    diagnostics.submitButtonSelector = submit.selector;

    const final = await _deepseekWebWaitForFinalAssistant(
      debuggee,
      baseline,
      startedAt,
      timeoutMs
    );
    diagnostics.completionProof = final.completionProof;
    diagnostics.stableForMs = final.stableForMs;
    diagnostics.elapsedMs = elapsedMs(startedAt);

    const finalTab = await chrome.tabs.get(tab.id);
    const finalUrl = typeof finalTab?.url === "string"
      ? finalTab.url
      : final.snapshot?.href;
    if (!_deepseekWebIsUrl(finalUrl)) {
      throw new Error("DEEPSEEK_FINAL_URL_INVALID");
    }

    const resolvedConversationId = conversationId || crypto.randomUUID();
    await _deepseekWebStoreConversationUrl(resolvedConversationId, finalUrl);

    return {
      providerId: DEEPSEEK_WEB_PROVIDER_ID,
      conversationId: resolvedConversationId,
      assistantText: final.assistantText,
      finalUrl,
      tabId: tab.id,
      tabWasActive: Boolean(tab.active),
      elapsedMs: diagnostics.elapsedMs,
      submitStrategy: diagnostics.submitStrategy,
      submitButtonSelector: diagnostics.submitButtonSelector,
      completionProof: diagnostics.completionProof,
      stableForMs: diagnostics.stableForMs
    };
  } finally {
    if (attached && Number.isInteger(tab?.id)) {
      try {
        await chrome.debugger.detach({ tabId: tab.id });
      } catch {
        // Tab may have already closed.
      }
    }
    if (Number.isInteger(tab?.id)) {
      try {
        await chrome.tabs.remove(tab.id);
      } catch {
        // The provider owns only the hidden tab created for this turn.
      }
    }
  }
}

registerProductProviderTurnHandler(
  DEEPSEEK_WEB_PROVIDER_ID,
  executeDeepSeekWebTurn
);
