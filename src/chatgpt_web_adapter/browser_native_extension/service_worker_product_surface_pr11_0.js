// PR11.0 product surface for the unpacked/local browser bridge.
//
// This layer exposes only local, sanitized extension health to the extension
// popup. It does not inspect ChatGPT page content, send product turns, approve
// actions, expose conversation ids/tab ids, or add retry/fallback authority.

const CWA_PRODUCT_STATUS_MESSAGE_TYPE = "cwa_bridge_status";

async function _cwaProductRuntimeTabState() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    return { present: false, routeKind: "not_created" };
  }

  try {
    const tab = await chrome.tabs.get(storedId);
    if (!isChatGPTUrl(tab?.url || "")) {
      return { present: false, routeKind: "stale" };
    }
    return {
      present: true,
      routeKind: conversationIdFromUrl(tab?.url || "") ? "conversation" : "chatgpt"
    };
  } catch {
    return { present: false, routeKind: "stale" };
  }
}

async function _cwaProductStatus() {
  const runtimeTab = await _cwaProductRuntimeTabState();
  return {
    extensionVersion: chrome.runtime.getManifest().version,
    protocolVersion: BRIDGE_PROTOCOL_VERSION,
    nativeHostConnected: nativePort !== null,
    runtimeTabPresent: runtimeTab.present,
    runtimeTabRouteKind: runtimeTab.routeKind,
    busy: activeRequestId !== null,
    transport: "browser-owned"
  };
}

async function _cwaUpdateActionState() {
  const connected = nativePort !== null;
  const busy = activeRequestId !== null;
  const title = !connected
    ? "ChatGPT Web Adapter — Needs attention"
    : busy
      ? "ChatGPT Web Adapter — Working"
      : "ChatGPT Web Adapter — Ready";
  const badgeText = !connected ? "!" : (busy ? "…" : "");

  try {
    await chrome.action.setTitle({ title });
    await chrome.action.setBadgeText({ text: badgeText });
    if (!connected) {
      await chrome.action.setBadgeBackgroundColor({ color: "#D84C4C" });
    } else if (busy) {
      await chrome.action.setBadgeBackgroundColor({ color: "#E6A117" });
    }
  } catch {
    // Product chrome must never affect bridge availability.
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== CWA_PRODUCT_STATUS_MESSAGE_TYPE) return false;

  _cwaProductStatus()
    .then((status) => sendResponse({ ok: true, status }))
    .catch(() => sendResponse({ ok: false, error: "BRIDGE_STATUS_UNAVAILABLE" }));
  return true;
});

function _cwaAttachNativePortProductState(port) {
  if (!port?.onDisconnect?.addListener) return;
  port.onDisconnect.addListener(() => {
    _cwaUpdateActionState();
  });
}

if (nativePort !== null) {
  _cwaAttachNativePortProductState(nativePort);
}

const _cwaProductPriorConnectNativeBridge = connectNativeBridge;
connectNativeBridge = function _connectNativeBridgeWithProductState() {
  const previousPort = nativePort;
  const result = _cwaProductPriorConnectNativeBridge();
  if (nativePort !== null && nativePort !== previousPort) {
    _cwaAttachNativePortProductState(nativePort);
  }
  _cwaUpdateActionState();
  return result;
};

const _cwaProductPriorOnNativeMessage = onNativeMessage;
onNativeMessage = async function _onNativeMessageWithProductState(message, port) {
  const result = _cwaProductPriorOnNativeMessage(message, port);
  // The base handler sets activeRequestId synchronously before its first await.
  queueMicrotask(() => _cwaUpdateActionState());
  try {
    return await result;
  } finally {
    _cwaUpdateActionState();
  }
};

_cwaUpdateActionState();
