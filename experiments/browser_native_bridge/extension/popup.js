const output = document.getElementById("output");
const text = document.getElementById("text");

function show(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function call(message) {
  show("Running…");
  const response = await chrome.runtime.sendMessage(message);
  show(response);
}

document.getElementById("capabilities").addEventListener("click", () => {
  call({ op: "probe_capabilities" });
});

document.getElementById("send").addEventListener("click", () => {
  call({ op: "send_text_probe", text: text.value });
});
