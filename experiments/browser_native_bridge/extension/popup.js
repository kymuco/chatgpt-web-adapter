const output = document.getElementById("output");
const text = document.getElementById("text");
const tabSelect = document.getElementById("tab");

function show(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function populateTabs(tabs) {
  const previousValue = tabSelect.value;
  tabSelect.textContent = "";
  if (!Array.isArray(tabs) || !tabs.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No ChatGPT tabs found";
    tabSelect.appendChild(option);
    return;
  }

  let restoredPrevious = false;
  for (const tab of tabs) {
    const option = document.createElement("option");
    option.value = String(tab.id);
    option.textContent = `${tab.active ? "● " : ""}${tab.title || "ChatGPT"} — ${tab.url}`;
    if (previousValue && option.value === previousValue) {
      option.selected = true;
      restoredPrevious = true;
    } else if (!previousValue && tab.active) {
      option.selected = true;
    }
    tabSelect.appendChild(option);
  }

  if (previousValue && !restoredPrevious) {
    tabSelect.selectedIndex = 0;
  }
}

function selectedTabId() {
  const tabId = Number.parseInt(tabSelect.value, 10);
  return Number.isInteger(tabId) ? tabId : null;
}

async function call(message) {
  show("Running…");
  const response = await chrome.runtime.sendMessage(message);
  show(response);
  return response;
}

async function probeCapabilities() {
  const response = await call({ op: "probe_capabilities" });
  if (response?.ok) populateTabs(response.result?.chatgptTabs);
}

document.getElementById("capabilities").addEventListener("click", () => {
  probeCapabilities();
});

document.getElementById("send").addEventListener("click", () => {
  const tabId = selectedTabId();
  if (tabId == null) {
    show({ ok: false, error: "SELECT_CHATGPT_TAB" });
    return;
  }
  call({ op: "send_text_probe", tabId, text: text.value });
});

document.getElementById("stress").addEventListener("click", () => {
  const tabId = selectedTabId();
  if (tabId == null) {
    show({ ok: false, error: "SELECT_CHATGPT_TAB" });
    return;
  }
  call({ op: "run_repeatability_stress", tabId });
});

probeCapabilities();
