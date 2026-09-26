const CWA_GEMINI_NOTEBOOK_PRODUCT_ID = "gemini-notebook-web";
const CWA_GEMINI_NOTEBOOK_ORIGINS = new Set([
  "https://notebook.google",
  "https://notebooklm.google.com"
]);

function _cwaGeminiNotebookIsUrl(url) {
  try {
    return CWA_GEMINI_NOTEBOOK_ORIGINS.has(new URL(url).origin);
  } catch {
    return false;
  }
}

async function _cwaGeminiNotebookFindOpenTabForCharacterization() {
  const tabs = (
    await chrome.tabs.query({
      url: [
        "https://notebook.google/*",
        "https://notebooklm.google.com/*"
      ]
    })
  ).filter(
    (tab) =>
      Number.isInteger(tab?.id) &&
      _cwaGeminiNotebookIsUrl(tab?.url || "")
  );

  if (tabs.length === 0) {
    throw new Error("GEMINI_NOTEBOOK_CHARACTERIZATION_TAB_MISSING");
  }
  if (tabs.length > 1) {
    throw new Error(
      "GEMINI_NOTEBOOK_CHARACTERIZATION_TAB_AMBIGUOUS:" +
      String(tabs.length)
    );
  }
  return tabs[0];
}

function _cwaGeminiNotebookCharacterizationExpression() {
  return "(() => {" +
    "const normalize=(value)=>String(value||'').replace(/\\s+/g,' ').trim();" +
    "const visible=(element)=>{" +
      "if(!(element instanceof Element))return false;" +
      "const rect=element.getBoundingClientRect();" +
      "const style=getComputedStyle(element);" +
      "return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden';" +
    "};" +
    "const summarize=(element,index)=>{" +
      "const rect=element.getBoundingClientRect();" +
      "const parent=element.parentElement;" +
      "return {" +
        "index," +
        "tag:String(element.tagName||'').toLowerCase()," +
        "id:String(element.id||'').slice(0,120)," +
        "className:String(element.className||'').slice(0,220)," +
        "role:element.getAttribute('role')," +
        "ariaLabel:String(element.getAttribute('aria-label')||'').slice(0,220)," +
        "placeholder:String(element.getAttribute('placeholder')||'').slice(0,220)," +
        "type:String(element.getAttribute('type')||'').slice(0,80)," +
        "name:String(element.getAttribute('name')||'').slice(0,120)," +
        "jsname:element.getAttribute('jsname')," +
        "dataTestId:element.getAttribute('data-testid')," +
        "text:normalize(element.innerText||element.textContent).slice(0,420)," +
        "childElementCount:element.childElementCount," +
        "parentTag:parent?String(parent.tagName||'').toLowerCase():null," +
        "parentRole:parent?parent.getAttribute('role'):null," +
        "parentClass:parent?String(parent.className||'').slice(0,180):null," +
        "left:Math.round(rect.left)," +
        "top:Math.round(rect.top)," +
        "width:Math.round(rect.width)," +
        "height:Math.round(rect.height)" +
      "};" +
    "};" +
    "const selectors=[" +
      "'button'," +
      "'[role=\\"button\\"]'," +
      "'[role=\\"dialog\\"]'," +
      "'[role=\\"list\\"]'," +
      "'[role=\\"listitem\\"]'," +
      "'[role=\\"menuitem\\"]'," +
      "'input'," +
      "'textarea'," +
      "'[contenteditable=\\"true\\"]'," +
      "'[aria-label]'," +
      "'[data-testid]'" +
    "];" +
    "const seen=new Set();" +
    "const candidates=[];" +
    "for(const selector of selectors){" +
      "for(const element of document.querySelectorAll(selector)){" +
        "if(candidates.length>=180)break;" +
        "if(seen.has(element)||!visible(element))continue;" +
        "seen.add(element);" +
        "const text=normalize(element.innerText||element.textContent);" +
        "const aria=normalize(element.getAttribute('aria-label'));" +
        "const placeholder=normalize(element.getAttribute('placeholder'));" +
        "if(!text&&!aria&&!placeholder&&element.tagName!=='INPUT'&&element.tagName!=='TEXTAREA')continue;" +
        "candidates.push(summarize(element,candidates.length));" +
      "}" +
      "if(candidates.length>=180)break;" +
    "}" +
    "const headings=Array.from(document.querySelectorAll('h1,h2,h3,[role=\\"heading\\"]'))" +
      ".filter(visible)" +
      ".slice(0,60)" +
      ".map((element,index)=>summarize(element,index));" +
    "return {" +
      "url:location.href," +
      "origin:location.origin," +
      "title:document.title," +
      "bodyText:normalize(document.body?.innerText||'').slice(0,5000)," +
      "headingCount:headings.length," +
      "headings," +
      "candidateCount:candidates.length," +
      "candidates" +
    "};" +
  "})()";
}

async function _cwaGeminiNotebookCharacterizeCurrentPage() {
  const tab = await _cwaGeminiNotebookFindOpenTabForCharacterization();
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    const evaluation = await _cwaBaseSendCommand(
      debuggee,
      "Runtime.evaluate",
      {
        expression: _cwaGeminiNotebookCharacterizationExpression(),
        returnByValue: true,
        awaitPromise: true
      }
    );
    if (evaluation?.exceptionDetails) {
      throw new Error("GEMINI_NOTEBOOK_CHARACTERIZATION_EVALUATION_FAILED");
    }
    const value = evaluation?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("GEMINI_NOTEBOOK_CHARACTERIZATION_RESULT_MISSING");
    }
    if (!_cwaGeminiNotebookIsUrl(value.url || "")) {
      throw new Error("GEMINI_NOTEBOOK_CHARACTERIZATION_ROUTE_CHANGED");
    }
    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      readOnly: true,
      tabId: tab.id,
      ...value
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Read-only characterization cleanup must not replace the observed result.
      }
    }
  }
}

async function _cwaOnNativeMessageWithGeminiNotebook(message, port, next) {
  if (
    message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
    message?.type !== "characterize_gemini_notebook"
  ) {
    return next(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;

  try {
    const result = await _cwaGeminiNotebookCharacterizeCurrentPage();
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "characterize_gemini_notebook_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "characterize_gemini_notebook_result",
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
