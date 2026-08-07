from __future__ import annotations

"""Capture a privacy-safe ChatGPT web model/transport contract probe.

This example is intentionally evidence-only. It does not change model defaults or
reasoning aliases. Run it against an existing ChatGPT conversation whose model
and reasoning mode were selected in the web UI.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from chatgpt_web_adapter import ChatGPTWebClient


PROBE_SCHEMA = "chatgpt-web-adapter.live-contract-probe.v1"
DEFAULT_PROMPT = "Reply exactly: probe-ok"
SAFE_SCALAR = re.compile(r"^[A-Za-z0-9._:/+-]{1,96}$")
MODEL_KEYS = {"model", "model_slug", "default_model_slug", "selected_model"}
REASONING_KEYS = {"thinking_effort", "reasoning_effort"}
IDENTIFIER_KEYS = {
    "conversation_id",
    "message_id",
    "parent_message_id",
    "turn_exchange_id",
    "resume_turn_topic_id",
    "resume_sse_topic_id",
    "resume_ws_topic_id",
    "resume_conduit_uuid",
}
SECRET_OR_CONTENT_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "cookies",
    "prompt",
    "raw",
    "response_text",
    "resume_token",
    "text",
    "token",
    "websocket_url",
}


def _safe_contract_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or not SAFE_SCALAR.fullmatch(value):
        return None
    return value


def _walk_contract_fields(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    """Collect only model/reasoning scalar evidence and structural paths.

    No generic scalar values are retained. This keeps prompts, assistant output,
    ids, tokens, URLs, connector payloads, and other account data out of the
    generated report by construction.
    """

    evidence: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            child_path = f"{path}.{key_text}"
            if key_lower in SECRET_OR_CONTENT_KEYS or key_lower in IDENTIFIER_KEYS:
                continue
            if key_lower in MODEL_KEYS | REASONING_KEYS:
                candidate = _safe_contract_value(nested)
                if candidate is not None:
                    evidence.append(
                        {
                            "path": child_path,
                            "kind": "model" if key_lower in MODEL_KEYS else "reasoning",
                            "value": candidate,
                        }
                    )
                continue
            if isinstance(nested, (dict, list)):
                evidence.extend(_walk_contract_fields(nested, path=child_path))
    elif isinstance(value, list):
        for nested in value:
            if isinstance(nested, (dict, list)):
                evidence.extend(_walk_contract_fields(nested, path=f"{path}[]"))
    return evidence


def _presence(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _request_contract(request: Any) -> dict[str, Any]:
    payload = request.to_dict() if hasattr(request, "to_dict") else dict(request or {})
    return {
        "requested_model": payload.get("requested_model"),
        "requested_reasoning_effort": payload.get("requested_reasoning_effort"),
        "sent_model": payload.get("sent_model"),
        "sent_reasoning_effort": payload.get("sent_reasoning_effort"),
        "observed_model": payload.get("observed_model"),
        "observed_reasoning_effort": payload.get("observed_reasoning_effort"),
        "is_continuation": bool(payload.get("is_continuation")),
        "resume_kind": payload.get("resume_kind"),
        "resume_token_present": bool(payload.get("resume_token_present")),
        "handoff_option_types": list(payload.get("handoff_option_types") or ()),
        "resume_transport_preference": payload.get("resume_transport_preference"),
        "handoff_recovery_mode": payload.get("handoff_recovery_mode"),
        "resume_with_websockets": bool(payload.get("resume_with_websockets")),
        "resume_ws_url_present": bool(payload.get("resume_ws_url_present")),
        "resume_ws_url_scheme": payload.get("resume_ws_url_scheme"),
        "resume_ws_url_host": payload.get("resume_ws_url_host"),
        "conversation_id_present": _presence(payload.get("conversation_id")),
        "parent_message_id_present": _presence(payload.get("parent_message_id")),
        "turn_exchange_id_present": _presence(payload.get("turn_exchange_id")),
        "resume_turn_topic_id_present": _presence(payload.get("resume_turn_topic_id")),
        "resume_sse_topic_id_present": _presence(payload.get("resume_sse_topic_id")),
        "resume_ws_topic_id_present": _presence(payload.get("resume_ws_topic_id")),
        "resume_conduit_uuid_present": _presence(payload.get("resume_conduit_uuid")),
    }


def _transport_summary(event_types: list[str], request_contract: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(event_types)
    return {
        "event_counts": dict(sorted(counts.items())),
        "saw_raw_sse_event": counts["raw_sse_event"] > 0,
        "saw_raw_ws_event": counts["raw_ws_event"] > 0,
        "saw_ws_connected": counts["stream_handoff_ws_connected"] > 0,
        "saw_ws_subscribed": counts["stream_handoff_ws_subscribed"] > 0,
        "saw_ws_failure": counts["stream_handoff_ws_failed"] > 0,
        "saw_polling": any(name.startswith("conversation_poll_") for name in counts),
        "handoff_recovery_mode": request_contract.get("handoff_recovery_mode"),
        "resume_transport_preference": request_contract.get("resume_transport_preference"),
    }


def _verdict(
    *,
    attached_model: str | None,
    attached_reasoning: str | None,
    request_contract: dict[str, Any],
    field_evidence: list[dict[str, str]],
) -> str:
    observed_model = request_contract.get("observed_model")
    sent_model = request_contract.get("sent_model")
    observed_reasoning = request_contract.get("observed_reasoning_effort")
    sent_reasoning = request_contract.get("sent_reasoning_effort")

    if not attached_model and not observed_model and not any(item["kind"] == "model" for item in field_evidence):
        return "MODEL_CONTRACT_UNOBSERVED"
    if attached_model and sent_model and attached_model != sent_model:
        return "PRESERVE_MODEL_MISMATCH"
    if observed_model and sent_model and observed_model != sent_model:
        return "OBSERVED_MODEL_DIFFERS_FROM_SENT"
    if attached_reasoning and sent_reasoning and attached_reasoning != sent_reasoning:
        return "PRESERVE_REASONING_MISMATCH"
    if observed_reasoning and sent_reasoning and observed_reasoning != sent_reasoning:
        return "OBSERVED_REASONING_DIFFERS_FROM_SENT"
    return "CONTRACT_OBSERVED"


def build_report(
    *,
    attached: Any,
    response: Any,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    attached_model = getattr(attached, "detected_model", None)
    attached_reasoning = getattr(attached, "detected_reasoning_effort", None)
    request_contract = _request_contract(response.request)
    field_evidence: list[dict[str, str]] = []
    event_types: list[str] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type:
            event_types.append(event_type)
        field_evidence.extend(_walk_contract_fields(event))

    unique_evidence = {
        (item["kind"], item["path"], item["value"]): item
        for item in field_evidence
    }
    field_evidence = [unique_evidence[key] for key in sorted(unique_evidence)]

    report = {
        "schema": PROBE_SCHEMA,
        "probe": {
            "preserve_model": True,
            "existing_conversation": True,
            "response_text_recorded": False,
            "prompt_text_recorded": False,
            "raw_event_payloads_recorded": False,
        },
        "attach": {
            "detected_model": attached_model,
            "detected_reasoning_effort": attached_reasoning,
            "conversation_id_present": bool(getattr(attached, "conversation_id", None)),
            "current_node_present": bool(getattr(attached, "current_node", None)),
        },
        "request": request_contract,
        "transport": _transport_summary(event_types, request_contract),
        "field_evidence": field_evidence,
    }
    report["verdict"] = _verdict(
        attached_model=attached_model,
        attached_reasoning=attached_reasoning,
        request_contract=request_contract,
        field_evidence=field_evidence,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture a privacy-safe live ChatGPT web model/transport contract report.",
    )
    parser.add_argument("conversation", help="Existing ChatGPT conversation URL or raw id.")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", default="live_contract_probe.json")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    attached = client.attach_conversation(args.conversation)
    events: list[dict[str, Any]] = []

    def on_event(event: dict[str, Any]) -> None:
        if isinstance(event, dict):
            events.append(event)

    response = client.send_to_conversation(
        args.conversation,
        args.prompt,
        model=None,
        reasoning_effort=None,
        preserve_model=True,
        on_event=on_event,
    )
    report = build_report(attached=attached, response=response, events=events)

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"report: {output_path}")


if __name__ == "__main__":
    main()
