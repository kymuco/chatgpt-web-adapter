const CWA_GOOGLE_TRANSLATE_ORIGIN = "https://translate.google.com";
const CWA_GOOGLE_TRANSLATE_RUNTIME_TAB_KEY = "googleTranslateRuntimeTabIdV1";
const CWA_GOOGLE_TRANSLATE_STABLE_MS = 1200;

function _cwaGoogleTranslateIsUrl(url) {
  try {
    return new URL(url).origin === CWA_GOOGLE_TRANSLATE_ORIGIN;
  } catch {
    return false;
  }
}

function _cwaGoogleTranslateLanguageCode(value, source) {
  if (typeof value !== "string") throw new Error("GOOGLE_TRANSLATE_LANGUAGE_REQUIRED");
  const normalized = value.trim();
  if (source && normalized.toLowerCase() === "auto") return "auto";
  if (!/^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(normalized)) {
    throw new Error("GOOGLE_TRANSLATE_LANGUAGE_INVALID");
  }
  return normalized;
}

async function _cwaGoogleTranslateStorageGet(key) {
  const result = await chrome.storage.local.get(key);
  return result?.[key];
}

async function _cwaGoogleTranslateStorageSet(key, value) {
  await chrome.storage.local.set({ [key]: value });
}

function _cwaGoogleTranslateTargetUrl(sourceLanguage, targetLanguage) {
  const url = new URL(CWA_GOOGLE_TRANSLATE_ORIGIN + "/");
  url.searchParams.set("sl", sourceLanguage);
  url.searchParams.set("tl", targetLanguage);
  url.searchParams.set("op", "translate");
  return url.toString();
}

function _cwaGoogleTranslateRouteMatchesLanguages(
  url,
  sourceLanguage,
  targetLanguage
) {
  try {
    const parsed = new URL(url);
    return (
      parsed.origin === CWA_GOOGLE_TRANSLATE_ORIGIN &&
      parsed.searchParams.get("sl") === sourceLanguage &&
      parsed.searchParams.get("tl") === targetLanguage
    );
  } catch {
    return false;
  }
}


async function _cwaGoogleTranslateExistingTab() {
  const stored = await _cwaGoogleTranslateStorageGet(
    CWA_GOOGLE_TRANSLATE_RUNTIME_TAB_KEY
  );
  if (!Number.isInteger(stored)) return null;
  try {
    const tab = await chrome.tabs.get(stored);
    return _cwaGoogleTranslateIsUrl(tab?.url || "") ? tab : null;
  } catch {
    return null;
  }
}

async function _cwaGoogleTranslateEnsureTab(
  sourceLanguage,
  targetLanguage,
  deadlineAt
) {
  const targetUrl = _cwaGoogleTranslateTargetUrl(sourceLanguage, targetLanguage);
  let tab = await _cwaGoogleTranslateExistingTab();

  if (tab === null) {
    tab = await chrome.tabs.create({ url: targetUrl, active: false });
    if (!Number.isInteger(tab?.id)) {
      throw new Error("GOOGLE_TRANSLATE_RUNTIME_TAB_CREATE_FAILED");
    }
    await _cwaGoogleTranslateStorageSet(
      CWA_GOOGLE_TRANSLATE_RUNTIME_TAB_KEY,
      tab.id
    );
  } else if (tab.url !== targetUrl) {
    tab = await chrome.tabs.update(tab.id, { url: targetUrl, active: false });
  }

  const remainingMs = Math.floor(deadlineAt - performance.now());
  if (remainingMs <= 0) {
    throw new Error("GOOGLE_TRANSLATE_OPERATION_DEADLINE_EXHAUSTED_BEFORE_PAGE_READY");
  }
  tab = await _cwaBaseWaitForTabComplete(
    tab.id,
    Math.max(1, Math.min(45000, remainingMs))
  );
  if (!_cwaGoogleTranslateIsUrl(tab?.url || "")) {
    throw new Error("GOOGLE_TRANSLATE_RUNTIME_TAB_ORIGIN_CHANGED");
  }
  return tab;
}

function _cwaGoogleTranslateSourceExpression(text) {
  const encodedText = JSON.stringify(text);
  return "(() => {" +
    "const requestedText=" + encodedText + ";" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const candidates=Array.from(document.querySelectorAll('textarea,[contenteditable=\"true\"][role=\"textbox\"]')).filter((element)=>visible(element)&&element.getAttribute('aria-disabled')!=='true'&&!element.disabled);" +
    "candidates.sort((left,right)=>left.getBoundingClientRect().left-right.getBoundingClientRect().left);" +
    "const source=candidates[0]||null;" +
    "if(!source)return {found:false};" +
    "source.focus();" +
    "if(source instanceof HTMLTextAreaElement||source instanceof HTMLInputElement){" +
      "const proto=source instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;" +
      "const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;" +
      "if(typeof setter==='function')setter.call(source,requestedText);else source.value=requestedText;" +
    "}else{" +
      "source.textContent=requestedText;" +
    "}" +
    "source.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:requestedText}));" +
    "source.dispatchEvent(new Event('change',{bubbles:true}));" +
    "return {found:true,written:true};" +
  "})()";
}

function _cwaGoogleTranslateResultExpression() {
  return "(() => {" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim();" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const primary=Array.from(document.querySelectorAll('[jsname=\"W297wb\"],[jsname=\"jqKxS\"]')).filter(visible);" +
    "const texts=[];" +
    "for(const element of primary){" +
      "if(element.closest('textarea,[contenteditable=\"true\"]'))continue;" +
      "const text=normalize(element.innerText||element.textContent);" +
      "if(!text)continue;" +
      "texts.push(text);" +
    "}" +
    "const identityResolved=texts.length<=1;" +
    "return {url:location.href,text:identityResolved?(texts[0]||null):null,candidateCount:texts.length,identityResolved};" +
  "})()";
}

function _cwaGoogleTranslateCharacterizationExpression() {
  return "(() => {" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim();" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const nodes=Array.from(document.querySelectorAll('[jsname=\"W297wb\"],[jsname=\"jqKxS\"]')).filter((element)=>visible(element)&&!element.closest('textarea,[contenteditable=\"true\"]'));" +
    "const index=new Map(nodes.map((node,i)=>[node,i]));" +
    "const candidates=nodes.map((element,i)=>{" +
      "const parent=element.parentElement;" +
      "return {" +
        "index:i," +
        "tag:String(element.tagName||'').toLowerCase()," +
        "jsname:element.getAttribute('jsname')," +
        "lang:element.getAttribute('lang')," +
        "role:element.getAttribute('role')," +
        "text:normalize(element.innerText||element.textContent)," +
        "childElementCount:element.childElementCount," +
        "parentTag:parent?String(parent.tagName||'').toLowerCase():null," +
        "parentJsname:parent?parent.getAttribute('jsname'):null," +
        "parentClass:parent?String(parent.className||'').slice(0,160):null," +
        "contains:nodes.filter((other)=>other!==element&&element.contains(other)).map((other)=>index.get(other))," +
        "containedBy:nodes.filter((other)=>other!==element&&other.contains(element)).map((other)=>index.get(other))" +
      "};" +
    "});" +
    "return {url:location.href,candidateCount:candidates.length,candidates};" +
  "})()";
}

async function _cwaGoogleTranslateCharacterizeCurrentResult() {
  const tab = await _cwaGoogleTranslateExistingTab();
  if (tab === null) {
    throw new Error("GOOGLE_TRANSLATE_CHARACTERIZATION_RUNTIME_TAB_MISSING");
  }
  const debuggee = { tabId: tab.id };
  let attached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    return await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateCharacterizationExpression()
    );
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Read-only characterization cleanup only.
      }
    }
  }
}

async function _cwaGoogleTranslateEvaluate(debuggee, expression) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.exceptionDetails) {
    throw new Error("GOOGLE_TRANSLATE_PAGE_EVALUATION_FAILED");
  }
  return result?.result?.value;
}

function _cwaGoogleTranslateAmbiguousError(error) {
  const message = String(error?.message || error || "UNKNOWN");
  if (message.startsWith(
    "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
  )) {
    return error;
  }
  return new Error(
    "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "POST_INPUT_OBSERVATION_FAILED:" +
    message
  );
}

async function _cwaGoogleTranslateWriteSource(
  debuggee,
  text,
  outcomeMayHaveStarted
) {
  try {
    const result = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateSourceExpression(text)
    );
    if (result?.written !== true) {
      throw new Error("GOOGLE_TRANSLATE_SOURCE_WRITE_FAILED");
    }
    return result;
  } catch (error) {
    if (outcomeMayHaveStarted) throw _cwaGoogleTranslateAmbiguousError(error);
    throw error;
  }
}

async function _cwaGoogleTranslateWaitForClearedResult(
  debuggee,
  targetLanguage,
  deadlineAt
) {
  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateResultExpression()
    );
    const text = typeof snapshot?.text === "string" ? snapshot.text.trim() : "";
    if (!text) return;
    await sleep(100);
  }
  throw new Error("GOOGLE_TRANSLATE_PREWRITE_RESULT_NOT_CLEARED");
}

async function _cwaGoogleTranslateWaitForResult(
  debuggee,
  targetLanguage,
  baselineText,
  deadlineAt
) {
  let lastText = null;
  let stableSince = null;

  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateResultExpression()
    );
    if (snapshot?.identityResolved === false) {
      throw new Error(
        "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
        "RESULT_IDENTITY_UNRESOLVED"
      );
    }
    const text = typeof snapshot?.text === "string" ? snapshot.text.trim() : "";
    if (text && text !== baselineText) {
      if (text !== lastText) {
        lastText = text;
        stableSince = performance.now();
      } else if (
        stableSince !== null &&
        performance.now() - stableSince >= CWA_GOOGLE_TRANSLATE_STABLE_MS
      ) {
        return { text, url: snapshot.url };
      }
    }
    await sleep(200);
  }
  throw new Error(
    "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "PAGE_RESULT_TIMEOUT"
  );
}

async function _cwaGoogleTranslateText(message) {
  const text = typeof message?.text === "string" ? message.text : "";
  if (!text.trim()) throw new Error("GOOGLE_TRANSLATE_TEXT_REQUIRED");
  if (text.length > 5000) throw new Error("GOOGLE_TRANSLATE_TEXT_TOO_LARGE");

  const sourceLanguage = _cwaGoogleTranslateLanguageCode(
    message?.sourceLanguage,
    true
  );
  const targetLanguage = _cwaGoogleTranslateLanguageCode(
    message?.targetLanguage,
    false
  );
  const timeoutMs = Math.max(
    1000,
    Math.min(Number(message?.timeoutMs) || 30000, 120000)
  );
  const deadlineAt = performance.now() + timeoutMs;
  const startedAt = performance.now();

  const tab = await _cwaGoogleTranslateEnsureTab(
    sourceLanguage,
    targetLanguage,
    deadlineAt
  );
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    // Clear previous text before the authoritative translation-triggering write.
    await _cwaGoogleTranslateWriteSource(
      debuggee,
      "",
      false
    );
    await _cwaGoogleTranslateWaitForClearedResult(
      debuggee,
      targetLanguage,
      Math.min(deadlineAt, performance.now() + 5000)
    );
    const baselineText = "";
    const remainingBeforeInput = deadlineAt - performance.now();
    if (remainingBeforeInput < CWA_GOOGLE_TRANSLATE_STABLE_MS + 1000) {
      throw new Error(
        "GOOGLE_TRANSLATE_OPERATION_DEADLINE_EXHAUSTED_BEFORE_INPUT"
      );
    }

    // Google Translate begins the hosted operation in response to this input
    // mutation. If the Runtime.evaluate result is lost, execution is ambiguous.
    await _cwaGoogleTranslateWriteSource(
      debuggee,
      text,
      true
    );

    let final;
    try {
      final = await _cwaGoogleTranslateWaitForResult(
        debuggee,
        targetLanguage,
        baselineText,
        deadlineAt
      );
    } catch (error) {
      throw _cwaGoogleTranslateAmbiguousError(error);
    }

    const finalUrl = typeof final?.url === "string" ? final.url : "";
    if (
      !_cwaGoogleTranslateRouteMatchesLanguages(
        finalUrl,
        sourceLanguage,
        targetLanguage
      )
    ) {
      throw _cwaGoogleTranslateAmbiguousError(
        new Error("GOOGLE_TRANSLATE_FINAL_ROUTE_LANGUAGE_IDENTITY_INVALID")
      );
    }

    return {
      productId: "google-translate-web",
      capabilityId: "translate_text",
      translatedText: final.text,
      sourceLanguage,
      targetLanguage,
      finalUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      finalityEvidence: "PAGE_DOM_STABLE_TRANSLATION",
      canonicalCompletionProven: false,
      automaticRetry: false
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Detach cleanup cannot replace the capability outcome.
      }
    }
  }
}

let _cwaGoogleTranslateActiveRequestId = null;

async function _cwaOnNativeMessageWithGoogleTranslate(message, port, next) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION) {
    return next(message, port);
  }
  if (
    message?.type !== "translate_text" &&
    message?.type !== "characterize_translate_result" &&
    message?.type !== "characterize_translate_ping"
  ) {
    return next(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;

  if (message.type === "characterize_translate_ping") {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "characterize_translate_ping_result",
      request_id: requestId,
      ok: true,
      worker: "google-translate-capability",
      characterizationVersion: 1
    });
    return;
  }

  const isCharacterization = message.type === "characterize_translate_result";
  if (_cwaGoogleTranslateActiveRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: isCharacterization
        ? "characterize_translate_result_result"
        : "translate_text_result",
      request_id: requestId,
      ok: false,
      error: "GOOGLE_TRANSLATE_CAPABILITY_BUSY"
    });
    return;
  }

  _cwaGoogleTranslateActiveRequestId = requestId;
  try {
    const result = isCharacterization
      ? await _cwaGoogleTranslateCharacterizeCurrentResult()
      : await _cwaGoogleTranslateText(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: isCharacterization
        ? "characterize_translate_result_result"
        : "translate_text_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: isCharacterization
        ? "characterize_translate_result_result"
        : "translate_text_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  } finally {
    _cwaGoogleTranslateActiveRequestId = null;
  }
}
