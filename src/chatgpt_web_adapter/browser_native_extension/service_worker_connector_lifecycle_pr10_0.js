// PR10.0: bounded app/connector + required-action product observation overlay.
//
// This layer observes only explicit product metadata identifiers. It never treats
// generic tool activity as a connector, never infers request/result pairing from
// ordering, and never exports raw metadata, arguments, results, credentials, URLs,
// cookies, authorization material, DOM, raw SSE, or private reasoning.

const _pr100PriorInspectMessage = _pr812InspectMessage;
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

_pr812InspectMessage = function _pr100InspectMessageOverlay(context, state, message) {
  _pr100PriorInspectMessage(context, state, message);
  try {
    _pr100InspectMessage(context, state, message);
  } catch {
    // PR10.0 observations are non-authoritative and may never perturb the turn.
  }
};
