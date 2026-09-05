/*
 * Read-only Gemini web conversation snapshot probe.
 *
 * Usage (while signed in on https://gemini.google.com):
 *   await geminiConversationSnapshot(
 *     "https://gemini.google.com/app/<chat-id>",
 *     { name: "conversation" },
 *   );
 *
 * This deliberately performs no product writes. It reads the target conversation
 * through Gemini's same-origin conversation-history RPC and downloads:
 *   - a summary-ready Markdown context,
 *   - a normalized JSON messages file,
 *   - the decoded raw RPC payload (unless includeRawPayload is false).
 */

(() => {
  "use strict";

  const GEMINI_HOST = "gemini.google.com";
  const READ_CHAT_RPC = "hNvQHb";
  const DEFAULT_TURN_LIMIT = 1000;

  function requiredString(value, name) {
    if (typeof value !== "string" || !value.trim()) {
      throw new TypeError(`${name} must be a non-empty string`);
    }
    return value.trim();
  }

  function parseGeminiConversationUrl(value) {
    const url = new URL(requiredString(value, "conversationUrl"));
    if (url.protocol !== "https:" || url.hostname !== GEMINI_HOST) {
      throw new Error("Gemini conversation URL must use https://gemini.google.com");
    }

    const parts = url.pathname.split("/").filter(Boolean);
    let index = 0;
    let accountPrefix = "";

    if (parts[index] === "u") {
      const accountIndex = parts[index + 1];
      if (!/^\d+$/.test(accountIndex || "")) {
        throw new Error("Gemini /u/ route is missing a numeric account index");
      }
      accountPrefix = `/u/${accountIndex}`;
      index += 2;
    }

    let gemId = null;
    let chatId = null;
    if (parts[index] === "app" && parts[index + 1]) {
      chatId = parts[index + 1];
      index += 2;
    } else if (
      parts[index] === "gem" &&
      parts[index + 1] &&
      parts[index + 2]
    ) {
      gemId = parts[index + 1];
      chatId = parts[index + 2];
      index += 3;
    } else {
      throw new Error(
        "Unsupported Gemini conversation URL. Expected /app/<id> or /gem/<gem-id>/<id>, optionally under /u/<account-index>/",
      );
    }

    if (index !== parts.length) {
      throw new Error("Gemini conversation URL contains an unsupported trailing path");
    }

    const rpcConversationId = chatId.startsWith("c_") ? chatId : `c_${chatId}`;
    return {
      url,
      accountPrefix,
      gemId,
      chatId,
      rpcConversationId,
      sourcePath: url.pathname,
    };
  }

  function decodeJsonStringFragment(value) {
    if (typeof value !== "string") {
      return null;
    }
    try {
      return JSON.parse(`"${value.replace(/"/g, '\\"')}"`);
    } catch {
      return value;
    }
  }

  function extractQuotedBootstrapValue(html, key) {
    const pattern = new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`);
    const match = html.match(pattern);
    return match ? decodeJsonStringFragment(match[1]) : null;
  }

  function extractBootstrap(html) {
    if (typeof html !== "string" || !html) {
      throw new Error("Gemini bootstrap HTML is empty");
    }

    let at = null;
    if (typeof DOMParser !== "undefined") {
      const doc = new DOMParser().parseFromString(html, "text/html");
      const input = doc.querySelector('input[name="at"]');
      if (input && typeof input.value === "string" && input.value.trim()) {
        at = input.value.trim();
      }
    }

    at = at || extractQuotedBootstrapValue(html, "SNlM0e");
    const buildLabel = extractQuotedBootstrapValue(html, "cfb2h");
    const sessionId = extractQuotedBootstrapValue(html, "FdrFJe");

    if (!at) {
      throw new Error(
        "Gemini anti-CSRF token (SNlM0e) was not found. Make sure this browser profile is signed in and the target chat is accessible.",
      );
    }

    return { at, buildLabel, sessionId };
  }

  function walkForRpcPayload(value, rpcId, results) {
    if (!Array.isArray(value)) {
      return;
    }

    if (
      value.length >= 3 &&
      value[0] === "wrb.fr" &&
      value[1] === rpcId &&
      typeof value[2] === "string"
    ) {
      try {
        results.push(JSON.parse(value[2]));
      } catch (error) {
        throw new Error(`Gemini ${rpcId} payload was not valid JSON: ${error}`);
      }
    }

    for (const item of value) {
      if (Array.isArray(item)) {
        walkForRpcPayload(item, rpcId, results);
      }
    }
  }

  function parseBatchExecuteResponse(text, rpcId = READ_CHAT_RPC) {
    const source = requiredString(text, "batch response").replace(/^\)\]\}'\s*/, "");
    const results = [];

    for (const rawLine of source.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || /^\d+$/.test(line) || (!line.startsWith("[") && !line.startsWith("{"))) {
        continue;
      }
      let frame;
      try {
        frame = JSON.parse(line);
      } catch {
        continue;
      }
      walkForRpcPayload(frame, rpcId, results);
    }

    if (!results.length) {
      throw new Error(`Gemini batch response did not contain RPC ${rpcId}`);
    }
    return results;
  }

  function nested(value, path) {
    let current = value;
    for (const key of path) {
      if (current == null || !(key in Object(current))) {
        return undefined;
      }
      current = current[key];
    }
    return current;
  }

  function cleanText(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function firstAssistantCandidate(turn) {
    const candidates = nested(turn, [3, 0]);
    if (!Array.isArray(candidates)) {
      return null;
    }
    for (const candidate of candidates) {
      if (!Array.isArray(candidate)) {
        continue;
      }
      const text = cleanText(nested(candidate, [1, 0]));
      if (!text) {
        continue;
      }
      const candidateId = typeof candidate[0] === "string" ? candidate[0] : null;
      return { text, candidateId };
    }
    return null;
  }

  function normalizeConversationPayload(payload, conversationId) {
    const turns = nested(payload, [0]);
    if (!Array.isArray(turns)) {
      throw new Error("Gemini conversation payload does not contain a recognized turns array");
    }

    const messages = [];
    const chronologicalTurns = [...turns].reverse();

    chronologicalTurns.forEach((turn, chronologicalIndex) => {
      if (!Array.isArray(turn)) {
        return;
      }

      const requestId = typeof nested(turn, [0, 1]) === "string" ? nested(turn, [0, 1]) : null;
      const userText = cleanText(nested(turn, [2, 0, 0]));
      if (userText) {
        messages.push({
          role: "user",
          text: userText,
          turn_index: chronologicalIndex,
          request_id: requestId,
        });
      }

      const assistant = firstAssistantCandidate(turn);
      if (assistant) {
        messages.push({
          role: "assistant",
          text: assistant.text,
          turn_index: chronologicalIndex,
          request_id: requestId,
          candidate_id: assistant.candidateId,
        });
      }
    });

    if (!messages.length) {
      throw new Error(
        "Gemini conversation payload was fetched, but no text user/assistant messages matched the known shape. Keep the raw payload and update the parser before trusting an empty summary context.",
      );
    }

    return {
      provider: "gemini-web",
      conversation_id: conversationId,
      ordering: "chronological",
      messages,
    };
  }

  function renderMarkdownContext(messages) {
    return (
      messages
        .filter((message) => ["user", "assistant"].includes(message.role) && cleanText(message.text))
        .map((message) => `## ${message.role.toUpperCase()}\n\n${message.text.trim()}`)
        .join("\n\n---\n\n") + "\n"
    );
  }

  function sanitizeName(value) {
    const name = requiredString(value, "name");
    const cleaned = name.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").replace(/\s+/g, "_");
    if (!cleaned || cleaned === "." || cleaned === "..") {
      throw new Error("name is not usable as a file-name prefix");
    }
    return cleaned;
  }

  function downloadTextFile(filename, content, mediaType) {
    const blob = new Blob([content], { type: mediaType });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = filename;
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }

  function jsonText(value) {
    return `${JSON.stringify(value, null, 2)}\n`;
  }

  async function fetchBootstrap(route) {
    const response = await fetch(route.url.href, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      redirect: "follow",
    });
    if (!response.ok) {
      throw new Error(`Failed to open Gemini conversation page (${response.status})`);
    }
    if (new URL(response.url).hostname !== GEMINI_HOST) {
      throw new Error("Gemini conversation page redirected away from gemini.google.com; sign in first");
    }
    return extractBootstrap(await response.text());
  }

  async function readConversationRpc(route, bootstrap, turnLimit) {
    const rpcUrl = new URL(
      `${route.accountPrefix}/_/BardChatUi/data/batchexecute`,
      "https://gemini.google.com",
    );
    rpcUrl.searchParams.set("rpcids", READ_CHAT_RPC);
    rpcUrl.searchParams.set("source-path", route.sourcePath);
    rpcUrl.searchParams.set("hl", document.documentElement.lang || "en");
    rpcUrl.searchParams.set("rt", "c");
    rpcUrl.searchParams.set("_reqid", String(Math.floor(100000 + Math.random() * 900000)));
    if (bootstrap.buildLabel) {
      rpcUrl.searchParams.set("bl", bootstrap.buildLabel);
    }
    if (bootstrap.sessionId) {
      rpcUrl.searchParams.set("f.sid", bootstrap.sessionId);
    }

    const rpcArgs = JSON.stringify([
      route.rpcConversationId,
      turnLimit,
      null,
      1,
      [1],
      [4],
      null,
      1,
    ]);
    const fReq = JSON.stringify([[[READ_CHAT_RPC, rpcArgs, null, "generic"]]]);
    const body = new URLSearchParams({
      "f.req": fReq,
      at: bootstrap.at,
    });

    const response = await fetch(rpcUrl.href, {
      method: "POST",
      credentials: "include",
      headers: {
        accept: "*/*",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-same-domain": "1",
      },
      body: body.toString(),
    });
    const responseText = await response.text();
    if (!response.ok) {
      throw new Error(`Gemini conversation-history RPC failed (${response.status})`);
    }

    const decoded = parseBatchExecuteResponse(responseText, READ_CHAT_RPC);
    const payload = decoded.find((candidate) => Array.isArray(nested(candidate, [0])));
    if (!payload) {
      throw new Error("Gemini history RPC returned data, but no recognized conversation payload was found");
    }
    return { payload, decodedCount: decoded.length };
  }

  async function geminiConversationSnapshot(conversationUrl, options = {}) {
    if (location.hostname !== GEMINI_HOST) {
      throw new Error("Run this probe from an authenticated https://gemini.google.com tab");
    }

    const route = parseGeminiConversationUrl(conversationUrl);
    const turnLimit = Number.isInteger(options.turnLimit) && options.turnLimit > 0
      ? options.turnLimit
      : DEFAULT_TURN_LIMIT;
    const name = sanitizeName(options.name || "conversation");
    const includeRawPayload = options.includeRawPayload !== false;

    const bootstrap = await fetchBootstrap(route);
    const { payload, decodedCount } = await readConversationRpc(route, bootstrap, turnLimit);
    const normalized = normalizeConversationPayload(payload, route.rpcConversationId);
    const retrievedAt = new Date().toISOString();
    const messagesDocument = {
      schema: "cwa.experimental.gemini.messages.v1",
      provider: normalized.provider,
      source_url: route.url.href,
      conversation_id: normalized.conversation_id,
      retrieved_at: retrievedAt,
      rpc: {
        id: READ_CHAT_RPC,
        decoded_payload_count: decodedCount,
      },
      ordering: normalized.ordering,
      messages: normalized.messages,
    };

    const contextFilename = `${name}_gemini_chat_context.md`;
    const messagesFilename = `${name}_gemini_chat_messages.json`;
    const rawFilename = `${name}_gemini_chat_payload.json`;

    downloadTextFile(
      contextFilename,
      renderMarkdownContext(normalized.messages),
      "text/markdown;charset=utf-8",
    );
    downloadTextFile(
      messagesFilename,
      jsonText(messagesDocument),
      "application/json;charset=utf-8",
    );
    if (includeRawPayload) {
      downloadTextFile(rawFilename, jsonText(payload), "application/json;charset=utf-8");
    }

    return {
      ok: true,
      provider: "gemini-web",
      conversation_id: route.rpcConversationId,
      message_count: normalized.messages.length,
      files: {
        context: contextFilename,
        messages: messagesFilename,
        raw_payload: includeRawPayload ? rawFilename : null,
      },
    };
  }

  const testing = {
    parseGeminiConversationUrl,
    extractBootstrap,
    parseBatchExecuteResponse,
    normalizeConversationPayload,
    renderMarkdownContext,
  };

  if (typeof window !== "undefined") {
    window.geminiConversationSnapshot = geminiConversationSnapshot;
    window.__geminiConversationSnapshotTesting = testing;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = testing;
  }
})();
