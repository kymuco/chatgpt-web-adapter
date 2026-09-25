// PR15.22 explicit production owner for product observations.
//
// Connector observation never exports raw metadata, arguments, results, credentials, URLs,
// cookies, authorization material, DOM, raw SSE, or private reasoning.
// Router characterization never exports raw arguments/results/content.
//
// Consolidates connector lifecycle, connector-router characterization, and
// generated-artifact observation. Production installs exactly one wrapper on
// PR8.12 message inspection and preserves historical observer side-effect order.

const PR100_CONNECTOR_OBSERVATION_SCHEMA = 1;
const _pr100EmissionState = new WeakMap();

function _pr100OwnObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function _pr100NestedObject(root, key) {
  const object = _pr100OwnObject(root);
  return object ? _pr100OwnObject(object[key]) : null;
}

function _pr100FirstString(values) {
  for (const value of values) {
    const text = _pr812OptionalString(value);
    if (text) return text;
  }
  return null;
}

function _pr100SafeIdentity(value) {
  return _pr812SafeEnum(value);
}

function _pr100State(state) {
  let value = _pr100EmissionState.get(state);
  if (value) return value;
  value = { emitted: new Set() };
  _pr100EmissionState.set(state, value);
  return value;
}

function _pr100EmitOnce(context, state, dedupeKey, event) {
  const local = _pr100State(state);
  if (local.emitted.has(dedupeKey)) return;
  local.emitted.add(dedupeKey);
  _pr812Emit(context, event);
}

function _pr100ConnectorEvidence(message) {
  const metadata = _pr100OwnObject(message?.metadata) || {};
  const connector = _pr100NestedObject(metadata, "connector");
  const app = _pr100NestedObject(metadata, "app");
  const plugin = _pr100NestedObject(metadata, "plugin");

  const connectorId = _pr100SafeIdentity(_pr100FirstString([
    metadata.connector_id,
    metadata.app_id,
    metadata.plugin_id,
    connector?.id,
    app?.id,
    plugin?.id
  ]));
  if (!connectorId) return null;

  const connectorName = _pr100SafeIdentity(_pr100FirstString([
    metadata.connector_name,
    metadata.app_name,
    metadata.plugin_name,
    connector?.name,
    app?.name,
    plugin?.name
  ]));

  const explicitActivityId = _pr100SafeIdentity(_pr100FirstString([
    metadata.connector_activity_id,
    metadata.app_activity_id,
    metadata.connector_call_id,
    metadata.app_call_id,
    metadata.tool_call_id,
    metadata.invocation_id,
    connector?.activity_id,
    connector?.call_id,
    app?.activity_id,
    app?.call_id,
    plugin?.activity_id,
    plugin?.call_id
  ]));

  const operation = _pr100SafeIdentity(_pr100FirstString([
    metadata.connector_operation,
    metadata.app_operation,
    metadata.plugin_operation,
    metadata.operation,
    metadata.function_name,
    connector?.operation,
    app?.operation,
    plugin?.operation
  ]));

  const explicitStatus = _pr100SafeIdentity(_pr100FirstString([
    metadata.connector_status,
    metadata.app_status,
    metadata.plugin_status,
    connector?.status,
    app?.status,
    plugin?.status
  ]));

  return { connectorId, connectorName, explicitActivityId, operation, explicitStatus };
}

function _pr100RequiredActionEvidence(message) {
  const metadata = _pr100OwnObject(message?.metadata) || {};
  const requiredAction = _pr100NestedObject(metadata, "required_action");
  const approval = _pr100NestedObject(metadata, "approval");

  const actionId = _pr100SafeIdentity(_pr100FirstString([
    metadata.action_id,
    metadata.required_action_id,
    metadata.approval_id,
    requiredAction?.action_id,
    requiredAction?.id,
    approval?.action_id,
    approval?.id
  ]));
  const actionType = _pr100SafeIdentity(_pr100FirstString([
    metadata.action_type,
    metadata.required_action_type,
    metadata.approval_type,
    requiredAction?.action_type,
    requiredAction?.type,
    approval?.action_type,
    approval?.type
  ]));
  if (!actionId || !actionType) return null;

  const explicitStatus = _pr100SafeIdentity(_pr100FirstString([
    metadata.action_status,
    metadata.required_action_status,
    metadata.approval_status,
    requiredAction?.status,
    approval?.status
  ]));
  return { actionId, actionType, explicitStatus };
}

function _pr100LifecycleEvent(prefix, status) {
  switch (status) {
    case "started":
    case "in_progress":
    case "running":
    case "pending":
      return `${prefix}_started`;
    case "updated":
      return `${prefix}_updated`;
    case "completed":
    case "finished":
    case "finished_successfully":
    case "success":
    case "succeeded":
      return `${prefix}_completed`;
    case "failed":
    case "error":
    case "cancelled":
    case "canceled":
    case "rejected":
      return `${prefix}_failed`;
    default:
      return `${prefix}_observed`;
  }
}

function _pr100InspectMessage(context, state, message) {
  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const messageId = _pr100SafeIdentity(message.id);
  const connector = _pr100ConnectorEvidence(message);
  const requiredAction = _pr100RequiredActionEvidence(message);

  let connectorActivityId = connector?.explicitActivityId || null;
  if (connector && !connectorActivityId && messageId) {
    // A unique product message id is enough for truthful point evidence, but not
    // enough to fabricate a request/result lifecycle across distinct messages.
    connectorActivityId = `connector-message:${messageId}`;
  }

  if (connector && connectorActivityId) {
    const eventType = connector.explicitActivityId
      ? _pr100LifecycleEvent("product_connector", connector.explicitStatus)
      : "product_connector_observed";
    const actionId = requiredAction?.actionId || null;
    const observationId = `pr10:${eventType}:${connectorActivityId}:${messageId || "no-message"}`;
    _pr100EmitOnce(context, state, observationId, {
      type: eventType,
      observation_id: observationId,
      connector_activity_id: connectorActivityId,
      connector_id: connector.connectorId,
      connector_name: connector.connectorName,
      operation: connector.operation,
      action_id: actionId
    });
  }

  if (requiredAction) {
    const eventType = _pr100LifecycleEvent(
      "product_required_action",
      requiredAction.explicitStatus
    );
    const observationId = `pr10:${eventType}:${requiredAction.actionId}:${messageId || "no-message"}`;
    _pr100EmitOnce(context, state, observationId, {
      type: eventType,
      observation_id: observationId,
      action_id: requiredAction.actionId,
      action_type: requiredAction.actionType,
      connector_activity_id: connectorActivityId,
      connector_id: connector?.connectorId || null
    });
  }
}



const PR100_CONNECTOR_ROUTER_SHAPE_EVENT = "product_connector_router_shape_observed";
const PR100_CONNECTOR_ROUTER_NAME = "api_tool.call_tool";
const PR100_CONNECTOR_ROUTER_MAX_TEXT = 200000;
const PR100_CONNECTOR_ROUTER_MAX_DEPTH = 4;
const PR100_CONNECTOR_ROUTER_MAX_KEYS = 64;

const _pr100RouterBlockedValueScopes = new Set([
  "arguments", "args", "parameters", "input", "request", "body",
  "result", "response", "content"
]);

const _pr100RouterTraversableEnvelopeKeys = new Set([
  "connector", "app", "plugin", "server", "mcp_server",
  "tool", "resource", "action", "function", "routing", "route", "target"
]);

const _pr100RouterIdentityContainers = new Set([
  "connector", "app", "plugin", "server", "mcp_server"
]);

const _pr100RouterToolContainers = new Set(["tool", "resource"]);
const _pr100RouterActionContainers = new Set(["action", "function"]);

const _pr100RouterIdentityKeyKinds = new Map([
  ["connector", "connector_name"],
  ["app", "connector_name"],
  ["plugin", "connector_name"],
  ["server", "connector_name"],
  ["mcp_server", "connector_name"],
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
  ["tool", "tool_resource"],
  ["resource", "tool_resource"],
  ["action", "action_name"],
  ["function", "action_name"],
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

function _pr100RouterSensitiveIdentifierText(text) {
  const lower = text.toLowerCase();
  return (
    lower.includes("token") || lower.includes("secret") ||
    lower.includes("authorization") || lower.includes("cookie") ||
    lower.includes("password") || lower.includes("credential")
  );
}

function _pr100RouterSafeIdentifier(value) {
  const text = _pr812OptionalString(value);
  if (!text || text.length > 128) return null;
  if (!/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  if (_pr100RouterSensitiveIdentifierText(text)) return null;
  return _pr812SafeEnum(text);
}

function _pr100RouterSafeDisplayName(value) {
  const text = _pr812OptionalString(value);
  if (!text || text.length > 128) return null;
  const lower = text.toLowerCase();
  if (_pr100RouterSensitiveIdentifierText(text)) return null;
  if (lower.includes("://") || lower.startsWith("www.") || text.includes("@")) return null;
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
      const parentKey = path.length ? path[path.length - 1] : null;
      const nextBlocked = valueScopeBlocked || _pr100RouterBlockedValueScopes.has(normalizedKey);
      let identityKind = _pr100RouterIdentityKeyKinds.get(normalizedKey);
      let toolKind = _pr100RouterToolKeyKinds.get(normalizedKey);

      if (!identityKind && _pr100RouterIdentityContainers.has(parentKey)) {
        if (normalizedKey === "id") identityKind = "connector_id";
        if (normalizedKey === "name") identityKind = "connector_name";
      }
      if (!toolKind && _pr100RouterToolContainers.has(parentKey)) {
        if (normalizedKey === "id" || normalizedKey === "name") toolKind = "tool_resource";
      }
      if (!toolKind && _pr100RouterActionContainers.has(parentKey)) {
        if (normalizedKey === "id" || normalizedKey === "name") toolKind = "action_name";
      }

      if (identityKind) {
        identityKeyPaths.add(keyPath);
        if (!nextBlocked) {
          const candidate = identityKind === "connector_name"
            ? _pr100RouterSafeDisplayName(value[key])
            : _pr100RouterSafeIdentifier(value[key]);
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
      if (
        !nextBlocked &&
        _pr100RouterTraversableEnvelopeKeys.has(normalizedKey) &&
        child && typeof child === "object"
      ) {
        visit(child, [...path, safeKey], depth + 1, false);
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

function _pr100RouterStructuralSummary(shape) {
  const parts = [];
  const top = _pr100RouterJoin(shape.topLevelKeys);
  const identity = _pr100RouterJoin(shape.identityKeyPaths);
  const tools = _pr100RouterJoin(shape.toolKeyPaths);
  if (top) parts.push(`top:${top}`);
  if (identity) parts.push(`identity:${identity}`);
  if (tools) parts.push(`tool:${tools}`);
  return parts.join(";").slice(0, 1200) || "router_envelope_no_whitelisted_keys";
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
      tool_name: PR100_CONNECTOR_ROUTER_NAME,
      source_event_type: "router_payload_not_json",
      payload_json: false
    });
    return;
  }

  const shape = _pr100RouterCharacterizeEnvelope(envelope);
  _pr812Emit(context, {
    type: PR100_CONNECTOR_ROUTER_SHAPE_EVENT,
    observation_id: observationId,
    router_name: PR100_CONNECTOR_ROUTER_NAME,
    tool_name: PR100_CONNECTOR_ROUTER_NAME,
    operation: shape.toolResource || shape.actionName,
    connector_id: shape.connectorId,
    connector_name: shape.connectorName,
    action_type: shape.actionName,
    source_event_type: _pr100RouterStructuralSummary(shape),
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



const PR101_ARTIFACT_EVENT = "product_artifact_observed";
const _pr101EmissionState = new WeakMap();

const _pr101ArtifactContainers = ["artifact", "file", "attachment", "asset", "generated_file"];
const _pr101ArtifactIdKeys = ["artifact_id", "file_id", "asset_id", "generated_file_id"];
const _pr101FilenameKeys = ["filename", "file_name"];
const _pr101MediaTypeKeys = ["media_type", "mime_type"];
const _pr101SizeKeys = ["size_bytes", "bytes", "file_size"];
const _pr101LocatorKeys = ["download_url", "download_uri", "signed_url", "url", "href"];

function _pr101OwnObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function _pr101OptionalString(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text || null;
}

function _pr101SafeArtifactId(value) {
  const text = _pr101OptionalString(value);
  if (!text || text.length > 192 || !/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  const lower = text.toLowerCase();
  if (
    lower.includes("token") || lower.includes("secret") ||
    lower.includes("credential") || lower.includes("authorization") ||
    lower.includes("cookie")
  ) return null;
  return text;
}

function _pr101SafeFilename(value) {
  const text = _pr101OptionalString(value);
  if (!text || text.length > 255 || text === "." || text === "..") return null;
  if (/[\\/\u0000-\u001f]/.test(text)) return null;
  return text;
}

function _pr101SafeMediaType(value) {
  const text = _pr101OptionalString(value);
  if (!text) return null;
  const normalized = text.toLowerCase();
  if (normalized.length > 128) return null;
  if (!/^[A-Za-z0-9!#$&^_.+-]+\/[A-Za-z0-9!#$&^_.+-]+$/.test(normalized)) return null;
  return normalized;
}

function _pr101SafeSize(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function _pr101FirstValue(object, keys) {
  if (!object) return null;
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(object, key) && object[key] != null) {
      return object[key];
    }
  }
  return null;
}

function _pr101HasLocator(object) {
  if (!object) return false;
  return _pr101LocatorKeys.some((key) => {
    const value = object[key];
    return typeof value === "string" && value.trim().length > 0;
  });
}

function _pr101CandidateFromObject(object, sourceOrigin) {
  object = _pr101OwnObject(object);
  if (!object) return null;

  const nestedCandidates = [];
  for (const key of _pr101ArtifactContainers) {
    const nested = _pr101OwnObject(object[key]);
    if (nested) nestedCandidates.push(nested);
  }
  const candidates = [object, ...nestedCandidates];

  for (const candidate of candidates) {
    const artifactId = _pr101SafeArtifactId(
      _pr101FirstValue(candidate, _pr101ArtifactIdKeys) ||
      (candidate !== object ? candidate.id : null)
    );
    if (!artifactId) continue;

    const filename = _pr101SafeFilename(
      _pr101FirstValue(candidate, _pr101FilenameKeys) ||
      (candidate !== object ? candidate.name : null)
    );
    const mediaType = _pr101SafeMediaType(_pr101FirstValue(candidate, _pr101MediaTypeKeys));
    const sizeBytes = _pr101SafeSize(_pr101FirstValue(candidate, _pr101SizeKeys));
    const downloadAvailable = _pr101HasLocator(candidate) || _pr101HasLocator(object) ||
      candidate.downloadable === true || object.downloadable === true;

    return {
      artifactId,
      filename,
      mediaType,
      sizeBytes,
      downloadAvailable,
      sourceOrigin
    };
  }
  return null;
}

function _pr101Candidates(message) {
  const output = [];
  const metadata = _pr101OwnObject(message?.metadata);
  const metadataCandidate = _pr101CandidateFromObject(metadata, "product_message_metadata");
  if (metadataCandidate) output.push(metadataCandidate);

  const content = _pr101OwnObject(message?.content);
  const parts = Array.isArray(content?.parts) ? content.parts.slice(0, 64) : [];
  for (const part of parts) {
    if (typeof part === "string") continue;
    const candidate = _pr101CandidateFromObject(part, "product_content_part");
    if (candidate) output.push(candidate);
  }

  const unique = new Map();
  for (const candidate of output) {
    if (!unique.has(candidate.artifactId)) unique.set(candidate.artifactId, candidate);
  }
  return Array.from(unique.values());
}

function _pr101State(state) {
  let local = _pr101EmissionState.get(state);
  if (local) return local;
  local = new Set();
  _pr101EmissionState.set(state, local);
  return local;
}

function _pr101InspectMessage(context, state, message) {
  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const messageId = _pr101SafeArtifactId(message.id) || "no-message";
  const emitted = _pr101State(state);
  for (const artifact of _pr101Candidates(message)) {
    const observationId = `pr10.1:${PR101_ARTIFACT_EVENT}:${artifact.artifactId}:${messageId}`;
    if (emitted.has(observationId)) continue;
    emitted.add(observationId);
    _pr812Emit(context, {
      type: PR101_ARTIFACT_EVENT,
      observation_id: observationId,
      artifact_id: artifact.artifactId,
      filename: artifact.filename,
      media_type: artifact.mediaType,
      size_bytes: artifact.sizeBytes,
      download_available: artifact.downloadAvailable,
      source_origin: artifact.sourceOrigin
    });
  }
}




function _pr10ProductObservationInspectMessage(context, state, message) {
  try {
    _pr100InspectMessage(context, state, message);
  } catch {
    // Connector observations are non-authoritative and may never perturb the turn.
  }

  try {
    _pr100RouterInspect(context, state, message);
  } catch {
    // Router characterization is evidence-only and may never perturb the turn.
  }

  try {
    _pr101InspectMessage(context, state, message);
  } catch {
    // Artifact observation is evidence-only and may never perturb the turn.
  }
}
