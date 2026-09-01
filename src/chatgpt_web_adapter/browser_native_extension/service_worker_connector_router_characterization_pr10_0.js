// PR10.0: characterize the product-level app/connector router envelope.
//
// The ChatGPT product can route connected Apps/Plugins through api_tool.call_tool.
// This layer inspects that router payload only inside the service worker. It never
// exports raw arguments/results/content. Outbound diagnostics contain only bounded
// structural key names and safe identifier-like values from explicit envelope
// fields. Identity is never inferred from ordering or from arbitrary tool payloads.

const PR100_CONNECTOR_ROUTER_SHAPE_EVENT = "product_connector_router_shape_observed";
const PR100_CONNECTOR_ROUTER_NAME = "api_tool.call_tool";
const PR100_CONNECTOR_ROUTER_MAX_TEXT = 200000;
const PR100_CONNECTOR_ROUTER_MAX_DEPTH = 4;
const PR100_CONNECTOR_ROUTER_MAX_KEYS = 64;

const _pr100RouterPriorInspectMessage = _pr812InspectMessage;

const _pr100RouterBlockedValueScopes = new Set([
  "arguments", "args", "parameters", "input", "request", "body",
  "result", "response", "content"
]);

const _pr100RouterIdentityKeyKinds = new Map([
  ["connector_id", "connector_id"],
  ["connectorid", "connector_id"],
  ["app_id", "connector_id"],
  ["appid", "connector_id"],
  ["plugin_id", "connector_id"],
  ["pluginid", "connector_id"],
  ["connector_name", "connector_name"],
  ["connectorname", "connector_name"],
  ["app_name", "connector_name"],
  ["appname", "connector_name"],
  ["plugin_name", "connector_name"],
  ["pluginname", "connector_name"],
  ["server_id", "connector_id"],
  ["serverid", "connector_id"],
  ["server_name", "connector_name"],
  ["servername", "connector_name"],
  ["mcp_server_id", "connector_id"],
  ["mcpserverid", "connector_id"],
  ["mcp_server_name", "connector_name"],
  ["mcpservername", "connector_name"]
]);

const _pr100RouterToolKeyKinds = new Map([
  ["tool_name", "tool_resource"],
  ["toolname", "tool_resource"],
  ["tool_resource", "tool_resource"],
  ["toolresource", "tool_resource"],
  ["resource_name", "tool_resource"],
  ["resourcename", "tool_resource"],
  ["action_name", "action_name"],
  ["actionname", "action_name"],
  ["function_name", "action_name"],
  ["functionname", "action_name"]
]);

function _pr100RouterNormalizedKey(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9_]+/g, "");
}

function _pr100RouterSafeKey(value) {
  const text = _pr812OptionalString(value);
  if (!text || text.length > 80) return null;
  if (!/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  return _pr812SafeEnum(text);
}

function _pr100RouterSafeIdentifier(value) {
  const text = _pr812OptionalString(value);
  if (!text || text.length > 128) return null;
  if (!/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  const lower = text.toLowerCase();
  if (
    lower.includes("token") || lower.includes("secret") ||
    lower.includes("authorization") || lower.includes("cookie") ||
    lower.includes("password") || lower.includes("credential")
  ) {
    return null;
  }
  return _pr812SafeEnum(text);
}

function _pr100RouterEnvelope(rawText) {
  if (typeof rawText !== "string") return null;
  const text = rawText.trim();
  if (!text || text.length > PR100_CONNECTOR_ROUTER_MAX_TEXT || !text.startsWith("{")) {
    return null;
  }
  try {
    const value = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

function _pr100RouterPath(path, key) {
  return [...path, key].join(".");
}

function _pr100RouterCharacterizeEnvelope(root) {
  const topLevelKeys = [];
  const envelopeKeyPaths = new Set();
  const identityKeyPaths = new Set();
  const toolKeyPaths = new Set();
  let connectorId = null;
  let connectorName = null;
  let toolResource = null;
  let actionName = null;

  for (const key of Object.keys(root).slice(0, PR100_CONNECTOR_ROUTER_MAX_KEYS)) {
    const safeKey = _pr100RouterSafeKey(key);
    if (safeKey) topLevelKeys.push(safeKey);
  }

  function visit(value, path = [], depth = 0, valueScopeBlocked = false) {
    if (!value || typeof value !== "object" || depth > PR100_CONNECTOR_ROUTER_MAX_DEPTH) return;
    if (Array.isArray(value)) {
      for (const item of value.slice(0, 32)) visit(item, path, depth + 1, valueScopeBlocked);
      return;
    }

    for (const key of Object.keys(value).slice(0, PR100_CONNECTOR_ROUTER_MAX_KEYS)) {
      const safeKey = _pr100RouterSafeKey(key);
      if (!safeKey) continue;
      const keyPath = _pr100RouterPath(path, safeKey);
      envelopeKeyPaths.add(keyPath);

      const normalizedKey = _pr100RouterNormalizedKey(key);
      const nextBlocked = valueScopeBlocked || _pr100RouterBlockedValueScopes.has(normalizedKey);
      const identityKind = _pr100RouterIdentityKeyKinds.get(normalizedKey);
      const toolKind = _pr100RouterToolKeyKinds.get(normalizedKey);

      if (identityKind) {
        identityKeyPaths.add(keyPath);
        if (!nextBlocked) {
          const candidate = _pr100RouterSafeIdentifier(value[key]);
          if (candidate && identityKind === "connector_id" && !connectorId) connectorId = candidate;
          if (candidate && identityKind === "connector_name" && !connectorName) connectorName = candidate;
        }
      }
      if (toolKind) {
        toolKeyPaths.add(keyPath);
        if (!nextBlocked) {
          const candidate = _pr100RouterSafeIdentifier(value[key]);
          if (candidate && toolKind === "tool_resource" && !toolResource) toolResource = candidate;
          if (candidate && toolKind === "action_name" && !actionName) actionName = candidate;
        }
      }

      const child = value[key];
      if (child && typeof child === "object") {
        visit(child, [...path, safeKey], depth + 1, nextBlocked);
      }
    }
  }

  visit(root);
  return {
    topLevelKeys: Array.from(new Set(topLevelKeys)).slice(0, 32),
    envelopeKeyPaths: Array.from(envelopeKeyPaths).slice(0, 64),
    identityKeyPaths: Array.from(identityKeyPaths).slice(0, 32),
    toolKeyPaths: Array.from(toolKeyPaths).slice(0, 32),
    connectorId,
    connectorName,
    toolResource,
    actionName
  };
}

function _pr100RouterJoin(values) {
  return values && values.length ? values.join(",") : null;
}

function _pr100RouterInspect(context, state, message) {
  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const role = _pr812OptionalString(message?.author?.role) || "";
  const recipient = _pr812OptionalString(message?.recipient) || "all";
  if (role !== "assistant" || recipient !== PR100_CONNECTOR_ROUTER_NAME) return;

  const rawText = _pr812RawTextForClassification(message?.content);
  const envelope = _pr100RouterEnvelope(rawText);
  const messageId = _pr100RouterSafeIdentifier(message?.id);
  const observationId = `pr10:connector-router-shape:${messageId || "no-message"}`;

  if (!envelope) {
    _pr812Emit(context, {
      type: PR100_CONNECTOR_ROUTER_SHAPE_EVENT,
      observation_id: observationId,
      router_name: PR100_CONNECTOR_ROUTER_NAME,
      payload_json: false
    });
    return;
  }

  const shape = _pr100RouterCharacterizeEnvelope(envelope);
  _pr812Emit(context, {
    type: PR100_CONNECTOR_ROUTER_SHAPE_EVENT,
    observation_id: observationId,
    router_name: PR100_CONNECTOR_ROUTER_NAME,
    payload_json: true,
    top_level_keys: _pr100RouterJoin(shape.topLevelKeys),
    envelope_key_paths: _pr100RouterJoin(shape.envelopeKeyPaths),
    identity_key_paths: _pr100RouterJoin(shape.identityKeyPaths),
    tool_key_paths: _pr100RouterJoin(shape.toolKeyPaths),
    candidate_connector_id: shape.connectorId,
    candidate_connector_name: shape.connectorName,
    candidate_tool_resource: shape.toolResource,
    candidate_action_name: shape.actionName
  });

  if (!messageId || (!shape.connectorId && !shape.connectorName)) return;
  const connectorActivityId = `connector-router-message:${messageId}`;
  const connectorObservationId = `pr10:product_connector_observed:${connectorActivityId}`;
  _pr812Emit(context, {
    type: "product_connector_observed",
    observation_id: connectorObservationId,
    connector_activity_id: connectorActivityId,
    connector_id: shape.connectorId,
    connector_name: shape.connectorName,
    operation: shape.toolResource || shape.actionName
  });
}

_pr812InspectMessage = function _pr100RouterInspectMessageOverlay(context, state, message) {
  _pr100RouterPriorInspectMessage(context, state, message);
  try {
    _pr100RouterInspect(context, state, message);
  } catch {
    // Router characterization is evidence-only and may never perturb a product turn.
  }
};
