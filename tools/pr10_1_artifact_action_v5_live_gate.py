from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


ACTION_SCHEMA = 5
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": ACTION_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "pre_code_svg_excluded": True,
    "host_action_only": True,
    "structural_key_names_only": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "attribute_values_exported": False,
    "react_prop_values_exported": False,
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


def _safe_name_list(value: Any, *, max_items: int = 192) -> list[str]:
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


def _safe_nullable_depth(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 16 else None


def _safe_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    interactive_kind = value.get("interactiveKind")
    if interactive_kind not in {"none", "a", "button", "role_button", "role_link"}:
        interactive_kind = "none"
    return {
        "index": _safe_count(value.get("index"), maximum=32),
        "tag_name": _safe_name(value.get("tagName")) or "unknown",
        "depth_to_turn": _safe_nullable_depth(value.get("depthToTurn")),
        "interactive_kind": interactive_kind,
        "href_attribute_present": value.get("hrefAttributePresent") is True,
        "download_attribute_present": value.get("downloadAttributePresent") is True,
        "host_attribute_names": _safe_name_list(value.get("hostAttributeNames"), max_items=64),
        "bounded_attribute_names": _safe_name_list(value.get("boundedAttributeNames"), max_items=128),
        "react_fiber_property_present": value.get("reactFiberPropertyPresent") is True,
        "react_props_property_present": value.get("reactPropsPropertyPresent") is True,
        "host_react_prop_names": _safe_name_list(value.get("hostReactPropNames"), max_items=160),
        "bounded_react_prop_names": _safe_name_list(value.get("boundedReactPropNames"), max_items=192),
        "identity_like_react_prop_names": _safe_name_list(
            value.get("identityLikeReactPropNames"), max_items=32
        ),
        "locator_like_react_prop_names": _safe_name_list(
            value.get("locatorLikeReactPropNames"), max_items=32
        ),
        "artifact_like_react_prop_names": _safe_name_list(
            value.get("artifactLikeReactPropNames"), max_items=64
        ),
        "bounded_react_component_names": _safe_name_list(
            value.get("boundedReactComponentNames"), max_items=96
        ),
        "artifact_like_react_component_names": _safe_name_list(
            value.get("artifactLikeReactComponentNames"), max_items=64
        ),
        "artifact_like_attribute_names": _safe_name_list(
            value.get("artifactLikeAttributeNames"), max_items=64
        ),
        "identity_signal": value.get("identitySignal") is True,
        "artifact_signal": value.get("artifactSignal") is True,
        "locator_signal": value.get("locatorSignal") is True,
    }


class ProductArtifactActionV5Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for PR10.1 HTML action-host topology reads."""

    def _action_rpc(self, flag: str, *, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
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

    def action_support(self, *, timeout: float = 5.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._action_rpc(
            "characterizeGeneratedArtifactActionV5Support", timeout=timeout
        )
        fields = (
            "generatedArtifactActionV5CharacterizationSupported",
            "generatedArtifactActionV5CharacterizationSchemaVersion",
            "orderedProbePairRequired",
            "assistantTurnAnchorRequired",
            "preCodeSvgExcluded",
            "hostActionOnly",
            "structuralKeyNamesOnly",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactActionV5CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactActionV5CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "pre_code_svg_excluded": response.get("preCodeSvgExcluded"),
            "host_action_only": response.get("hostActionOnly"),
            "structural_key_names_only": response.get("structuralKeyNamesOnly"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def action_snapshot(self, *, timeout: float = 10.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._action_rpc("characterizeGeneratedArtifactActionV5", timeout=timeout)
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
            "actionHostCount",
            "hrefActionHostCount",
            "downloadActionHostCount",
            "identitySignalActionCount",
            "artifactSignalActionCount",
            "locatorSignalActionCount",
            "candidateSummaries",
            "preCodeSvgExcluded",
            "hostActionOnly",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
            "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        candidates: list[dict[str, Any]] = []
        raw_candidates = response.get("candidateSummaries")
        if isinstance(raw_candidates, list):
            for item in raw_candidates[:32]:
                candidate = _safe_candidate(item)
                if candidate is not None:
                    candidates.append(candidate)

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
            "action_host_count": _safe_count(response.get("actionHostCount"), maximum=64),
            "href_action_host_count": _safe_count(response.get("hrefActionHostCount"), maximum=64),
            "download_action_host_count": _safe_count(response.get("downloadActionHostCount"), maximum=64),
            "identity_signal_action_count": _safe_count(
                response.get("identitySignalActionCount"), maximum=64
            ),
            "artifact_signal_action_count": _safe_count(
                response.get("artifactSignalActionCount"), maximum=64
            ),
            "locator_signal_action_count": _safe_count(
                response.get("locatorSignalActionCount"), maximum=64
            ),
            "candidate_summaries": candidates,
            "pre_code_svg_excluded": response.get("preCodeSvgExcluded"),
            "host_action_only": response.get("hostActionOnly"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == ACTION_SCHEMA
            and snapshot["pre_code_svg_excluded"] is True
            and snapshot["host_action_only"] is True
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["react_prop_values_exported"] is False
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


def run_gate(*, expected_head: str | None, timeout: float, preflight_only: bool = False) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_ACTION_V5_LIVE_GATE_V1",
        "action_schema": ACTION_SCHEMA,
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
        "locator_values_exported": False,
        "click_performed": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactActionV5Provider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.action_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_ACTION_V5_SUPPORT_RPC_FAILED"
        return report
    report["action_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SUPPORT:
        report["preflight_error"] = "ARTIFACT_ACTION_V5_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_ACTION_V5_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.action_snapshot(timeout=min(timeout, 20.0))
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["action_snapshot"] = snapshot
    report["action_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        report["characterization"] = "ARTIFACT_ACTION_V5_SNAPSHOT_CONTRACT_NOT_PROVEN"
        return report

    placement_proven = bool(
        snapshot["runtime_tab_present"]
        and snapshot["surface_ready"]
        and snapshot["ordered_probe_turn_pair_present"]
        and snapshot["probe_placement_proven"]
        and snapshot["user_probe_marker_turn_count"] >= 1
        and snapshot["assistant_completion_marker_turn_count"] >= 1
    )
    candidates = snapshot["candidate_summaries"]
    identity_observed = bool(snapshot["identity_signal_action_count"] >= 1) or any(
        item["identity_signal"] for item in candidates
    )
    artifact_observed = bool(snapshot["artifact_signal_action_count"] >= 1) or any(
        item["artifact_signal"] for item in candidates
    )
    locator_observed = bool(snapshot["locator_signal_action_count"] >= 1) or any(
        item["locator_signal"] for item in candidates
    )
    action_hosts_observed = bool(placement_proven and snapshot["action_host_count"] >= 1)

    report["experiment_valid"] = placement_proven
    report["action_hosts_observed"] = action_hosts_observed
    report["identity_signal_observed"] = identity_observed
    report["artifact_signal_observed"] = artifact_observed
    report["locator_signal_observed"] = locator_observed

    if not placement_proven:
        report["characterization"] = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif not action_hosts_observed:
        report["characterization"] = "PROBE_TURN_PROVEN_NO_HTML_ACTION_HOSTS_OBSERVED"
    elif identity_observed:
        report["characterization"] = "PROBE_ANCHORED_HTML_ACTION_IDENTITY_KEY_NAMES_OBSERVED"
    elif artifact_observed:
        report["characterization"] = "PROBE_ANCHORED_HTML_ACTION_ARTIFACT_STRUCTURE_OBSERVED"
    elif locator_observed:
        report["characterization"] = "PROBE_ANCHORED_HTML_ACTION_LOCATOR_ONLY_STRUCTURE_OBSERVED"
    else:
        report["characterization"] = "PROBE_ANCHORED_HTML_ACTION_GENERIC_ONLY"

    report["ok"] = placement_proven
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PR10.1 bounded no-write HTML action-host artifact topology characterization."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_read:
        parser.error(
            "--acknowledge-live-read is required unless --preflight-only is used; "
            "the gate performs one read-only HTML action-host snapshot, zero product writes, "
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
