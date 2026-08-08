from __future__ import annotations

import importlib.util
from pathlib import Path

from chatgpt_web_adapter.conversation_prepare import PrepareResult


def _load_probe_module():
    path = Path(__file__).resolve().parents[1] / "examples" / "probe_prepare_contract.py"
    spec = importlib.util.spec_from_file_location("probe_prepare_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepare_probe_report_does_not_serialize_prompt_or_conduit_token() -> None:
    probe = _load_probe_module()
    result = PrepareResult(
        status_code=200,
        status_ok=True,
        conduit_token_present=True,
        response_keys=("conduit_token", "status"),
        conduit_token="secret-conduit-token",
    )
    payload = {
        "conversation_id": "secret-conversation-id",
        "client_prepare_state": "success",
        "thinking_effort": "extended",
        "partial_query": {
            "id": "secret-message-id",
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": ["secret prompt text"]},
        },
    }

    report = probe.build_report(result, payload)
    rendered = str(report)
    assert probe.verdict(report) == "PREPARE_CONTRACT_OBSERVED"
    assert "secret-conduit-token" not in rendered
    assert "secret prompt text" not in rendered
    assert "secret-conversation-id" not in rendered
    assert "secret-message-id" not in rendered
    assert report["prepare"]["conduit_token_present"] is True
    assert report["prepare"]["partial_query_present"] is True
    assert report["prepare"]["partial_query_text_recorded"] is False


def test_prepare_probe_reports_rejection_without_raw_body() -> None:
    probe = _load_probe_module()
    result = PrepareResult(
        status_code=403,
        status_ok=False,
        conduit_token_present=False,
        response_keys=("detail",),
    )
    report = probe.build_report(result, {"partial_query": {}, "client_prepare_state": "success"})
    assert probe.verdict(report) == "PREPARE_REJECTED"
    assert report["probe"]["raw_response_recorded"] is False
