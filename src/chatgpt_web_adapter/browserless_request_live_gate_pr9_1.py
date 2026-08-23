from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .browserless_request_transport import (
    BrowserlessChallengeBoundaryError,
    BrowserlessProtocolDriftError,
    BrowserlessRequestTransportError,
)
from .product_contract import product_runtime_contract
from .product_runtime import assemble_product_runtime

SCHEMA = 1
DEFAULT_PROMPT = "Reply with exactly: CWA_PR9_1_BROWSERLESS_OK"
DEFAULT_EXPECTED = "CWA_PR9_1_BROWSERLESS_OK"


def run_live_gate(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    prompt: str = DEFAULT_PROMPT,
    expected: str = DEFAULT_EXPECTED,
    timeout: float = 150.0,
) -> dict[str, Any]:
    """Run one bounded browserless live attempt with no browser fallback.

    A protected challenge is a successful safety-boundary observation, not proof
    that direct write is available. Ambiguous outcomes remain reconciliation
    required and are never retried.
    """

    runtime = assemble_product_runtime(
        transport="browserless-request",
        auth_file=auth_file,
    )
    capabilities = runtime.capabilities().to_dict()
    contract = product_runtime_contract(runtime).to_dict()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "pr": "PR9.1",
        "transport": runtime.transport,
        "support_tier": capabilities.get("transport_support_tier"),
        "product_write_budget": 1,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "challenge_bypass_attempted": False,
        "capabilities": capabilities,
        "contract": contract,
        "outcome": None,
        "ok": False,
    }

    report["write_attempts"] = 1
    try:
        execution = runtime.send_text_observed(
            prompt,
            timeout=timeout,
            conversation_mode="normal",
        )
    except BrowserlessChallengeBoundaryError as error:
        report["outcome"] = "CHALLENGE_BOUNDARY"
        report["boundary"] = error.to_dict()
        report["ok"] = True
        return report
    except BrowserlessProtocolDriftError as error:
        report["outcome"] = "PROTOCOL_DRIFT"
        report["error"] = error.to_dict()
        return report
    except BrowserlessRequestTransportError as error:
        report["outcome"] = (
            "RECONCILIATION_REQUIRED"
            if error.reconciliation_required
            else "DIRECT_REQUEST_FAILED"
        )
        report["error"] = error.to_dict()
        return report

    report["write_completions"] = 1
    actual = execution.response.text.strip()
    report["response_matches"] = actual == expected
    report["conversation_id_present"] = bool(
        execution.response.conversation.conversation_id
    )
    report["message_id_present"] = bool(execution.response.conversation.message_id)
    report["observation"] = execution.observation.to_dict()
    report["provenance"] = (
        execution.provenance.to_dict() if execution.provenance is not None else None
    )
    report["outcome"] = "DIRECT_WRITE_COMPLETED"
    report["ok"] = bool(
        actual == expected
        and report["conversation_id_present"]
        and report["message_id_present"]
        and execution.provenance is not None
        and execution.provenance.completion.canonical_completion_proven
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.1 bounded experimental browserless request live gate"
    )
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--expected", default=DEFAULT_EXPECTED)
    parser.add_argument("--acknowledge-live-write", action="store_true")
    args = parser.parse_args()

    if not args.acknowledge_live_write:
        parser.error(
            "--acknowledge-live-write is required; this gate may perform exactly one product write"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    report = run_live_gate(
        auth_file=args.auth_file,
        prompt=args.prompt,
        expected=args.expected,
        timeout=args.timeout,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
