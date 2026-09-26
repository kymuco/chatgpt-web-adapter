// PR17.0 first non-chat hosted-capability falsification.
//
// This is intentionally product-specific research code. It does not register as a
// ProductWriteTransport or ProductProviderBoundary provider. The point is to prove
// text translation as a bounded hosted capability before generalizing the chat core.

const CWA_GOOGLE_TRANSLATE_ORIGIN = "https://translate.google.com";
const CWA_GOOGLE_TRANSLATE_RUNTIME_TAB_KEY = "googleTranslateRuntimeTabIdPr17_0";
const CWA_GOOGLE_TRANSLATE_STABLE_MS = 2000;

function _cwaGoogleTranslateIsUrl(url) {
  try {
    return new URL(url).origin === CWA_GOOGLE_TRANSLATE_ORIGIN;
  } catch {
    return false;
  }
}

async function _cwaGoogleTranslateStorageGet(key) {
  const result = await chrome.storage.local.get(key);
  return result?.[key];
}

async function _cwaGoogleTranslateStorageSet(key, value) {
  await chrome.storage.local.set({ [key]: value });
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

function _cwaGoogleTranslateTargetUrl(sourceLanguage, targetLanguage) {
  const url = new URL(CWA_GOOGLE_TRANSLATE_ORIGIN + "/");
  url.searchParams.set("sl", sourceLanguage);
  url.searchParams.set("tl", targetLanguage);
  url.searchParams.set("op", "translate");
  return url.toString();
}

async function _cwaGoogleTranslateEnsureFreshTab(sourceLanguage, targetLanguage) {
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
  } else if (tab.url === targetUrl) {
    await chrome.tabs.reload(tab.id);
    tab = await chrome.tabs.get(tab.id);
  } else {
    tab = await chrome.tabs.update(tab.id, { url: targetUrl, active: false });
  }

  tab = await _cwaBaseWaitForTabComplete(tab.id, 45000);
  if (!_cwaGoogleTranslateIsUrl(tab?.url || "")) {
    throw new Error("GOOGLE_TRANSLATE_RUNTIME_TAB_ORIGIN_CHANGED");
  }
  return tab;
}

function _cwaGoogleTranslateSourceExpression(text) {
  const encodedText = JSON.stringify(text === undefined ? null : text);
  return "(() => {" +
    "const requestedText=" + encodedText + ";" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const candidates=Array.from(document.querySelectorAll('textarea')).filter((element)=>visible(element)&&!element.disabled&&element.getAttribute('aria-disabled')!=='true');" +
    "candidates.sort((left,right)=>left.getBoundingClientRect().top-right.getBoundingClientRect().top);" +
    "const source=candidates[0]||null;" +
    "if(!source)return {found:false};" +
    "if(requestedText===null)return {found:true,value:String(source.value||'')};" +
    "source.focus();" +
    "const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')?.set;" +
    "if(typeof setter==='function')setter.call(source,requestedText);else source.value=requestedText;" +
    "source.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:requestedText}));" +
    "source.dispatchEvent(new Event('change',{bubbles:true}));" +
    "return {found:true,written:true,value:String(source.value||'')};" +
  "})()";
}

function _cwaGoogleTranslateSnapshotExpression() {
  return "(() => {" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim();" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const source=Array.from(document.querySelectorAll('textarea')).filter((element)=>visible(element)&&!element.disabled)[0]||null;" +
    "let translated='';" +
    "for(const selector of ['[jsname=\\\"jqKxS\\\"]','[data-language-for-alternatives]']){" +
      "const candidates=Array.from(document.querySelectorAll(selector)).filter((element)=>visible(element));" +
      "const texts=candidates.map((element)=>normalize(element.innerText||element.textContent)).filter(Boolean);" +
      "if(texts.length){translated=texts[texts.length-1];break;}" +
    "}" +
    "if(!translated){" +
      "const leaves=Array.from(document.querySelectorAll('span[jsname=\\\"W297wb\\\"],span.ryNqvb')).filter((element)=>visible(element));" +
      "const texts=[];const seen=new Set();" +
      "for(const element of leaves){" +
        "const text=normalize(element.innerText||element.textContent);" +
        "if(!text||seen.has(text))continue;" +
        "seen.add(text);texts.push(text);" +
      "}" +
      "translated=texts.join(' ');" +
    "}" +
    "const busy=Array.from(document.querySelectorAll('[aria-busy=\\\"true\\\"]')).some((element)=>visible(element));" +
    "return {url:location.href,sourceValue:source?String(source.value||''):'',translatedText:translated,busy};" +
  "})()";
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

async function _cwaGoogleTranslateWaitForSource(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateSourceExpression()
    );
    if (snapshot?.found === true) return snapshot;
    await sleep(200);
  }
  throw new Error("GOOGLE_TRANSLATE_SOURCE_NOT_READY");
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
    message
  );
}

async function _cwaGoogleTranslateWriteOnce(debuggee, text) {
  try {
    const written = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateSourceExpression(text)
    );
    if (written?.written !== true || written?.value !== text) {
      throw new Error("SOURCE_WRITE_NOT_CONFIRMED");
    }
  } catch (error) {
    // Runtime.evaluate may have dispatched input/change before its result is lost.
    throw _cwaGoogleTranslateAmbiguousError(error);
  }
}

async function _cwaGoogleTranslateWaitForResult(debuggee, text, deadlineAt) {
  let lastText = null;
  let stableSince = null;

  while (performance.now() < deadlineAt) {
    let snapshot;
    try {
      snapshot = await _cwaGoogleTranslateEvaluate(
        debuggee,
        _cwaGoogleTranslateSnapshotExpression()
      );
    } catch (error) {
      throw _cwaGoogleTranslateAmbiguousError(error);
    }

    if (snapshot?.sourceValue !== text) {
      throw _cwaGoogleTranslateAmbiguousError(
        new Error("SOURCE_VALUE_DIVERGED_AFTER_WRITE")
      );
    }

    const candidate =
      typeof snapshot?.translatedText === "string"
        ? snapshot.translatedText.trim()
        : "";

    if (candidate && candidate === lastText) {
      if (stableSince === null) stableSince = performance.now();
    } else {
      lastText = candidate || null;
      stableSince = candidate ? performance.now() : null;
    }

    if (
      candidate &&
      snapshot?.busy !== true &&
      stableSince !== null &&
      performance.now() - stableSince >= CWA_GOOGLE_TRANSLATE_STABLE_MS
    ) {
      return {
        text: candidate,
        url: typeof snapshot?.url === "string" ? snapshot.url : null
      };
    }
    await sleep(200);
  }

  throw new Error(
    "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
    "PAGE_RESULT_TIMEOUT"
  );
}

async function _cwaGoogleTranslateHandle(message) {
  if (message?.type !== "translate_text") {
    throw new Error("GOOGLE_TRANSLATE_OPERATION_TYPE_REQUIRED");
  }
  if (typeof message?.text !== "string" || !message.text.trim()) {
    throw new Error("GOOGLE_TRANSLATE_TEXT_REQUIRED");
  }
  if (message.text.length > 5000) {
    throw new Error("GOOGLE_TRANSLATE_TEXT_TOO_LARGE");
  }
  const sourceLanguage =
    typeof message?.sourceLanguage === "string"
      ? message.sourceLanguage.trim().toLowerCase()
      : "";
  const targetLanguage =
    typeof message?.targetLanguage === "string"
      ? message.targetLanguage.trim().toLowerCase()
      : "";
  const languagePattern = /^(auto|[a-z]{2,8}(?:-[a-z0-9]{2,8})*)$/;
  if (!languagePattern.test(sourceLanguage)) {
    throw new Error("GOOGLE_TRANSLATE_SOURCE_LANGUAGE_INVALID");
  }
  if (!languagePattern.test(targetLanguage) || targetLanguage === "auto") {
    throw new Error("GOOGLE_TRANSLATE_TARGET_LANGUAGE_INVALID");
  }

  const timeoutMs = Math.max(
    5000,
    Math.min(Number(message?.timeoutMs) || 45000, 90000)
  );
  const deadlineAt = performance.now() + timeoutMs;
  const startedAt = performance.now();
  const tab = await _cwaGoogleTranslateEnsureFreshTab(
    sourceLanguage,
    targetLanguage
  );
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    await _cwaGoogleTranslateWaitForSource(debuggee, deadlineAt);
    const before = await _cwaGoogleTranslateEvaluate(
      debuggee,
      _cwaGoogleTranslateSnapshotExpression()
    );
    if (
      String(before?.sourceValue || "").trim() ||
      String(before?.translatedText || "").trim()
    ) {
      throw new Error("GOOGLE_TRANSLATE_FRESH_BASELINE_REQUIRED");
    }

    await _cwaGoogleTranslateWriteOnce(debuggee, message.text);

    try {
      const final = await _cwaGoogleTranslateWaitForResult(
        debuggee,
        message.text,
        deadlineAt
      );
      const finalTab = await chrome.tabs.get(tab.id);
      const finalUrl =
        typeof finalTab?.url === "string" ? finalTab.url : final.url;
      if (!_cwaGoogleTranslateIsUrl(finalUrl)) {
        throw new Error("GOOGLE_TRANSLATE_FINAL_ROUTE_INVALID");
      }

      return {
        productId: "google-translate",
        capability: "translate_text",
        sourceLanguage,
        targetLanguage,
        translatedText: final.text,
        finalUrl,
        tabId: tab.id,
        elapsedMs: Math.round(performance.now() - startedAt),
        finalityEvidence: "PAGE_DOM_STABLE_RESULT",
        canonicalResultProven: false,
        automaticWriteRetry: false,
        fallbackTransport: null,
        conversationSemantics: false
      };
    } catch (error) {
      throw _cwaGoogleTranslateAmbiguousError(error);
    }
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {}
    }
  }
}

async function _cwaOnNativeMessageWithGoogleTranslate(message, port, next) {
  if (
    message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
    message?.type !== "translate_text"
  ) {
    return next(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;

  if (activeRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "translate_text_result",
      request_id: requestId,
      ok: false,
      error: "BROWSER_NATIVE_EXTENSION_BUSY"
    });
    return;
  }

  activeRequestId = requestId;
  try {
    const result = await _cwaGoogleTranslateHandle(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "translate_text_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "translate_text_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  } finally {
    activeRequestId = null;
  }
}
