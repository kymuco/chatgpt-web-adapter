const STATUS_MESSAGE_TYPE = "cwa_bridge_status";
const CHATGPT_URL = "https://chatgpt.com/";

const elements = {
  statusTitle: document.getElementById("status-title"),
  statusDetail: document.getElementById("status-detail"),
  runtimeSummary: document.getElementById("runtime-summary"),
  chatgptSummary: document.getElementById("chatgpt-summary"),
  nativeHost: document.getElementById("native-host"),
  runtimeTab: document.getElementById("runtime-tab"),
  activity: document.getElementById("activity"),
  protocol: document.getElementById("protocol"),
  version: document.getElementById("version"),
  versionDetail: document.getElementById("version-detail"),
  copyFeedback: document.getElementById("copy-feedback"),
  openChatGPT: document.getElementById("open-chatgpt"),
  copyStatus: document.getElementById("copy-status")
};

let latestStatus = null;

function requestBridgeStatus() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: STATUS_MESSAGE_TYPE }, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message || "BRIDGE_STATUS_UNAVAILABLE"));
        return;
      }
      if (!response?.ok || !response?.status) {
        reject(new Error(response?.error || "BRIDGE_STATUS_UNAVAILABLE"));
        return;
      }
      resolve(response.status);
    });
  });
}

function runtimeTabLabel(status) {
  if (status.runtimeTabPresent === true) {
    if (status.runtimeTabRouteKind === "conversation") return "Conversation open";
    if (status.runtimeTabRouteKind === "chatgpt") return "Ready";
    return "Open";
  }
  if (status.runtimeTabRouteKind === "stale") return "Needs refresh";
  return "Created on demand";
}

function renderStatus(status) {
  latestStatus = status;
  const connected = status.nativeHostConnected === true;
  const busy = status.busy === true;
  const version = status.extensionVersion || "—";

  document.body.dataset.state = connected ? (busy ? "working" : "ready") : "offline";

  if (!connected) {
    elements.statusTitle.textContent = "Needs attention";
    elements.statusDetail.textContent = "CWA can't reach the local runtime.";
    elements.runtimeSummary.textContent = "Not connected";
    elements.chatgptSummary.textContent = "Opens when needed";
  } else if (busy) {
    elements.statusTitle.textContent = "Working";
    elements.statusDetail.textContent = "Your local runtime is using this browser session.";
    elements.runtimeSummary.textContent = "Connected";
    elements.chatgptSummary.textContent = "In use";
  } else {
    elements.statusTitle.textContent = "Ready";
    elements.statusDetail.textContent = "Your local runtime can use this browser session.";
    elements.runtimeSummary.textContent = "Connected";
    elements.chatgptSummary.textContent = "Opens when needed";
  }

  elements.nativeHost.textContent = connected ? "Connected" : "Unavailable";
  elements.runtimeTab.textContent = runtimeTabLabel(status);
  elements.activity.textContent = busy ? "Turn in progress" : "Idle";
  elements.protocol.textContent = String(status.protocolVersion ?? "—");
  elements.version.textContent = `v${version}`;
  elements.versionDetail.textContent = version;
}

function renderError() {
  latestStatus = null;
  document.body.dataset.state = "error";
  const version = chrome.runtime.getManifest().version;
  elements.statusTitle.textContent = "Status unavailable";
  elements.statusDetail.textContent = "Reload the extension and try again.";
  elements.runtimeSummary.textContent = "Unknown";
  elements.chatgptSummary.textContent = "Opens when needed";
  elements.nativeHost.textContent = "Unknown";
  elements.runtimeTab.textContent = "Unknown";
  elements.activity.textContent = "Unknown";
  elements.protocol.textContent = "—";
  elements.version.textContent = `v${version}`;
  elements.versionDetail.textContent = version;
}

function safeStatusForClipboard(status) {
  return {
    product: "chatgpt-web-adapter",
    surface: "browser-extension-diagnostics",
    extensionVersion: status.extensionVersion || null,
    protocolVersion: status.protocolVersion ?? null,
    nativeHostConnected: status.nativeHostConnected === true,
    runtimeTabPresent: status.runtimeTabPresent === true,
    runtimeTabRouteKind: status.runtimeTabRouteKind || "unknown",
    busy: status.busy === true,
    transport: status.transport || "browser-owned"
  };
}

async function copyStatus() {
  if (!latestStatus) {
    elements.copyFeedback.textContent = "Diagnostics are not available yet.";
    return;
  }
  const text = JSON.stringify(safeStatusForClipboard(latestStatus), null, 2);
  try {
    await navigator.clipboard.writeText(text);
    elements.copyFeedback.textContent = "Diagnostics copied.";
  } catch {
    elements.copyFeedback.textContent = "Clipboard unavailable in this Chrome session.";
  }
}

async function refresh() {
  try {
    renderStatus(await requestBridgeStatus());
  } catch {
    renderError();
  }
}

elements.openChatGPT.addEventListener("click", () => {
  chrome.tabs.create({ url: CHATGPT_URL });
});

elements.copyStatus.addEventListener("click", () => {
  copyStatus();
});

refresh();
