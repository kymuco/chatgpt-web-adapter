from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any
import uuid

from chatgpt_web_adapter.product_model_profile_pr8_10 import ProductModelProfileProvider


SCHEMA = "CWA_PR10_0_REQUIRED_ACTION_SURFACE_PROBE_V1"


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
        "stable_action_id_present": response.get("stableActionIdPresent") is True,
        "raw_dom_exported": response.get("rawDomExported") is True,
        "click_performed": response.get("clickPerformed") is True,
        "write_performed": response.get("writePerformed") is True,
        "approval_authority_granted": response.get("approvalAuthorityGranted") is True,
        "runtime_tab_present": response.get("runtimeTabPresent") is True,
        "debugger_attached_after": response.get("debuggerAttachedAfter"),
    }
    safety_ok = bool(
        surface["raw_dom_exported"] is False
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
    report.update(
        {
            "surface": surface,
            "safety_ok": safety_ok,
            "characterization": (
                "REQUIRED_ACTION_SURFACE_OBSERVED"
                if observed
                else "NO_REQUIRED_ACTION_SURFACE_OBSERVED"
            ),
            "ok": safety_ok and observed,
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
