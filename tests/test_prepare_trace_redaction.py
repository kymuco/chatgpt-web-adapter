from __future__ import annotations

import json
from pathlib import Path

import chatgpt_web_adapter as adapter

from chatgpt_web_adapter.conversation_prepare import prepare_text_turn


def test_prepare_debug_trace_never_serializes_conduit_token(tmp_path: Path) -> None:
    secret = "secret-conduit-credential"

    class TraceClient(adapter.ChatGPTWebClient):
        def __init__(self) -> None:
            self.debug_trace_dir = tmp_path
            self.debug_trace_sanitize = False
            self._debug_trace_counter = 0

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        def _json_request(self, method, url, payload, headers):
            # The generic HTTP tracer must be disabled while the credential-
            # bearing prepare response is in flight.
            assert self.debug_trace_dir is None
            return 200, {"status": "ok", "conduit_token": secret}

    client = TraceClient()
    result, _payload = prepare_text_turn(
        client,
        "secret prompt",
        model="gpt-5-6-thinking",
        conversation={"conversation_id": "conv-1", "message_id": "parent-1"},
        partial_query_message_id="user-1",
    )

    assert result.conduit_token == secret
    traces = sorted(tmp_path.glob("*.json"))
    assert len(traces) == 1
    rendered = traces[0].read_text(encoding="utf-8")
    assert secret not in rendered
    assert "secret prompt" not in rendered

    payload = json.loads(rendered)
    assert payload["conduit_token_present"] is True
    assert payload["raw_response_recorded"] is False
    assert payload["response_keys"] == ["conduit_token", "status"]
