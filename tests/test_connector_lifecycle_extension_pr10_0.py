from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CONNECTOR_JS = EXTENSION / "service_worker_product_observation.js"
OBSERVABILITY_JS = EXTENSION / "service_worker_observability.js"


def test_connector_overlay_requires_explicit_connector_or_app_identity() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "metadata.connector_id" in source
    assert "metadata.app_id" in source
    assert "metadata.plugin_id" in source
    assert "if (!connectorId) return null;" in source
    assert 'role === "tool"' not in source
    assert 'recipient !== "all"' not in source


def test_connector_overlay_does_not_use_generic_message_status_as_lifecycle() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "metadata.connector_status" in source
    assert "metadata.app_status" in source
    assert "metadata.plugin_status" in source
    assert "message.status" not in source
    assert "message.end_turn" not in source


def test_connector_overlay_supports_point_evidence_without_inferred_pairing() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "eventType = connector.explicitActivityId" in source
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


def test_connector_lifecycle_overlay_does_not_own_native_turn_dispatch() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")

    assert "const PR100_CONNECTOR_OBSERVATION_SCHEMA = 1;" in source
    assert "function _pr100InspectMessage(context, state, message)" in source
    assert "executeNativeTurn = async function" not in source
    assert "_pr100PriorExecuteNativeTurn" not in source
    assert "characterizeConnectorObservationSupport" not in source


def test_overlay_loads_after_single_pr812_response_owner() -> None:
    source = OBSERVABILITY_JS.read_text(encoding="utf-8")
    owner = 'importScripts("service_worker_response_activity.js");'
    product_observation = 'importScripts("service_worker_product_observation.js");'

    assert owner in source and product_observation in source
    assert source.index(owner) < source.index(product_observation)
    assert "service_worker_normalized_activity_patch_protocol_pr8_12.js" not in source

    owner_source = (EXTENSION / "service_worker_response_activity.js").read_text(
        encoding="utf-8"
    )
    assert "function _pr812PatchSelect(state, message)" in owner_source
    assert "function _pr812PatchApplyItem(" in owner_source


def test_product_observation_owner_installs_pr812_inspection_once() -> None:
    source = CONNECTOR_JS.read_text(encoding="utf-8")
    assert source.count("_pr812InspectMessage =") == 1
    assert "_pr100PriorInspectMessage" not in source
    assert "_pr100RouterPriorInspectMessage" not in source
    assert "_pr101PriorInspectMessage" not in source
