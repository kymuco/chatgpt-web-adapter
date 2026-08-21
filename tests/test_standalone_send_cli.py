from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.cli as cli


def _execution(text: str = "assistant reply"):
    response = SimpleNamespace(
        text=text,
        title="Conversation",
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id="assistant-1",
            finish_reason="stop",
        ),
        request=SimpleNamespace(observed_model="gpt-test", temporary=False),
        metrics=SimpleNamespace(backend_status=200),
    )
    observation = SimpleNamespace(
        to_dict=lambda: {
            "runtime_tab_id": 77,
            "runtime_tab_preexisting": True,
            "runtime_tab_created_for_turn": False,
        }
    )
    provenance = SimpleNamespace(
        to_dict=lambda: {
            "transport": "browser-owned",
            "completion": {
                "completed": True,
                "source": "CANONICAL_READBACK",
                "canonical_completion_proven": True,
            },
        }
    )
    return SimpleNamespace(
        transport="browser-owned",
        response=response,
        observation=observation,
        provenance=provenance,
    )


class _Runtime:
    def __init__(self, *, events=None, final_text: str = "assistant reply") -> None:
        self.events = list(events or [])
        self.final_text = final_text
        self.send_call = None

    def send_text_observed(self, text, **kwargs):
        self.send_call = (text, kwargs)
        on_event = kwargs.get("on_event")
        if on_event is not None:
            for event in self.events:
                on_event(event)
        return _execution(self.final_text)


def test_standalone_send_defaults_to_deep_high_policy(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    captured = {}

    def fake_assemble(**kwargs):
        captured.update(kwargs)
        return runtime

    monkeypatch.setattr(cli, "assemble_product_runtime", fake_assemble)

    code = cli.main(["send", "hello"])

    assert code == 0
    assert capsys.readouterr().out == "assistant reply\n"
    assert captured["transport"] == "browser-owned"
    assert runtime.send_call == (
        "hello",
        {
            "conversation": None,
            "timeout": 150.0,
            "poll_interval": 0.5,
            "on_event": None,
            "model_profile": "DEEP",
            "conversation_mode": "normal",
        },
    )


def test_standalone_send_profile_is_case_insensitive(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(
        [
            "send",
            "hello",
            "--conversation",
            "conversation-1",
            "--profile",
            "fast",
            "--timeout",
            "25",
            "--poll-interval",
            "0.25",
        ]
    )

    assert code == 0
    assert capsys.readouterr().out == "assistant reply\n"
    assert runtime.send_call[1]["conversation"] == "conversation-1"
    assert runtime.send_call[1]["model_profile"] == "FAST"
    assert runtime.send_call[1]["conversation_mode"] == "normal"
    assert runtime.send_call[1]["timeout"] == 25.0
    assert runtime.send_call[1]["poll_interval"] == 0.25


def test_standalone_send_json_keeps_structured_execution(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["send", "hello", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert runtime.send_call[1]["model_profile"] == "DEEP"
    assert runtime.send_call[1]["conversation_mode"] == "normal"
    assert payload["ok"] is True
    assert payload["text"] == "assistant reply"
    assert payload["conversation_id"] == "conversation-1"
    assert payload["temporary"] is False
    assert payload["runtime_observation"]["runtime_tab_id"] == 77
    assert payload["provenance"]["completion"]["source"] == "CANONICAL_READBACK"


def test_standalone_stream_renders_append_revision_and_canonical_truthfully(
    monkeypatch,
    capsys,
) -> None:
    runtime = _Runtime(
        events=[
            {
                "type": "assistant_text_snapshot",
                "sequence": 1,
                "message_id": "assistant-1",
                "text": "Hel",
            },
            {
                "type": "assistant_text_delta",
                "sequence": 2,
                "message_id": "assistant-1",
                "delta": "lo",
            },
            {
                "type": "assistant_text_revision",
                "sequence": 3,
                "message_id": "assistant-1",
                "text": "Hello!",
            },
            {
                "type": "canonical_text_finalized",
                "message_id": "assistant-1",
                "text": "Hello final",
                "reconciliation": "STREAM_REVISED_BY_CANONICAL",
            },
        ],
        final_text="Hello final",
    )
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["send", "hello", "--stream"])

    output = capsys.readouterr().out
    assert code == 0
    assert output == (
        "Hello!\n"
        "[canonical]\n"
        "Hello final\n"
    )
    assert callable(runtime.send_call[1]["on_event"])
    assert runtime.send_call[1]["model_profile"] == "DEEP"


def test_standalone_stream_ignores_duplicate_sequence(monkeypatch, capsys) -> None:
    runtime = _Runtime(
        events=[
            {
                "type": "assistant_text_snapshot",
                "sequence": 1,
                "message_id": "assistant-1",
                "text": "Hi",
            },
            {
                "type": "assistant_text_delta",
                "sequence": 2,
                "message_id": "assistant-1",
                "delta": "!",
            },
            {
                "type": "assistant_text_delta",
                "sequence": 2,
                "message_id": "assistant-1",
                "delta": "!",
            },
        ],
        final_text="Hi!",
    )
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["send", "hello", "--stream"])

    assert code == 0
    assert capsys.readouterr().out == "Hi!\n"


def test_standalone_stream_falls_back_to_canonical_when_no_events(
    monkeypatch,
    capsys,
) -> None:
    runtime = _Runtime(events=[], final_text="canonical only")
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["send", "hello", "--stream"])

    assert code == 0
    assert capsys.readouterr().out == "canonical only\n"


def test_standalone_send_rejects_stream_and_json_together() -> None:
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(["send", "hello", "--stream", "--json"])


def test_standalone_send_rejects_unmapped_profile() -> None:
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(["send", "hello", "--profile", "MAX"])
