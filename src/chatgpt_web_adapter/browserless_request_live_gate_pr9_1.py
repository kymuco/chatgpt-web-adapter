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


def _base_report() -> dict[str, Any]:
    """Return the zero-write report envelope before runtime assembly begins."""

    return {
        "schema": SCHEMA,
        "pr": "PR9.1",
        "transport": "browserless-request",
        "support_tier": None,
        "product_write_budget": 1,
        "product_turn_invocations": 0,
        "conversation_write_attempts": 0,
        "conversation_write_completions": 0,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "challenge_bypass_attempted": False,
        "capabilities": None,
        "contract": None,
        "outcome": None,
        "ok": False,
    }


def _runtime_assembly_error(error: Exception) -> dict[str, Any]:
    """Serialize a proven-prewrite runtime assembly failure."""

    return {
        "error": type(error).__name__,
        "message": str(error),
        "request_stage": "runtime_assembly",
        "status_code": None,
        "endpoint": None,
        "write_may_have_been_submitted": False,
        "reconciliation_required": False,
    }


def run_live_gate(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    prompt: str = DEFAULT_PROMPT,
    expected: str = DEFAULT_EXPECTED,
    timeout: float = 150.0,
) -> dict[str, Any]:
    """Run one bounded browserless live invocation with no browser fallback.

    A protected challenge is a successful safety-boundary observation, not proof
    that direct write is available. Ambiguous outcomes remain reconciliation
    required and are never retried.

    ``product_turn_invocations`` counts calls into the transport. Conversation
    write counters describe only the mutation plane; a challenge/protocol boundary
    reached before that plane therefore records zero conversation write attempts.

    Runtime assembly and contract/capability materialization are also part of the
    proven-prewrite gate boundary. Operational failures there are returned as a
    structured zero-write ``DIRECT_REQUEST_FAILED`` result rather than escaping as
    a CLI traceback.
    """

    report = _base_report()
    try:
        runtime = assemble_product_runtime(
            transport="browserless-request",
            auth_file=auth_file,
        )
        capabilities = runtime.capabilities().to_dict()
        contract = product_runtime_contract(runtime).to_dict()
    except Exception as error:
        report["outcome"] = "DIRECT_REQUEST_FAILED"
        report["error"] = _runtime_assembly_error(error)
        return report

    report["transport"] = runtime.transport
    report["support_tier"] = capabilities.get("transport_support_tier")
    report["capabilities"] = capabilities
    report["contract"] = contract
    report["product_turn_invocations"] = 1
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
        if error.write_may_have_been_submitted:
            report["conversation_write_attempts"] = 1
        report["outcome"] = (
            "RECONCILIATION_REQUIRED"
            if error.reconciliation_required
            else "DIRECT_REQUEST_FAILED"
        )
        report["error"] = error.to_dict()
        return report

    report["conversation_write_attempts"] = 1
    report["conversation_write_completions"] = 1
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
            "--acknowledge-live-write is required; this gate may perform at most one conversation write"
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
