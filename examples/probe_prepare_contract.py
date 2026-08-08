from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter import (
    ChatGPTWebClient,
    DEFAULT_MODEL,
    prepare_text_turn,
)

SCHEMA = "chatgpt-web-adapter.prepare-contract-probe.v1"
DEFAULT_PROMPT = "Reply exactly: prepare-probe-ok"


def build_report(result, payload: dict) -> dict:
    partial_query = payload.get("partial_query")
    return {
        "schema": SCHEMA,
        "probe": {
            "write_attempted": False,
            "prepare_attempted": True,
            "prompt_text_recorded": False,
            "raw_response_recorded": False,
            "conduit_token_recorded": False,
        },
        "prepare": {
            "status_code": result.status_code,
            "status_ok": result.status_ok,
            "conduit_token_present": result.conduit_token_present,
            "response_keys": list(result.response_keys),
            "partial_query_present": isinstance(partial_query, dict),
            "partial_query_text_recorded": False,
            "client_prepare_state": payload.get("client_prepare_state"),
            "x_conduit_initial_mode": "no-token",
            "conversation_id_present": bool(payload.get("conversation_id")),
            "thinking_effort_present": bool(payload.get("thinking_effort")),
        },
    }


def verdict(report: dict) -> str:
    prepare = report["prepare"]
    if prepare["status_ok"] and prepare["conduit_token_present"]:
        return "PREPARE_CONTRACT_OBSERVED"
    if prepare["status_ok"]:
        return "PREPARE_OK_NO_CONDUIT"
    return "PREPARE_REJECTED"


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the ordinary ChatGPT text prepare/conduit contract without sending the turn.")
    parser.add_argument("conversation", help="Existing ChatGPT conversation URL or raw id.")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", default="prepare_contract_probe.json")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    attached = client.attach_conversation(args.conversation)
    model = attached.detected_model or DEFAULT_MODEL
    reasoning = attached.detected_reasoning_effort
    result, payload = prepare_text_turn(
        client,
        args.prompt,
        model=model,
        conversation=attached.conversation,
        reasoning_effort=reasoning,
    )
    report = build_report(result, payload)
    report["verdict"] = verdict(report)
    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"report: {output}")


if __name__ == "__main__":
    main()
