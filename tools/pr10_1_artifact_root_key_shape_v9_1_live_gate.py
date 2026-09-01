from __future__ import annotations

import argparse
import json
from typing import Any

import pr10_1_artifact_root_key_shape_v9_live_gate as v9


WIRE_REPAIR_SCHEMA = "CWA_PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_1_LIVE_GATE_V1"


def _wire_value(value: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in value:
        return value.get(camel)
    return value.get(snake)


def _safe_child_wire(value: Any) -> dict[str, Any] | None:
    """Normalize either raw camelCase or worker-sanitized snake_case child shape.

    The v9 browser worker already strips raw child keys/values and emits only bounded
    shape fields. Its safe-child boundary uses snake_case; the original Python gate
    expected camelCase and therefore degraded those already-safe fields to defaults.
    """
    if not isinstance(value, dict):
        return None

    key_shape_raw = _wire_value(value, "keyShape", "key_shape")
    key_shape = key_shape_raw if key_shape_raw in v9._KEY_SHAPES else "other"

    key_length_raw = _wire_value(value, "keyLengthBucket", "key_length_bucket")
    key_length_bucket = (
        key_length_raw if key_length_raw in v9._LENGTH_BUCKETS else "over_sixty_four"
    )

    child_kind_raw = _wire_value(value, "childValueKind", "child_value_kind")
    child_value_kind = child_kind_raw if child_kind_raw in v9._VALUE_KINDS else "other"

    child_bucket_raw = _wire_value(value, "childCardinalityBucket", "child_cardinality_bucket")
    child_cardinality_bucket = (
        child_bucket_raw if child_bucket_raw in v9._BUCKETS else "unknown"
    )

    child_object_raw = _wire_value(value, "childPlainObjectKind", "child_plain_object_kind")
    child_plain_object_kind = (
        child_object_raw if child_object_raw in v9._OBJECT_KINDS else "other_object"
    )

    known_name_raw = _wire_value(value, "knownStructuralKeyName", "known_structural_key_name")

    return {
        "key_shape": key_shape,
        "key_length_bucket": key_length_bucket,
        "known_structural_key_name": v9._safe_known_structural_name(known_name_raw),
        "child_value_kind": child_value_kind,
        "child_cardinality_bucket": child_cardinality_bucket,
        "child_plain_object_kind": child_plain_object_kind,
    }


def _install_wire_repair() -> None:
    # v9._safe_candidate resolves _safe_child from the v9 module global at call time.
    # Replacing that one normalizer repairs only report decoding; browser semantics,
    # support schema, authority budgets, and the live-read path remain unchanged.
    v9._safe_child = _safe_child_wire


def run_gate(*, expected_head: str | None, timeout: float, preflight_only: bool = False) -> dict[str, Any]:
    _install_wire_repair()
    report = v9.run_gate(
        expected_head=expected_head,
        timeout=timeout,
        preflight_only=preflight_only,
    )
    report["schema"] = WIRE_REPAIR_SCHEMA
    report["wire_normalization_repaired"] = True
    report["wire_child_shape_accepts_camel_case"] = True
    report["wire_child_shape_accepts_snake_case"] = True
    report["raw_root_keys_exported"] = False
    report["raw_root_values_exported"] = False
    report["child_values_exported"] = False

    if preflight_only:
        if report.get("characterization") == "ARTIFACT_ROOT_KEY_SHAPE_V9_SUPPORT_PREFLIGHT_ONLY_PROVEN":
            report["characterization"] = "ARTIFACT_ROOT_KEY_SHAPE_V9_1_WIRE_REPAIR_PREFLIGHT_ONLY_PROVEN"
        elif report.get("characterization") == "ARTIFACT_ROOT_KEY_SHAPE_V9_SUPPORT_PREFLIGHT_FAILED":
            report["characterization"] = "ARTIFACT_ROOT_KEY_SHAPE_V9_1_WIRE_REPAIR_PREFLIGHT_FAILED"
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PR10.1 v9.1 artifact-root key-shape wire-normalization repair gate")
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.preflight_only and not args.acknowledge_live_read:
        raise SystemExit("live read requires --acknowledge-live-read")
    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
