
const CWA_DEEPSEEK_PROVIDER_ID = "deepseek";
const CWA_DEEPSEEK_ORIGIN = "https://chat.deepseek.com";
const CWA_DEEPSEEK_RUNTIME_TAB_KEY = "deepseekWebRuntimeTabIdV1";
const CWA_DEEPSEEK_ROUTE_MAP_KEY = "deepseekWebConversationRoutesV1";
const CWA_DEEPSEEK_STABLE_MS = 9000;

function _cwaDeepSeekIsUrl(url) {
  try {
    return new URL(url).origin === CWA_DEEPSEEK_ORIGIN;
  } catch {
    return false;
  }
}

async function _cwaDeepSeekStorageGet(key) {
  const result = await chrome.storage.local.get(key);
  return result?.[key];
}

async function _cwaDeepSeekStorageSet(key, value) {
  await chrome.storage.local.set({ [key]: value });
}

async function _cwaDeepSeekStoredRoutes() {
  const value = await _cwaDeepSeekStorageGet(CWA_DEEPSEEK_ROUTE_MAP_KEY);
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

async function _cwaDeepSeekStoreRoute(conversationId, url) {
  if (!_cwaDeepSeekIsUrl(url)) throw new Error("DEEPSEEK_ROUTE_IDENTITY_INVALID");
  const routes = await _cwaDeepSeekStoredRoutes();
  routes[conversationId] = url;
  await _cwaDeepSeekStorageSet(CWA_DEEPSEEK_ROUTE_MAP_KEY, routes);
}

async function _cwaDeepSeekRouteForConversation(conversationId) {
  const routes = await _cwaDeepSeekStoredRoutes();
  const value = routes?.[conversationId];
  return typeof value === "string" && _cwaDeepSeekIsUrl(value) ? value : null;
}

async function _cwaDeepSeekExistingTab() {
  const stored = await _cwaDeepSeekStorageGet(CWA_DEEPSEEK_RUNTIME_TAB_KEY);
  if (!Number.isInteger(stored)) return null;
  try {
    const tab = await chrome.tabs.get(stored);
    return _cwaDeepSeekIsUrl(tab?.url || "") ? tab : null;
  } catch {
    return null;
  }
}

async function _cwaDeepSeekEnsureTab(conversationId) {
  let targetUrl = CWA_DEEPSEEK_ORIGIN + "/";
  if (conversationId !== null) {
    const storedRoute = await _cwaDeepSeekRouteForConversation(conversationId);
    if (storedRoute === null) throw new Error("DEEPSEEK_CONTINUATION_ROUTE_UNKNOWN");
    targetUrl = storedRoute;
  }

  let tab = await _cwaDeepSeekExistingTab();
  if (tab === null) {
    tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab?.id)) throw new Error("DEEPSEEK_RUNTIME_TAB_CREATE_FAILED");
    await _cwaDeepSeekStorageSet(CWA_DEEPSEEK_RUNTIME_TAB_KEY, tab.id);
  } else if (tab.url !== targetUrl) {
    tab = await chrome.tabs.update(tab.id, { url: targetUrl, active: false });
  }

  tab = await _cwaBaseWaitForTabComplete(tab.id, 45000);
  if (!_cwaDeepSeekIsUrl(tab?.url || "")) throw new Error("DEEPSEEK_RUNTIME_TAB_ORIGIN_CHANGED");
  return tab;
}

function _cwaDeepSeekComposerExpression(text) {
  const encodedText = JSON.stringify(text === undefined ? null : text);
  return "(() => {" +
    "const requestedText=" + encodedText + ";" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const candidates=Array.from(document.querySelectorAll(" +
      "'textarea,[contenteditable=\"true\"][role=\"textbox\"],[contenteditable=\"true\"]'" +
    ")).filter((element)=>visible(element)&&element.getAttribute('aria-disabled')!=='true'&&!element.disabled);" +
    "candidates.sort((left,right)=>right.getBoundingClientRect().top-left.getBoundingClientRect().top);" +
    "const composer=candidates[0]||null;" +
    "if(!composer)return {found:false};" +
    "if(requestedText===null)return {found:true,tagName:composer.tagName,contentEditable:composer.isContentEditable===true};" +
    "composer.focus();" +
    "if(composer instanceof HTMLTextAreaElement||composer instanceof HTMLInputElement){" +
      "const proto=composer instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;" +
      "const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;" +
      "if(typeof setter==='function')setter.call(composer,requestedText);else composer.value=requestedText;" +
    "}else{composer.textContent=requestedText;}" +
    "composer.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:requestedText}));" +
    "composer.dispatchEvent(new Event('change',{bubbles:true}));" +
    "return {found:true,written:true};" +
  "})()";
}

function _cwaDeepSeekSnapshotExpression(promptText) {
  const encodedPrompt = JSON.stringify(promptText);
  return "(() => {" +
    "const prompt=" + encodedPrompt + ";" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim();" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const selectorGroups=[[\".ds-markdown.ds-assistant-message-main-content\"],[\".ds-markdown.ds-markdown--block\"],[\"main [class*='markdown']\",\"main [class*='message']\",\"main [class*='prose']\",'main p','main pre']];" +
    "let responseElements=[];" +
    "for(const selectors of selectorGroups){" +
      "const candidates=Array.from(document.querySelectorAll(selectors.join(','))).filter((element)=>visible(element));" +
      "if(candidates.length){responseElements=candidates;break;}" +
    "}" +
    "const texts=[];const seen=new Set();" +
    "for(const element of responseElements){" +
      "if(!visible(element)||element.closest(\"textarea,[contenteditable='true']\"))continue;" +
      "const text=normalize(element.innerText||element.textContent);" +
      "if(!text||text===prompt||text.length<2||seen.has(text))continue;" +
      "seen.add(text);texts.push(text);" +
    "}" +
    "const generating=Array.from(document.querySelectorAll('button,[role=button]')).some((element)=>{" +
      "if(!visible(element))return false;" +
      "const label=normalize(element.getAttribute('aria-label')||element.getAttribute('title')||element.innerText||element.textContent).toLowerCase();" +
      "return label.includes('stop')||label.includes('停止')||label.includes('中止');" +
    "});" +
    "return {url:location.href,texts:texts.slice(-80),generating};" +
  "})()";
}

async function _cwaDeepSeekEvaluate(debuggee, expression) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.exceptionDetails) throw new Error("DEEPSEEK_PAGE_EVALUATION_FAILED");
  return result?.result?.value;
}

async function _cwaDeepSeekWaitForComposer(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaDeepSeekEvaluate(debuggee, _cwaDeepSeekComposerExpression());
    if (snapshot?.found === true) return;
    await sleep(250);
  }
  throw new Error("DEEPSEEK_COMPOSER_NOT_READY");
}

function _cwaDeepSeekSubmitExpression() {
  return "(() => {" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const disabled=(element)=>element.getAttribute('aria-disabled')==='true'||element.disabled===true;" +
    "const composers=Array.from(document.querySelectorAll(" +
      "'textarea,[contenteditable=\\\"true\\\"][role=\\\"textbox\\\"],[contenteditable=\\\"true\\\"]'" +
    ")).filter((element)=>visible(element)&&!disabled(element));" +
    "composers.sort((left,right)=>right.getBoundingClientRect().top-left.getBoundingClientRect().top);" +
    "const composer=composers[0]||null;" +
    "if(!composer)return {found:false,submitted:false};" +
    "const composerRect=composer.getBoundingClientRect();" +
    "let scope=composer.closest('form');" +
    "if(!scope){" +
      "let node=composer.parentElement;" +
      "while(node&&node!==document.body){" +
        "const rect=node.getBoundingClientRect();" +
        "if(rect.height>0&&rect.height<=360&&node.querySelector('button,[role=button]')){scope=node;break;}" +
        "node=node.parentElement;" +
      "}" +
    "}" +
    "if(!scope)return {found:true,submitted:false,reason:'submit_scope_missing'};" +
    "const controls=Array.from(scope.querySelectorAll('button,[role=button]')).filter((element)=>visible(element)&&!disabled(element));" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim().toLowerCase();" +
    "const semantic=controls.find((element)=>{" +
      "const label=normalize(element.getAttribute('aria-label')||element.getAttribute('title')||element.textContent);" +
      "return label==='send'||label.includes('send message')||label.includes('submit')||label.includes('发送');" +
    "});" +
    "const typed=controls.find((element)=>element.matches('button[type=submit]'));" +
    "let control=semantic||typed||null;" +
    "if(!control){" +
      "const nearby=controls.filter((element)=>{" +
        "const rect=element.getBoundingClientRect();" +
        "const verticalOverlap=Math.min(rect.bottom,composerRect.bottom)-Math.max(rect.top,composerRect.top);" +
        "const nearBottom=Math.abs(rect.bottom-composerRect.bottom)<=96;" +
        "return verticalOverlap>0||nearBottom;" +
      "}).sort((left,right)=>right.getBoundingClientRect().right-left.getBoundingClientRect().right);" +
      "control=nearby[0]||null;" +
    "}" +
    "if(!control)return {found:true,submitted:false,reason:'submit_control_missing'};" +
    "control.click();" +
    "return {found:true,submitted:true};" +
  "})()";
}

function _cwaDeepSeekDebuggerDetached(error) {
  const message = String(error?.message || error || "");
  return message.includes("Debugger is not attached to the tab");
}

async function _cwaDeepSeekReattachForObservation(debuggee, deadlineAt) {
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
    "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "POST_SUBMIT_DEBUGGER_REATTACH_FAILED"
  );
}

function _cwaDeepSeekPostSubmitAmbiguousError(error) {
  const message = String(error?.message || error || "UNKNOWN");
  if (message.startsWith(
    "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
  )) {
    return error;
  }
  return new Error(
    "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "POST_SUBMIT_OBSERVATION_FAILED:" +
    message
  );
}

async function _cwaDeepSeekSubmitOnce(debuggee, text, deadlineAt) {
  const written = await _cwaDeepSeekEvaluate(debuggee, _cwaDeepSeekComposerExpression(text));
  if (written?.written !== true) throw new Error("DEEPSEEK_COMPOSER_WRITE_FAILED");

  while (performance.now() < deadlineAt) {
    try {
      const submit = await _cwaDeepSeekEvaluate(debuggee, _cwaDeepSeekSubmitExpression());
      if (submit?.submitted === true) return;
    } catch (error) {
      if (_cwaDeepSeekDebuggerDetached(error)) {
        // A navigation may detach CDP after the single click. Never replay the write.
        return;
      }
      throw error;
    }
    await sleep(150);
  }
  throw new Error("DEEPSEEK_SUBMIT_CONTROL_NOT_READY");
}

function _cwaDeepSeekLatestNewText(snapshot, baseline) {
  if (!Array.isArray(snapshot?.texts)) return null;
  for (let index = snapshot.texts.length - 1; index >= 0; index -= 1) {
    const text = snapshot.texts[index];
    if (typeof text === "string" && text.trim() && !baseline.has(text)) return text.trim();
  }
  return null;
}

async function _cwaDeepSeekWaitForFinalText(debuggee, text, baseline, deadlineAt) {
  let lastText = null;
  let stableSince = null;
  while (performance.now() < deadlineAt) {
    let snapshot;
    try {
      snapshot = await _cwaDeepSeekEvaluate(debuggee, _cwaDeepSeekSnapshotExpression(text));
    } catch (error) {
      if (!_cwaDeepSeekDebuggerDetached(error)) throw error;
      await _cwaDeepSeekReattachForObservation(debuggee, deadlineAt);
      await sleep(250);
      continue;
    }
    const candidate = _cwaDeepSeekLatestNewText(snapshot, baseline);
    if (candidate !== null && candidate === lastText) {
      if (stableSince === null) stableSince = performance.now();
    } else {
      lastText = candidate;
      stableSince = candidate === null ? null : performance.now();
    }
    if (candidate !== null && snapshot?.generating !== true &&
        stableSince !== null && performance.now() - stableSince >= CWA_DEEPSEEK_STABLE_MS) {
      return { text: candidate, url: snapshot.url };
    }
    await sleep(250);
  }
  throw new Error(
    "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "PAGE_FINALITY_TIMEOUT"
  );
}

async function _cwaDeepSeekHandleTurn(message) {
  if (message?.type !== "turn") throw new Error("DEEPSEEK_TURN_TYPE_REQUIRED");
  if (typeof message?.text !== "string" || !message.text.trim()) throw new Error("DEEPSEEK_TEXT_REQUIRED");
  if ((Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0) ||
      message?.conversationMode != null || message?.modelProfile != null ||
      message?.browserAuthorityLeaseId != null) {
    throw new Error("DEEPSEEK_MINIMAL_PROOF_UNSUPPORTED_OPTION");
  }

  const conversationId =
    typeof message?.conversationId === "string" && message.conversationId.trim()
      ? message.conversationId.trim()
      : null;
  const timeoutMs = Math.max(5000, Math.min(Number(message?.timeoutMs) || 120000, 180000));
  const deadlineAt = performance.now() + timeoutMs;
  const startedAt = performance.now();
  const tab = await _cwaDeepSeekEnsureTab(conversationId);
  const initialUrl = tab.url || CWA_DEEPSEEK_ORIGIN + "/";
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    await _cwaDeepSeekWaitForComposer(debuggee, deadlineAt);

    const before = await _cwaDeepSeekEvaluate(debuggee, _cwaDeepSeekSnapshotExpression(message.text));
    const baseline = new Set(Array.isArray(before?.texts) ? before.texts : []);

    await _cwaDeepSeekSubmitOnce(debuggee, message.text, deadlineAt);
    try {
      const final = await _cwaDeepSeekWaitForFinalText(
        debuggee,
        message.text,
        baseline,
        deadlineAt
      );
      const finalTab = await chrome.tabs.get(tab.id);
      const finalUrl = typeof finalTab?.url === "string" ? finalTab.url : final.url;
      if (!_cwaDeepSeekIsUrl(finalUrl)) throw new Error("DEEPSEEK_FINAL_ROUTE_INVALID");

      let resolvedConversationId = conversationId;
      if (resolvedConversationId === null) {
        if (finalUrl === initialUrl) {
          throw new Error("DEEPSEEK_NEW_CHAT_ROUTE_IDENTITY_UNPROVEN");
        }
        resolvedConversationId = crypto.randomUUID();
      }
      await _cwaDeepSeekStoreRoute(resolvedConversationId, finalUrl);

      return {
        providerId: CWA_DEEPSEEK_PROVIDER_ID,
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
      throw _cwaDeepSeekPostSubmitAmbiguousError(error);
    }
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

registerProductProviderTurnHandler(
  CWA_DEEPSEEK_PROVIDER_ID,
  _cwaDeepSeekHandleTurn
);
