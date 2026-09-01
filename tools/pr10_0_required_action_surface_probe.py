from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any
import uuid

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    PRODUCT_REQUIRED_ACTION_SURFACE_OBSERVED,
    ProductConnectorLifecycleCollector,
)
from chatgpt_web_adapter.product_model_profile_pr8_10 import ProductModelProfileProvider


SCHEMA = "CWA_PR10_0_REQUIRED_ACTION_SURFACE_PROBE_V3"
_ALLOWED_IDENTITY_ATTRIBUTE_NAMES = frozenset(
    {
        "data-action-id",
        "data-required-action-id",
        "data-connector-action-id",
        "data-connect-action-id",
        "data-connector-id",
        "data-app-id",
        "data-plugin-id",
        "data-testid",
    }
)
_ALLOWED_ACTION_ID_CANDIDATE_FIELDS = frozenset(
    {
        "data-action-id",
        "data-required-action-id",
        "data-connector-action-id",
        "data-connect-action-id",
    }
)


class RequiredActionSurfaceProvider(ProductModelProfileProvider):
    def characterize_required_action_surface(
        self,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "characterizeRequiredActionSurface": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if response.get("request_id") != request_id:
            raise RuntimeError("PR10_0_REQUIRED_ACTION_SURFACE_REQUEST_ID_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError("PR10_0_REQUIRED_ACTION_SURFACE_WORKER_ERROR")
        return response


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _surface_observation_event(surface: dict[str, Any]) -> dict[str, Any] | None:
    connector_name = surface.get("connector_name")
    action_type = surface.get("action_type")
    if not isinstance(connector_name, str) or not isinstance(action_type, str):
        return None
    return {
        "type": PRODUCT_REQUIRED_ACTION_SURFACE_OBSERVED,
        "observation_id": f"required-action-surface:{connector_name}:{action_type}",
        "connector_name": connector_name,
        "action_type": action_type,
        "connect_control_present": surface.get("connect_control_present") is True,
        "dismiss_control_present": surface.get("dismiss_control_present") is True,
        "stable_action_id_present": surface.get("stable_action_id_present") is True,
    }


def _identity_attribute_names(response: dict[str, Any]) -> list[str]:
    raw = response.get("identityAttributeNames")
    if not isinstance(raw, list):
        return []
    names = {
        value
        for value in raw
        if isinstance(value, str) and value in _ALLOWED_IDENTITY_ATTRIBUTE_NAMES
    }
    return sorted(names)


def _stable_action_id_candidate_field(response: dict[str, Any]) -> str | None:
    value = response.get("stableActionIdCandidateField")
    if isinstance(value, str) and value in _ALLOWED_ACTION_ID_CANDIDATE_FIELDS:
        return value
    return None


def run_probe(*, expected_head: str, timeout: float) -> dict[str, Any]:
    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = head == expected_head
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "expected_head": expected_head,
        "head": head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "product_write_budget": 0,
        "write_attempted": False,
        "click_attempted": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    try:
        response = RequiredActionSurfaceProvider().characterize_required_action_surface(
            timeout=timeout
        )
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["preflight_error"] = "REQUIRED_ACTION_SURFACE_RPC_FAILED"
        return report

    identity_attribute_names = _identity_attribute_names(response)
    stable_action_id_candidate_field = _stable_action_id_candidate_field(response)
    surface = {
        "surface_observed": response.get("surfaceObserved") is True,
        "connector_name": response.get("connectorName")
        if isinstance(response.get("connectorName"), str)
        else None,
        "action_type": response.get("actionType")
        if isinstance(response.get("actionType"), str)
        else None,
        "connect_control_present": response.get("connectControlPresent") is True,
        "dismiss_control_present": response.get("dismissControlPresent") is True,
        # Candidate field presence is deliberately weaker than a proven stable id.
        "stable_action_id_present": response.get("stableActionIdPresent") is True,
        "identity_attribute_names": identity_attribute_names,
        "stable_action_id_candidate_field": stable_action_id_candidate_field,
        "raw_dom_exported": response.get("rawDomExported") is True,
        "raw_identity_attribute_values_exported": (
            response.get("rawIdentityAttributeValuesExported") is True
        ),
        "click_performed": response.get("clickPerformed") is True,
        "write_performed": response.get("writePerformed") is True,
        "approval_authority_granted": response.get("approvalAuthorityGranted") is True,
        "runtime_tab_present": response.get("runtimeTabPresent") is True,
        "debugger_attached_after": response.get("debuggerAttachedAfter"),
    }
    safety_ok = bool(
        surface["raw_dom_exported"] is False
        and surface["raw_identity_attribute_values_exported"] is False
        and surface["click_performed"] is False
        and surface["write_performed"] is False
        and surface["approval_authority_granted"] is False
        and surface["debugger_attached_after"] is False
    )
    observed = bool(
        surface["surface_observed"]
        and surface["connector_name"]
        and surface["action_type"] == "connector_authorization_required"
        and surface["connect_control_present"]
        and surface["dismiss_control_present"]
    )

    typed_observation = None
    observation_drop_count = 0
    if observed:
        event = _surface_observation_event(surface)
        if event is not None:
            collector = ProductConnectorLifecycleCollector()
            observation = collector.consume(event)
            observation_drop_count = collector.dropped_event_count
            if observation is not None:
                typed_observation = observation.to_dict()

    point_observation_materialized = bool(
        typed_observation is not None
        and typed_observation.get("kind") == "REQUIRED_ACTION"
        and typed_observation.get("phase") == "OBSERVED"
        and "action_id" not in typed_observation
        and observation_drop_count == 0
    )
    action_id_value_observed = False
    lifecycle_correlation_claimed = False

    report.update(
        {
            "surface": surface,
            "typed_observation": typed_observation,
            "point_observation_materialized": point_observation_materialized,
            "observation_drop_count": observation_drop_count,
            "identity_attribute_name_count": len(identity_attribute_names),
            "stable_action_id_candidate_field_present": (
                stable_action_id_candidate_field is not None
            ),
            "action_id_value_observed": action_id_value_observed,
            "lifecycle_correlation_claimed": lifecycle_correlation_claimed,
            "safety_ok": safety_ok,
            "characterization": (
                "REQUIRED_ACTION_SURFACE_OBSERVED"
                if observed
                else "NO_REQUIRED_ACTION_SURFACE_OBSERVED"
            ),
            "ok": safety_ok and observed and point_observation_materialized,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only PR10.0 required-action/connector authorization surface probe."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    report = run_probe(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
