from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.product_connector_router_characterization_pr10_0 import (
    PRODUCT_CONNECTOR_ROUTER_SHAPE_OBSERVED,
    ProductConnectorRouterCharacterizationCollector,
)


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OBSERVABILITY = EXT / "service_worker_observability.js"
ROUTER = EXT / "service_worker_connector_router_characterization_pr10_0.js"


def test_router_overlay_loads_after_connector_metadata_and_before_patch_protocol() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")
    normalized = 'importScripts("service_worker_normalized_activity_stream_pr8_12.js");'
    connector = 'importScripts("service_worker_connector_lifecycle_pr10_0.js");'
    router = 'importScripts("service_worker_connector_router_characterization_pr10_0.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'

    assert normalized in source and connector in source and router in source and patch in source
    assert source.index(normalized) < source.index(connector) < source.index(router) < source.index(patch)


def test_router_characterization_is_scoped_to_explicit_api_tool_router() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert 'const PR100_CONNECTOR_ROUTER_NAME = "api_tool.call_tool";' in source
    assert 'role !== "assistant"' in source
    assert 'recipient !== PR100_CONNECTOR_ROUTER_NAME' in source
    assert "role === \"tool\"" not in source
    assert "generic tool" not in source.lower()


def test_router_identity_values_are_never_taken_from_payload_argument_scopes() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    for blocked in (
        '"arguments"',
        '"args"',
        '"parameters"',
        '"input"',
        '"request"',
        '"body"',
        '"result"',
        '"response"',
        '"content"',
    ):
        assert blocked in source

    assert "const nextBlocked = valueScopeBlocked || _pr100RouterBlockedValueScopes.has(normalizedKey);" in source
    assert "if (!nextBlocked)" in source
    assert "candidate_connector_id" in source
    assert "candidate_connector_name" in source
    assert "raw arguments/results/content" in source


def test_router_exports_only_bounded_structure_and_safe_identifier_candidates() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "_pr100RouterSafeKey" in source
    assert "_pr100RouterSafeIdentifier" in source
    assert "PR100_CONNECTOR_ROUTER_MAX_DEPTH = 4" in source
    assert "PR100_CONNECTOR_ROUTER_MAX_KEYS = 64" in source
    assert 'source_event_type: _pr100RouterStructuralSummary(shape)' in source
    assert "topLevelKeys" in source
    assert "identityKeyPaths" in source
    assert "toolKeyPaths" in source
    assert "rawText" not in source[source.index("_pr812Emit(context, {") :]
    assert "message.content" not in source


def test_router_promotes_only_explicit_envelope_identity_to_point_observation() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "if (!messageId || (!shape.connectorId && !shape.connectorName)) return;" in source
    assert 'type: "product_connector_observed"' in source
    assert "connector_id: shape.connectorId" in source
    assert "connector_name: shape.connectorName" in source
    assert "operation: shape.toolResource || shape.actionName" in source
    assert "product_connector_started" not in source
    assert "product_connector_completed" not in source


def test_router_shape_event_is_known_diagnostic_not_dropped_public_observation() -> None:
    collector = ProductConnectorRouterCharacterizationCollector()
    event = {
        "type": PRODUCT_CONNECTOR_ROUTER_SHAPE_OBSERVED,
        "observation_id": "router-shape-1",
        "tool_name": "api_tool.call_tool",
        "source_event_type": "top:tool_name,arguments;tool:tool_name",
    }

    assert collector.consume(event) is None
    assert collector.observations == ()
    assert collector.dropped_event_count == 0
