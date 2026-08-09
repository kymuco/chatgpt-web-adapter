from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter import (
    ChatGPTWebClient,
    probe_sentinel_requirements_prepare,
    sentinel_requirements as sentinel_contract,
)

SCHEMA = "chatgpt-web-adapter.sentinel-requirements-contract-probe.v1"


def build_report(result) -> dict:
    return {
        "schema": SCHEMA,
        "probe": {
            "sentinel_prepare_attempted": True,
            "sentinel_finalize_attempted": False,
            "conversation_write_attempted": False,
            "raw_request_recorded": False,
            "raw_response_recorded": False,
            "prepare_token_recorded": False,
            "challenge_values_recorded": False,
            "final_requirements_token_recorded": False,
        },
        "sentinel_prepare": {
            "status_code": result.status_code,
            "status_ok": result.status_ok,
            "observed_shape_matches": result.observed_shape_matches,
            "persona_present": result.persona_present,
            "prepare_token_present": result.prepare_token_present,
            "response_keys": list(result.response_keys),
            "turnstile": {
                "present": result.turnstile_present,
                "required": result.turnstile_required,
                "keys": list(result.turnstile_keys),
            },
            "proofofwork": {
                "present": result.proofofwork_present,
                "required": result.proofofwork_required,
                "keys": list(result.proofofwork_keys),
            },
            "so": {
                "present": result.so_present,
                "required": result.so_required,
                "keys": list(result.so_keys),
            },
        },
        "browser_observed_finalize_contract": {
            "request_keys": list(sentinel_contract.OBSERVED_FINALIZE_REQUEST_KEYS),
            "response_keys": list(sentinel_contract.OBSERVED_FINALIZE_RESPONSE_KEYS),
            "network_invocation_attempted_by_probe": False,
        },
        "governance": {
            "challenge_solver_present": False,
            "challenge_replay_attempted": False,
            "legacy_single_step_current_write_live_validated": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Probe the current two-phase Sentinel chat-requirements prepare "
            "contract without finalizing challenges or sending a conversation turn."
        )
    )
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--output",
        default="sentinel_requirements_contract_probe.json",
    )
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    result = probe_sentinel_requirements_prepare(client)
    report = build_report(result)
    report["verdict"] = result.verdict

    output = Path(args.output)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"report: {output}")


if __name__ == "__main__":
    main()
