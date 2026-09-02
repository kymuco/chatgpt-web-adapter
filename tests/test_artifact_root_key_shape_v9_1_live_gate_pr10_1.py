from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pr10_1_artifact_root_key_shape_v9_live_gate as v9  # noqa: E402
from pr10_1_artifact_root_key_shape_v9_1_live_gate import (  # noqa: E402
    WIRE_REPAIR_SCHEMA,
    _install_wire_repair,
    _safe_child_wire,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_root_key_shape_v9_pr10_1.js"
GATE = TOOLS / "pr10_1_artifact_root_key_shape_v9_1_live_gate.py"


def test_v9_1_documents_actual_worker_snake_case_child_boundary() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "key_shape:keyShape" in source
    assert "key_length_bucket:keyLengthBucket" in source
    assert "known_structural_key_name:_pr101ArtifactRootKeyShapeV9SafeName" in source
    assert "child_value_kind:childValueKind" in source
    assert "child_cardinality_bucket:childCardinalityBucket" in source
    assert "child_plain_object_kind:childPlainObjectKind" in source


def test_v9_1_safe_child_accepts_worker_sanitized_snake_case() -> None:
    child = _safe_child_wire(
        {
            "key_shape": "opaque_token",
            "key_length_bucket": "seventeen_to_thirty_two",
            "known_structural_key_name": None,
            "child_value_kind": "array",
            "child_cardinality_bucket": "two_to_four",
            "child_plain_object_kind": "array",
            "raw_key": "opaque_secret_key_that_must_not_leave",
            "child_value": ["private"],
            "url_value": "https://example.invalid/private",
        }
    )
    assert child == {
        "key_shape": "opaque_token",
        "key_length_bucket": "seventeen_to_thirty_two",
        "known_structural_key_name": None,
        "child_value_kind": "array",
        "child_cardinality_bucket": "two_to_four",
        "child_plain_object_kind": "array",
    }
    serialized = json.dumps(child, sort_keys=True)
    assert "opaque_secret_key_that_must_not_leave" not in serialized
    assert "example.invalid" not in serialized
    assert "private" not in serialized


def test_v9_1_safe_child_keeps_camel_case_compatibility_and_whitelist() -> None:
    child = _safe_child_wire(
        {
            "keyShape": "known_structural",
            "keyLengthBucket": "up_to_8",
            "knownStructuralKeyName": "type",
            "childValueKind": "string",
            "childCardinalityBucket": "not_applicable",
            "childPlainObjectKind": "not_object",
        }
    )
    assert child is not None
    assert child["known_structural_key_name"] == "type"
    assert child["child_value_kind"] == "string"

    unknown = _safe_child_wire(
        {
            "key_shape": "known_structural",
            "known_structural_key_name": "privateUnknownKey",
        }
    )
    assert unknown is not None
    assert unknown["known_structural_key_name"] is None


def test_v9_1_installed_repair_fixes_existing_v9_candidate_decoder() -> None:
    original = v9._safe_child
    try:
        _install_wire_repair()
        candidate = v9._safe_candidate(
            {
                "index": 0,
                "relationKind": "turn_descendant",
                "fiberDepth": 25,
                "componentName": "SMn",
                "sourceKind": "update_queue",
                "sourceNestedDepth": 5,
                "sourceContainerKind": "object",
                "artifactRootKeyName": "attachments",
                "rootValueKind": "object",
                "rootCardinalityBucket": "two_to_four",
                "rootPlainObjectKind": "plain_object",
                "knownStructuralChildKeyNames": ["type"],
                "keyShapeCounts": {"known_structural": 1, "opaque_token": 3},
                "childValueKindCounts": {"array": 2, "boolean": 1, "string": 1},
                "traversableChildCountBucket": "two_to_four",
                "childSummaries": [
                    {
                        "key_shape": "known_structural",
                        "key_length_bucket": "up_to_8",
                        "known_structural_key_name": "type",
                        "child_value_kind": "string",
                        "child_cardinality_bucket": "not_applicable",
                        "child_plain_object_kind": "not_object",
                    },
                    {
                        "key_shape": "opaque_token",
                        "key_length_bucket": "seventeen_to_thirty_two",
                        "known_structural_key_name": None,
                        "child_value_kind": "array",
                        "child_cardinality_bucket": "two_to_four",
                        "child_plain_object_kind": "array",
                    },
                ],
            }
        )
        assert candidate is not None
        assert candidate["child_summaries"][0]["key_shape"] == "known_structural"
        assert candidate["child_summaries"][0]["known_structural_key_name"] == "type"
        assert candidate["child_summaries"][0]["child_value_kind"] == "string"
        assert candidate["child_summaries"][1]["key_shape"] == "opaque_token"
        assert candidate["child_summaries"][1]["child_value_kind"] == "array"
    finally:
        v9._safe_child = original


def test_v9_1_gate_reuses_v9_zero_authority_path() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "v9.run_gate(" in source
    assert "--acknowledge-live-read" in source
    assert "WIRE_REPAIR_SCHEMA" in source
    assert "wire_normalization_repaired" in source
    assert "raw_root_keys_exported" in source
    assert "raw_root_values_exported" in source
    assert "child_values_exported" in source
    assert "send_text_observed(" not in source


def test_v9_1_schema_name_is_distinct_from_historical_v9_report() -> None:
    assert WIRE_REPAIR_SCHEMA == "CWA_PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_1_LIVE_GATE_V1"
