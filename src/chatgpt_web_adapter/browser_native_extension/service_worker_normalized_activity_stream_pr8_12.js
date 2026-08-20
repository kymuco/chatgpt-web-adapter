// PR8.12: normalized user-visible activity / tool-progress streaming.
//
// This layer extends the proven PR8.9 response observer without changing write,
// retry, Browser Authority, early-completion, or canonical-finality semantics.
// It exports only bounded normalized activity events and explicitly user-visible
// recap/display text. Raw tool arguments/results, raw SSE, hidden messages,
// credentials, DOM/HTML, and private `thoughts` content never leave the worker.

const PR812_ACTIVITY_SCHEMA_VERSION = 1;
const PR812_MAX_ACTIVITY_TEXT_CHARS = 12000;
const PR812_MAX_OPERATION_DEPTH = 7;

const _pr812PriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr812PriorExecuteNativeTurn = executeNativeTurn;

let _pr812RequestId = null;
let _pr812Sequence = 0;
const _pr812StateByStreamContext = new WeakMap();

function _pr812OptionalString(value) {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function _pr812SafeEnum(value) {
  const normalized = _pr812OptionalString(value);
  if (!normalized) return null;
  const safe = normalized.toLowerCase().replace(/[^a-z0-9_.:-]+/g, "_");
  return safe.slice(0, 96) || null;
}

function _pr812State(context) {
  let state = _pr812StateByStreamContext.get(context);
  if (state) return state;
  state = {
    currentPatchMessage: null,
    started: new Set(),
    completed: new Set(),
    textByActivity: new Map(),
    syntheticCounter: 0
  };
  _pr812StateByStreamContext.set(context, state);
  return state;
}

function _pr812ElapsedMs(context) {
  if (!context || !Number.isFinite(context.startedAt)) return null;
  return Math.max(0, Math.round(performance.now() - context.startedAt));
}

function _pr812Emit(context, event) {
  const requestId = _pr812RequestId;
  if (typeof requestId !== "string" || !requestId) return;
  _pr812Sequence += 1;
  postNative({
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "turn_event",
    request_id: requestId,
    event: {
      schema: PR812_ACTIVITY_SCHEMA_VERSION,
      sequence: _pr812Sequence,
      observed_at_ms: _pr812ElapsedMs(context),
      ...event
    }
  });
}

function _pr812ActivityId(state, message, prefix) {
  const id = _pr812OptionalString(message?.id);
  if (id) return `${prefix}:${id}`;
  state.syntheticCounter += 1;
  return `${prefix}:synthetic-${state.syntheticCounter}`;
}

function _pr812ActivityKindFromToolName(name) {
  const value = (_pr812OptionalString(name) || "").toLowerCase();
  if (!value) return "tool";
  if (value.includes("web") || value.includes("browser")) return "web";
  if (value.includes("file_search") || value.includes("files")) return "file_search";
  if (value.includes("research")) return "research";
  if (value.includes("python") || value.includes("code") || value.includes("jupyter")) return "code";
  if (value.includes("image")) return "image";
  if (value.includes("product")) return "product_search";
  if (value.includes("business") || value.includes("local")) return "local_search";
  return "tool";
}

function _pr812OperationFromObject(value, depth = 0) {
  if (!value || typeof value !== "object" || depth > PR812_MAX_OPERATION_DEPTH) return null;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 64)) {
      const found = _pr812OperationFromObject(item, depth + 1);
      if (found) return found;
    }
    return null;
  }

  const keys = Object.keys(value);
  const known = [
    "search_query", "image_query", "product_query", "businesses_query",
    "availability_query", "open", "click", "find", "screenshot",
    "calculator", "weather", "finance", "sports", "time"
  ];
  for (const key of known) {
    if (keys.includes(key)) return key;
  }
  const type = _pr812OptionalString(value.type);
  if (type && known.includes(type)) return type;
  const command = _pr812OptionalString(value.command);
  if (command && known.includes(command)) return command;

  for (const key of ["message", "data", "payload", "result", "tool", "arguments", "args"]) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
    const found = _pr812OperationFromObject(value[key], depth + 1);
    if (found) return found;
  }
  return null;
}

function _pr812OperationFromText(text) {
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 200000 || !trimmed.startsWith("{")) return null;
  try {
    return _pr812OperationFromObject(JSON.parse(trimmed));
  } catch {
    return null;
  }
}

function _pr812Label(kind, operation = null, completed = false) {
  const done = completed ? " complete" : "…";
  switch (operation) {
    case "search_query": return completed ? "Web search complete" : "Searching the web…";
    case "open":
    case "click":
    case "find":
    case "screenshot": return completed ? "Source reading complete" : "Reading sources…";
    case "image_query": return completed ? "Image search complete" : "Searching images…";
    case "product_query": return completed ? "Product search complete" : "Searching products…";
    case "businesses_query": return completed ? "Place search complete" : "Searching places…";
    case "availability_query": return completed ? "Availability check complete" : "Checking availability…";
    case "calculator": return completed ? "Calculation complete" : "Calculating…";
    case "weather": return completed ? "Weather check complete" : "Checking weather…";
    case "finance": return completed ? "Market check complete" : "Checking market data…";
    case "sports": return completed ? "Sports check complete" : "Checking sports data…";
    case "time": return completed ? "Time check complete" : "Checking time…";
    default: break;
  }
  if (kind === "web") return completed ? "Web activity complete" : "Using the web…";
  if (kind === "file_search") return completed ? "File search complete" : "Searching files…";
  if (kind === "research") return completed ? "Research step complete" : "Researching…";
  if (kind === "code") return completed ? "Code execution complete" : "Running code…";
  if (kind === "image") return completed ? "Image step complete" : "Working with images…";
  if (kind === "product_search") return completed ? "Product search complete" : "Searching products…";
  if (kind === "local_search") return completed ? "Place search complete" : "Searching places…";
  if (kind === "reasoning") return completed ? "Reasoning summary complete" : "Reasoning…";
  if (kind === "browsing_display") return completed ? "Browsing update complete" : "Browsing…";
  return completed ? `Tool activity${done}` : "Using a tool…";
}

function _pr812BoundedText(value) {
  if (typeof value !== "string") return "";
  const text = value.replace(/\u0000/g, "");
  if (text.length <= PR812_MAX_ACTIVITY_TEXT_CHARS) return text;
  return text.slice(0, PR812_MAX_ACTIVITY_TEXT_CHARS);
}

function _pr812VisibleActivityText(content) {
  if (!content || typeof content !== "object") return "";
  const contentType = _pr812OptionalString(content.content_type) || "";

  // `thoughts` is intentionally excluded: PR8.12 never exports private/raw
  // reasoning. `reasoning_recap` is a distinct user-facing recap surface.
  if (contentType === "reasoning_recap") {
    const direct = _pr812OptionalString(content.content);
    if (direct) return _pr812BoundedText(direct);
    const parts = Array.isArray(content.parts) ? content.parts : [];
    return _pr812BoundedText(parts.filter((part) => typeof part === "string").join(""));
  }

  if (contentType === "tether_browsing_display") {
    const pieces = [];
    for (const key of ["title", "text", "content"]) {
      const value = _pr812OptionalString(content[key]);
      if (value) pieces.push(value);
    }
    const parts = Array.isArray(content.parts) ? content.parts : [];
    for (const part of parts.slice(0, 16)) {
      if (typeof part === "string" && part.trim()) pieces.push(part);
      else if (part && typeof part === "object" && typeof part.text === "string" && part.text.trim()) {
        pieces.push(part.text);
      }
    }
    return _pr812BoundedText(Array.from(new Set(pieces)).join("\n"));
  }

  return "";
}

function _pr812RawTextForClassification(content) {
  if (!content || typeof content !== "object") return "";
  const parts = Array.isArray(content.parts) ? content.parts : [];
  let text = "";
  for (const part of parts.slice(0, 32)) {
    if (typeof part === "string") text += part;
    else if (part && typeof part === "object" && typeof part.text === "string") text += part.text;
  }
  if (!text && typeof content.text === "string") text = content.text;
  // Classification-only. This string is never put into a turn_event.
  return text;
}

function _pr812Start(context, state, activityId, kind, label, fields = {}) {
  if (state.started.has(activityId)) return;
  state.started.add(activityId);
  _pr812Emit(context, {
    type: "activity_started",
    activity_id: activityId,
    activity_kind: kind,
    label,
    ...fields
  });
}

function _pr812Complete(context, state, activityId, kind, label, fields = {}) {
  if (state.completed.has(activityId)) return;
  state.completed.add(activityId);
  _pr812Emit(context, {
    type: "activity_completed",
    activity_id: activityId,
    activity_kind: kind,
    label,
    ...fields
  });
}

function _pr812RecordActivityText(context, state, activityId, kind, label, text) {
  text = _pr812BoundedText(text);
  if (!text.trim()) return;
  _pr812Start(context, state, activityId, kind, label);

  const previous = state.textByActivity.get(activityId);
  if (previous === text) return;
  let type = "activity_text_snapshot";
  const event = {
    type,
    activity_id: activityId,
    activity_kind: kind,
    label
  };
  if (previous != null && text.startsWith(previous)) {
    event.type = "activity_text_delta";
    event.delta = text.slice(previous.length);
  } else if (previous != null) {
    event.type = "activity_text_revision";
    event.text = text;
  } else {
    event.text = text;
  }
  state.textByActivity.set(activityId, text);
  _pr812Emit(context, event);
}

function _pr812InspectMessage(context, state, message) {
  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const role = _pr812OptionalString(message?.author?.role) || "";
  const authorName = _pr812OptionalString(message?.author?.name);
  const recipient = _pr812OptionalString(message.recipient) || "all";
  const content = message.content && typeof message.content === "object" ? message.content : {};
  const contentType = _pr812OptionalString(content.content_type) || "";

  if (role === "assistant" && contentType === "thoughts") {
    const activityId = _pr812ActivityId(state, message, "thinking");
    _pr812Start(context, state, activityId, "reasoning", "Thinking…", {
      source_content_type: "thoughts"
    });
    return;
  }

  if (role === "assistant" && recipient === "all" && contentType === "reasoning_recap") {
    const activityId = _pr812ActivityId(state, message, "reasoning");
    const text = _pr812VisibleActivityText(content);
    _pr812RecordActivityText(context, state, activityId, "reasoning", "Reasoning summary", text);
    if (message.end_turn === true || message.status === "finished_successfully" || message.status === "completed") {
      _pr812Complete(context, state, activityId, "reasoning", "Reasoning summary complete");
    }
    return;
  }

  if (contentType === "tether_browsing_display") {
    const activityId = _pr812ActivityId(state, message, "browsing-display");
    const text = _pr812VisibleActivityText(content);
    _pr812RecordActivityText(context, state, activityId, "browsing_display", "Browsing update", text);
    if (message.end_turn === true || message.status === "finished_successfully" || role === "tool") {
      _pr812Complete(context, state, activityId, "browsing_display", "Browsing update complete");
    }
    return;
  }

  if (role === "assistant" && recipient !== "all") {
    const kind = _pr812ActivityKindFromToolName(recipient);
    const raw = _pr812RawTextForClassification(content);
    const operation = _pr812OperationFromText(raw) || _pr812OperationFromObject(message?.metadata);
    const activityId = _pr812ActivityId(state, message, `tool-${kind}`);
    _pr812Start(context, state, activityId, kind, _pr812Label(kind, operation, false), {
      tool_name: _pr812SafeEnum(recipient),
      operation: _pr812SafeEnum(operation)
    });
    return;
  }

  if (role === "tool") {
    const toolName = authorName || recipient;
    const kind = _pr812ActivityKindFromToolName(toolName);
    const operation = _pr812OperationFromObject(message?.metadata) ||
      _pr812OperationFromText(_pr812RawTextForClassification(content));
    const activityId = _pr812ActivityId(state, message, `tool-result-${kind}`);
    _pr812Complete(context, state, activityId, kind, _pr812Label(kind, operation, true), {
      tool_name: _pr812SafeEnum(toolName),
      operation: _pr812SafeEnum(operation),
      source_content_type: _pr812SafeEnum(contentType)
    });
  }
}

function _pr812CollectMessages(value, output, depth = 0) {
  if (value == null || depth > 7) return;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 128)) _pr812CollectMessages(item, output, depth + 1);
    return;
  }
  if (typeof value !== "object") return;
  if (value.author && value.content) output.push(value);
  for (const key of ["message", "messages", "data", "result", "payload", "turn", "v", "value"]) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      _pr812CollectMessages(value[key], output, depth + 1);
    }
  }
}

function _pr812PatchSelect(state, message) {
  if (!message || typeof message !== "object") return;
  state.currentPatchMessage = {
    ...message,
    content: message.content && typeof message.content === "object"
      ? { ...message.content }
      : { content_type: "text", parts: [] }
  };
}

function _pr812PatchApplyItem(context, state, item) {
  if (!item || typeof item !== "object") return;
  const path = typeof item.p === "string" ? item.p : null;
  const value = item.v;
  if (value && typeof value === "object" && !Array.isArray(value) && value.message) {
    _pr812PatchSelect(state, value.message);
    _pr812InspectMessage(context, state, state.currentPatchMessage);
    return;
  }
  if (!state.currentPatchMessage || path == null) return;

  if (path === "/message/content/parts/0" && typeof value === "string") {
    const content = state.currentPatchMessage.content || {};
    const parts = Array.isArray(content.parts) ? [...content.parts] : [];
    const previous = typeof parts[0] === "string" ? parts[0] : "";
    parts[0] = previous + value;
    state.currentPatchMessage.content = { ...content, parts };
    _pr812InspectMessage(context, state, state.currentPatchMessage);
  } else if (path === "/message/content" && value && typeof value === "object") {
    state.currentPatchMessage.content = { ...value };
    _pr812InspectMessage(context, state, state.currentPatchMessage);
  } else if (path === "/message/status") {
    state.currentPatchMessage.status = value;
    _pr812InspectMessage(context, state, state.currentPatchMessage);
  } else if (path === "/message/end_turn") {
    state.currentPatchMessage.end_turn = value;
    _pr812InspectMessage(context, state, state.currentPatchMessage);
  } else if (path === "/message/metadata" && value && typeof value === "object") {
    state.currentPatchMessage.metadata = {
      ...(state.currentPatchMessage.metadata || {}),
      ...value
    };
    _pr812InspectMessage(context, state, state.currentPatchMessage);
  }
}

function _pr812InspectPatch(context, state, payload) {
  if (!payload || typeof payload !== "object") return;
  _pr812PatchApplyItem(context, state, payload);
  if (Array.isArray(payload.v)) {
    for (const item of payload.v.slice(0, 128)) _pr812PatchApplyItem(context, state, item);
  }
}

function _pr812InspectTypedOperation(context, state, payload) {
  if (!payload || typeof payload !== "object") return;
  const type = _pr812OptionalString(payload.type);
  if (!type || ["message_marker", "stream_handoff", "server_ste_metadata"].includes(type)) return;
  const operation = _pr812OperationFromObject(payload);
  if (!operation) return;
  state.syntheticCounter += 1;
  const kind = _pr812ActivityKindFromToolName(type.includes("web") ? "web" : type);
  const activityId = `typed-${kind}:${state.syntheticCounter}`;
  _pr812Start(context, state, activityId, kind, _pr812Label(kind, operation, false), {
    operation: _pr812SafeEnum(operation),
    source_event_type: _pr812SafeEnum(type)
  });
}

_pr89BrowserStreamProcessSseEvent = async function _pr812ProcessSseEvent(context, block) {
  const result = await _pr812PriorProcessSseEvent(context, block);
  if (_pr812RequestId === null) return result;

  let data = "";
  try {
    const dataLines = String(block || "").split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart());
    data = dataLines.join("\n").trim();
  } catch {
    return result;
  }
  if (!data || data === "[DONE]") return result;

  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return result;
  }

  const state = _pr812State(context);
  try {
    const messages = [];
    _pr812CollectMessages(payload, messages);
    const seen = new Set();
    for (const message of messages) {
      if (seen.has(message)) continue;
      seen.add(message);
      _pr812InspectMessage(context, state, message);
    }
    _pr812InspectPatch(context, state, payload);
    _pr812InspectTypedOperation(context, state, payload);
  } catch {
    // Activity observation is best-effort and can never perturb the write path.
  }
  return result;
};

executeNativeTurn = async function _pr812ExecuteNativeTurn(message) {
  const streaming = message?.streamTextObservations === true;
  if (!streaming) return _pr812PriorExecuteNativeTurn(message);

  const requestId = typeof message?.request_id === "string" ? message.request_id.trim() : "";
  if (!requestId) return _pr812PriorExecuteNativeTurn(message);
  if (_pr812RequestId !== null) {
    throw new Error("PR8_12_ACTIVITY_STREAM_ALREADY_ACTIVE");
  }

  _pr812RequestId = requestId;
  _pr812Sequence = 0;
  try {
    return await _pr812PriorExecuteNativeTurn(message);
  } finally {
    _pr812RequestId = null;
  }
};
