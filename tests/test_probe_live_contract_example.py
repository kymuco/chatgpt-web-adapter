from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "probe_live_contract.py"


def _load_module():
    if "chatgpt_web_adapter" not in sys.modules:
        stub = types.ModuleType("chatgpt_web_adapter")
        stub.ChatGPTWebClient = object
        stub.RequestError = RuntimeError
        sys.modules["chatgpt_web_adapter"] = stub
    spec = importlib.util.spec_from_file_location("probe_live_contract_example", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


def _attached():
    return SimpleNamespace(
        detected_model="gpt-5-6-sol-web",
        detected_reasoning_effort="extended",
        conversation_id="conv-secret",
        current_node="node-secret",
    )


def _response(**overrides):
    payload = {
        "requested_model": None,
        "requested_reasoning_effort": None,
        "sent_model": "gpt-5-6-sol-web",
        "sent_reasoning_effort": "extended",
        "observed_model": "gpt-5-6-sol-web",
        "observed_reasoning_effort": "extended",
        "conversation_id": "conv-secret",
        "parent_message_id": "message-secret",
        "turn_exchange_id": "turn-secret",
        "resume_token_present": True,
        "resume_ws_topic_id": "topic-secret",
        "resume_ws_url_present": True,
        "resume_ws_url_scheme": "wss",
        "resume_ws_url_host": "chatgpt.com",
        "handoff_recovery_mode": "websocket_topic",
    }
    payload.update(overrides)
    return SimpleNamespace(request=_Request(payload))


def test_report_does_not_serialize_prompt_response_or_ids() -> None:
    module = _load_module()
    events = [
        {
            "type": "request_payload_prepared",
            "prompt": "TOP SECRET PROMPT",
            "conversation_id": "conv-secret",
            "token": "resume-secret",
            "payload": {
                "model": "gpt-5-6-sol-web",
                "thinking_effort": "extended",
                "messages": [{"content": {"parts": ["TOP SECRET PROMPT"]}}],
            },
        },
        {
            "type": "raw_ws_event",
            "raw": "TOP SECRET RAW FRAME",
            "parsed": {
                "message_id": "message-secret",
                "model_slug": "gpt-5-6-sol-web",
                "content": {"parts": ["TOP SECRET RESPONSE"]},
            },
        },
    ]

    report = module.build_report(attached=_attached(), response=_response(), events=events)
    serialized = json.dumps(report, sort_keys=True)

    for secret in (
        "TOP SECRET PROMPT",
        "TOP SECRET RESPONSE",
        "TOP SECRET RAW FRAME",
        "conv-secret",
        "message-secret",
        "turn-secret",
        "topic-secret",
        "resume-secret",
    ):
        assert secret not in serialized
    assert report["request"]["conversation_id_present"] is True
    assert report["request"]["parent_message_id_present"] is True


def test_field_evidence_collects_only_model_and_reasoning_scalars() -> None:
    module = _load_module()
    evidence = module._walk_contract_fields(
        {
            "metadata": {
                "model_slug": "gpt-5-6-sol-web",
                "thinking_effort": "extra-high",
                "other": "must-not-be-recorded",
                "selected_model": {"slug": "nested-object-is-not-a-scalar"},
            }
        }
    )

    assert evidence == [
        {"path": "$.metadata.model_slug", "kind": "model", "value": "gpt-5-6-sol-web"},
        {"path": "$.metadata.thinking_effort", "kind": "reasoning", "value": "extra-high"},
    ]


def test_matching_preserved_contract_is_observed() -> None:
    module = _load_module()
    report = module.build_report(
        attached=_attached(),
        response=_response(),
        events=[{"type": "raw_sse_event", "parsed": {"model_slug": "gpt-5-6-sol-web"}}],
    )

    assert report["verdict"] == "CONTRACT_OBSERVED"
    assert report["transport"]["saw_raw_sse_event"] is True


def test_detector_drift_gets_explicit_verdict() -> None:
    module = _load_module()
    report = module.build_report(
        attached=_attached(),
        response=_response(sent_model="another-web-slug", observed_model="another-web-slug"),
        events=[],
    )

    assert report["verdict"] == "PRESERVE_MODEL_MISMATCH"


def test_attach_only_report_keeps_detected_contract_without_request() -> None:
    module = _load_module()

    report = module.build_report(attached=_attached(), response=None, events=[])

    assert report["attach"]["detected_model"] == "gpt-5-6-sol-web"
    assert report["attach"]["detected_reasoning_effort"] == "extended"
    assert report["probe"]["write_attempted"] is False
    assert report["request"]["sent_model"] is None
    assert report["verdict"] == "CONTRACT_OBSERVED"
