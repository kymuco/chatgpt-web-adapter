from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CONNECTOR_JS = EXTENSION / "service_worker_connector_lifecycle_pr10_0.js"
OBSERVABILITY_JS = EXTENSION / "service_worker_observability.js"


def test_connector_overlay_requires_explicit_connector_or_app_identity() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "metadata.connector_id" in source
    assert "metadata.app_id" in source
    assert "metadata.plugin_id" in source
    assert "if (!connectorId) return null;" in source
    assert "role === \"tool\"" not in source
    assert "recipient !== \"all\"" not in source


def test_connector_overlay_does_not_use_generic_message_status_as_lifecycle() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "metadata.connector_status" in source
    assert "metadata.app_status" in source
    assert "metadata.plugin_status" in source
    assert "message.status" not in source
    assert "message.end_turn" not in source


def test_connector_overlay_supports_point_evidence_without_inferred_pairing() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert 'eventType = connector.explicitActivityId' in source
    assert '"product_connector_observed"' in source
    assert "connector-message:${messageId}" in source
    assert "connector?.explicitActivityId || null" in source
    assert "messageId" in source


def test_required_action_requires_both_explicit_id_and_type() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "if (!actionId || !actionType) return null;" in source
    assert "metadata.action_id" in source
    assert "metadata.action_type" in source
    assert '"product_required_action"' in source


def test_overlay_never_selects_raw_sensitive_payload_fields_for_export() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    for forbidden_access in (
        "metadata.arguments",
        "metadata.args",
        "metadata.result",
        "metadata.authorization",
        "metadata.access_token",
        "metadata.refresh_token",
        "metadata.cookies",
        "metadata.signed_url",
        "message.content",
    ):
        assert forbidden_access not in source

    assert "raw metadata, arguments, results, credentials, URLs" in source
    assert "_pr812Emit(context, event)" in source


def test_connector_overlay_exposes_no_write_support_contract() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "const PR100_CONNECTOR_OBSERVATION_SCHEMA = 1;" in source
    assert "message?.characterizeConnectorObservationSupport !== true" in source
    assert "connectorObservationSupported: true" in source
    assert "connectorObservationSchemaVersion: PR100_CONNECTOR_OBSERVATION_SCHEMA" in source
    assert "explicitConnectorIdentityRequired: true" in source
    assert "explicitLifecycleCorrelationRequired: true" in source
    assert "genericToolActivityImpliesConnector: false" in source
    assert "rawConnectorPayloadExported: false" in source
    assert "connectorObservationGrantsApprovalAuthority: false" in source
    assert "connectorObservationChangesCanonicalFinality: false" in source
    assert "connectorObservationChangesRetryAuthority: false" in source
    assert "automaticWriteRetry: false" in source
    assert "fallbackTransport: null" in source
    assert "writePerformed: false" in source


def test_support_probe_delegates_every_non_probe_turn_to_prior_runtime() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "const _pr100PriorExecuteNativeTurn = executeNativeTurn;" in source
    assert "return _pr100PriorExecuteNativeTurn(message);" in source
    assert source.count("characterizeConnectorObservationSupport") == 1


def test_overlay_loads_after_normalized_stream_and_before_patch_protocol() -> None:
    source = OBSERVABILITY_JS.read_text(encoding="utf-8")
    activity = 'importScripts("service_worker_normalized_activity_stream_pr8_12.js");'
    connector = 'importScripts("service_worker_connector_lifecycle_pr10_0.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'

    assert activity in source and connector in source and patch in source
    assert source.index(activity) < source.index(connector) < source.index(patch)
