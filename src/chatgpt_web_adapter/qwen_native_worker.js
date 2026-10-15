const CDP_PROTOCOL_VERSION = "1.3";
const BRIDGE_PROTOCOL_VERSION = 1;
let nativePort = null;
let handler = null;
let busy = false;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function registerProductProviderTurnHandler(id, fn) { if (id === "qwen") handler = fn; }
function postNative(message) { if (nativePort) nativePort.postMessage(message); }
async function _cwaBaseSendCommand(debuggee, method, params = {}) {
  if (method === "Input.insertText") {
    // Qwen's editor relies on focus state even when CDP accepts insertion.
    // Emulate page focus without activating the Chrome tab or window.
    await chrome.debugger.sendCommand(debuggee, "Emulation.setFocusEmulationEnabled", {enabled: true});
  }
  return chrome.debugger.sendCommand(debuggee, method, params);
}
async function _cwaBaseWaitForTabComplete(id, timeout) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    const tab = await chrome.tabs.get(id);
    if (tab.status === "complete") return tab;
    await sleep(100);
  }
  throw new Error("QWEN_TAB_LOAD_TIMEOUT");
}
importScripts("service_worker_qwen_stream.js", "service_worker_qwen_provider.js");
function connect() {
  if (nativePort) return;
  const port = chrome.runtime.connectNative("com.kymuco.qwen_web_adapter");
  nativePort = port;
  port.postMessage({protocol:1,type:"hello",extensionId:chrome.runtime.id});
  port.onDisconnect.addListener(() => { void chrome.runtime.lastError; if (nativePort === port) nativePort = null; setTimeout(connect, 2000); });
  port.onMessage.addListener(async message => {
    if (message.protocol !== 1 || message.type !== "turn") return;
    const base = {protocol:1,type:"turn_result",request_id:message.request_id};
    if (busy) { port.postMessage({...base,ok:false,error:"QWEN_BUSY"}); return; }
    busy = true;
    try {
      if (message.providerId !== "qwen") throw new Error("QWEN_PROVIDER_REQUIRED");
      port.postMessage({...base,ok:true,...await handler(message)});
    } catch (error) { port.postMessage({...base,ok:false,error:String(error.message || error)}); }
    finally { busy = false; }
  });
}
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
connect();
