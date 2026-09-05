// ==UserScript==
// @name         Gemini Conversation Snapshot (CWA experiment)
// @namespace    https://github.com/kymuco/chatgpt-web-adapter
// @version      0.1.0
// @description  Read-only export of the current authenticated Gemini conversation to Markdown and JSON.
// @match        https://gemini.google.com/*
// @require      https://raw.githubusercontent.com/kymuco/chatgpt-web-adapter/experiment/gemini-conversation-snapshot/experiments/gemini_conversation_snapshot_probe.js
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  "use strict";

  const BUTTON_ID = "cwa-gemini-snapshot-export";

  function isConversationRoute() {
    return /\/(?:u\/\d+\/)?(?:app\/[^/?#]+|gem\/[^/?#]+\/[^/?#]+)(?:[/?#]|$)/.test(
      location.pathname,
    );
  }

  function setButtonState(button, text, disabled = false) {
    button.textContent = text;
    button.disabled = disabled;
    button.style.opacity = disabled ? "0.65" : "1";
  }

  async function exportCurrentConversation(button) {
    if (typeof window.geminiConversationSnapshot !== "function") {
      throw new Error("Gemini snapshot probe did not load");
    }
    if (!isConversationRoute()) {
      throw new Error("Open a saved Gemini conversation first");
    }

    const suggested = `gemini_${new Date().toISOString().slice(0, 10)}`;
    const requested = window.prompt("Snapshot file prefix", suggested);
    if (requested === null) {
      return;
    }

    setButtonState(button, "Exporting…", true);
    try {
      const result = await window.geminiConversationSnapshot(location.href, {
        name: requested.trim() || suggested,
      });
      setButtonState(button, `Exported ${result.message_count} msgs`, false);
      window.setTimeout(() => setButtonState(button, "Export chat", false), 3000);
    } catch (error) {
      setButtonState(button, "Export failed", false);
      window.alert(`Gemini snapshot failed: ${error instanceof Error ? error.message : String(error)}`);
      window.setTimeout(() => setButtonState(button, "Export chat", false), 3000);
    }
  }

  function installButton() {
    if (document.getElementById(BUTTON_ID)) {
      return;
    }

    const button = document.createElement("button");
    button.id = BUTTON_ID;
    button.type = "button";
    button.textContent = "Export chat";
    button.setAttribute("aria-label", "Export Gemini conversation snapshot");
    Object.assign(button.style, {
      position: "fixed",
      right: "14px",
      bottom: "18px",
      zIndex: "2147483647",
      padding: "11px 15px",
      border: "0",
      borderRadius: "999px",
      background: "#1f1f1f",
      color: "#fff",
      font: "600 14px/1.2 system-ui, sans-serif",
      boxShadow: "0 3px 16px rgba(0,0,0,.28)",
      cursor: "pointer",
    });
    button.addEventListener("click", () => void exportCurrentConversation(button));
    document.documentElement.appendChild(button);
  }

  installButton();
  new MutationObserver(installButton).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
