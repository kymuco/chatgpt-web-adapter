from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


FIBER_STATE_SCHEMA = 6
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": FIBER_STATE_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "fiber_graph_bounded": True,
    "artifact_relevant_keys_only": True,
    "accessor_properties_skipped": True,
    "dom_state_node_values_excluded": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "attribute_values_exported": False,
    "react_prop_values_exported": False,
    "react_state_values_exported": False,
    "locator_values_exported": False,
    "click_performed": False,
    "download_attempted": False,
    "write_performed": False,
}


def _safe_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 80 or not text.isascii():
        return None
    if not all(ch.isalnum() or ch in "_.:-" for ch in text):
        return None
    return text


def _safe_name_list(value: Any, *, max_items: int = 96) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        name = _safe_name(item)
        if name is None:
            continue
        output.append(name)
        if len(output) >= max_items:
            break
    return sorted(set(output))


def _safe_count(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, maximum)


def _safe_depth(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, maximum)


def _safe_hit(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    relation_kind = value.get("relationKind")
    if relation_kind not in {"turn_root", "turn_ancestor", "turn_descendant"}:
        relation_kind = "turn_descendant"
    source_kind = value.get("sourceKind")
    if source_kind not in {
        "memoized_props",
        "pending_props",
        "memoized_state",
        "update_queue",
        "dependencies",
    }:
        source_kind = "memoized_state"
    container_kind = value.get("containerKind")
    if container_kind not in {"object", "array"}:
        container_kind = "object"
    return {
        "index": _safe_count(value.get("index"), maximum=48),
        "relation_kind": relation_kind,
        "fiber_depth": _safe_depth(value.get("fiberDepth"), maximum=64),
        "component_name": _safe_name(value.get("componentName")) or "unknown",
        "source_kind": source_kind,
        "nested_depth": _safe_depth(value.get("nestedDepth"), maximum=5),
        "container_kind": container_kind,
        "identity_like_key_names": _safe_name_list(value.get("identityLikeKeyNames"), max_items=24),
        "artifact_like_key_names": _safe_name_list(value.get("artifactLikeKeyNames"), max_items=32),
        "locator_like_key_names": _safe_name_list(value.get("locatorLikeKeyNames"), max_items=24),
        "artifact_context": value.get("artifactContext") is True,
        "artifact_context_locator": value.get("artifactContextLocator") is True,
    }


class ProductArtifactFiberStateV6Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for PR10.1 React fiber/application-state shape reads."""

    def _fiber_state_rpc(
        self,
        flag: str,
        *,
        timeout: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                flag: True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        diagnostic = {
            "request_id_matches": response.get("request_id") == request_id,
            "response_ok": response.get("ok") is True,
        }
        if diagnostic["request_id_matches"] is not True:
            diagnostic["failure_reason"] = "REQUEST_ID_MISMATCH"
        elif diagnostic["response_ok"] is not True:
            diagnostic["failure_reason"] = "WORKER_RETURNED_ERROR"
        else:
            diagnostic["failure_reason"] = None
        return response, diagnostic

    def fiber_state_support(
        self,
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._fiber_state_rpc(
            "characterizeGeneratedArtifactFiberStateV6Support",
            timeout=timeout,
        )
        fields = (
            "generatedArtifactFiberStateV6CharacterizationSupported",
            "generatedArtifactFiberStateV6CharacterizationSchemaVersion",
            "orderedProbePairRequired",
            "assistantTurnAnchorRequired",
            "fiberGraphBounded",
            "artifactRelevantKeysOnly",
            "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "reactStateValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactFiberStateV6CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactFiberStateV6CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "artifact_relevant_keys_only": response.get("artifactRelevantKeysOnly"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def fiber_state_snapshot(
        self,
        *,
        timeout: float = 15.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._fiber_state_rpc(
            "characterizeGeneratedArtifactFiberStateV6",
            timeout=timeout,
        )
        fields = (
            "schema",
            "runtimeTabPresent",
            "runtimeRouteKind",
            "runtimeConversationIdPresent",
            "surfaceReady",
            "selectorKind",
            "visibleTurnCount",
            "userProbeMarkerTurnCount",
            "assistantCompletionMarkerTurnCount",
            "orderedProbeTurnPairPresent",
            "probePlacementProven",
            "placementRoleEvidenceKinds",
            "fiberRootCount",
            "scannedFiberCount",
            "scannedContainerCount",
            "identityKeyHitCount",
            "artifactKeyHitCount",
            "locatorKeyHitCount",
            "artifactContextLocatorHitCount",
            "artifactComponentFiberCount",
            "artifactComponentNames",
            "hitSummaries",
            "fiberGraphBounded",
            "artifactRelevantKeysOnly",
            "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "reactStateValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
            "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        hits: list[dict[str, Any]] = []
        raw_hits = response.get("hitSummaries")
        if isinstance(raw_hits, list):
            for item in raw_hits[:48]:
                hit = _safe_hit(item)
                if hit is not None:
                    hits.append(hit)

        route_kind = response.get("runtimeRouteKind")
        if route_kind not in {
            "absent", "root", "conversation", "chatgpt_other", "not_chatgpt", "invalid"
        }:
            route_kind = "invalid"
        selector_kind = response.get("selectorKind")
        if selector_kind not in {"none", "conversation_testid", "article_fallback"}:
            selector_kind = "none"

        snapshot = {
            "schema": response.get("schema"),
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "runtime_route_kind": route_kind,
            "runtime_conversation_id_present": response.get("runtimeConversationIdPresent") is True,
            "surface_ready": response.get("surfaceReady") is True,
            "selector_kind": selector_kind,
            "visible_turn_count": _safe_count(response.get("visibleTurnCount"), maximum=64),
            "user_probe_marker_turn_count": _safe_count(response.get("userProbeMarkerTurnCount"), maximum=64),
            "assistant_completion_marker_turn_count": _safe_count(
                response.get("assistantCompletionMarkerTurnCount"), maximum=64
            ),
            "ordered_probe_turn_pair_present": response.get("orderedProbeTurnPairPresent") is True,
            "probe_placement_proven": response.get("probePlacementProven") is True,
            "placement_role_evidence_kinds": _safe_name_list(
                response.get("placementRoleEvidenceKinds"), max_items=8
            ),
            "fiber_root_count": _safe_count(response.get("fiberRootCount"), maximum=4),
            "scanned_fiber_count": _safe_count(response.get("scannedFiberCount"), maximum=4096),
            "scanned_container_count": _safe_count(response.get("scannedContainerCount"), maximum=200000),
            "identity_key_hit_count": _safe_count(response.get("identityKeyHitCount"), maximum=4096),
            "artifact_key_hit_count": _safe_count(response.get("artifactKeyHitCount"), maximum=4096),
            "locator_key_hit_count": _safe_count(response.get("locatorKeyHitCount"), maximum=4096),
            "artifact_context_locator_hit_count": _safe_count(
                response.get("artifactContextLocatorHitCount"), maximum=4096
            ),
            "artifact_component_fiber_count": _safe_count(
                response.get("artifactComponentFiberCount"), maximum=4096
            ),
            "artifact_component_names": _safe_name_list(response.get("artifactComponentNames"), max_items=32),
            "hit_summaries": hits,
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "artifact_relevant_keys_only": response.get("artifactRelevantKeysOnly"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == FIBER_STATE_SCHEMA
            and snapshot["fiber_graph_bounded"] is True
            and snapshot["artifact_relevant_keys_only"] is True
            and snapshot["accessor_properties_skipped"] is True
            and snapshot["dom_state_node_values_excluded"] is True
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["react_prop_values_exported"] is False
            and snapshot["react_state_values_exported"] is False
            and snapshot["locator_values_exported"] is False
            and snapshot["click_performed"] is False
            and snapshot["download_attempted"] is False
            and snapshot["write_performed"] is False
            and snapshot["debugger_attached_after"] in {False, None}
        )
        diagnostic["snapshot_contract_ok"] = contract_ok
        if not contract_ok:
            diagnostic["failure_reason"] = "SNAPSHOT_CONTRACT_MISMATCH"
        return snapshot, diagnostic


def run_gate(
    *,
    expected_head: str | None,
    timeout: float,
    preflight_only: bool = False,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_FIBER_STATE_V6_LIVE_GATE_V1",
        "fiber_state_schema": FIBER_STATE_SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "surface_read_budget": 0 if preflight_only else SURFACE_READ_BUDGET,
        "download_budget": DOWNLOAD_BUDGET,
        "local_write_budget": LOCAL_WRITE_BUDGET,
        "preflight_only": preflight_only,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "support_probe_attempted": False,
        "support_probe_proven": False,
        "surface_read_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_dom_exported": False,
        "raw_text_exported": False,
        "attribute_values_exported": False,
        "react_prop_values_exported": False,
        "react_state_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactFiberStateV6Provider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.fiber_state_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_FIBER_STATE_V6_SUPPORT_RPC_FAILED"
        return report
    report["fiber_state_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SUPPORT:
        report["preflight_error"] = "ARTIFACT_FIBER_STATE_V6_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_FIBER_STATE_V6_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.fiber_state_snapshot(timeout=min(timeout, 25.0))
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["fiber_state_snapshot"] = snapshot
    report["fiber_state_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        report["characterization"] = "ARTIFACT_FIBER_STATE_V6_SNAPSHOT_CONTRACT_NOT_PROVEN"
        return report

    placement_proven = bool(
        snapshot["runtime_tab_present"]
        and snapshot["surface_ready"]
        and snapshot["ordered_probe_turn_pair_present"]
        and snapshot["probe_placement_proven"]
        and snapshot["user_probe_marker_turn_count"] >= 1
        and snapshot["assistant_completion_marker_turn_count"] >= 1
    )
    fiber_root_observed = bool(placement_proven and snapshot["fiber_root_count"] >= 1)
    identity_signal = bool(fiber_root_observed and snapshot["identity_key_hit_count"] >= 1)
    artifact_signal = bool(
        fiber_root_observed
        and (
            snapshot["artifact_key_hit_count"] >= 1
            or snapshot["artifact_component_fiber_count"] >= 1
        )
    )
    artifact_context_locator_signal = bool(
        fiber_root_observed and snapshot["artifact_context_locator_hit_count"] >= 1
    )
    locator_signal = bool(fiber_root_observed and snapshot["locator_key_hit_count"] >= 1)

    report["experiment_valid"] = placement_proven
    report["fiber_root_observed"] = fiber_root_observed
    report["identity_key_names_observed"] = identity_signal
    report["artifact_structure_observed"] = artifact_signal
    report["artifact_context_locator_key_names_observed"] = artifact_context_locator_signal
    report["locator_key_names_observed"] = locator_signal

    if not placement_proven:
        report["characterization"] = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif not fiber_root_observed:
        report["characterization"] = "PROBE_TURN_PROVEN_NO_REACT_FIBER_ROOT_OBSERVED"
    elif identity_signal:
        report["characterization"] = "PROBE_ANCHORED_REACT_STATE_IDENTITY_KEY_NAMES_OBSERVED"
    elif artifact_context_locator_signal:
        report["characterization"] = "PROBE_ANCHORED_REACT_STATE_ARTIFACT_CONTEXT_LOCATOR_KEY_NAMES_OBSERVED"
    elif artifact_signal:
        report["characterization"] = "PROBE_ANCHORED_REACT_STATE_ARTIFACT_STRUCTURE_OBSERVED"
    elif locator_signal:
        report["characterization"] = "PROBE_ANCHORED_REACT_STATE_LOCATOR_KEY_NAMES_ONLY_OBSERVED"
    else:
        report["characterization"] = "PROBE_ANCHORED_REACT_STATE_NO_ARTIFACT_RELEVANT_KEY_NAMES_OBSERVED"

    report["ok"] = placement_proven
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PR10.1 bounded no-write React fiber/application-state characterization."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_read:
        parser.error(
            "--acknowledge-live-read is required unless --preflight-only is used; "
            "the gate performs one bounded read-only React state shape snapshot, zero product writes, "
            "zero clicks, and zero downloads"
        )

    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
