from __future__ import annotations

import json
from types import SimpleNamespace

import chatgpt_web_adapter.cli as cli


class _Health:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready

    def to_dict(self):
        return {
            "transport": "browser-owned",
            "ready": self.ready,
            "reason": "READY_FOR_BROWSER_OWNED_WRITE" if self.ready else "NOT_READY",
        }


class _Runtime:
    transport = "browser-owned"

    def health(self, conversation=None):
        self.health_conversation = conversation
        return _Health(ready=True)

    def governance(self):
        return {
            "transport": "browser-owned",
            "fallback_transport": None,
            "legacy_direct_write_fallback": False,
        }

    def send_text_observed(self, text, **kwargs):
        self.send_call = (text, kwargs)
        response = SimpleNamespace(
            text="assistant reply",
            title="Conversation",
            conversation=SimpleNamespace(
                conversation_id="conversation-1",
                message_id="assistant-1",
                finish_reason="stop",
            ),
            request=SimpleNamespace(observed_model="gpt-test"),
            metrics=SimpleNamespace(backend_status=200),
        )
        observation = SimpleNamespace(
            to_dict=lambda: {
                "runtime_tab_id": 77,
                "runtime_tab_preexisting": True,
                "runtime_tab_created_for_turn": False,
            }
        )
        return SimpleNamespace(
            transport="browser-owned",
            response=response,
            observation=observation,
        )


def test_runtime_status_cli_uses_product_assembly(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    captured = {}

    def fake_assemble(**kwargs):
        captured.update(kwargs)
        return runtime

    monkeypatch.setattr(cli, "assemble_product_runtime", fake_assemble)

    code = cli.main([
        "runtime",
        "status",
        "--transport",
        "browser-owned",
        "--conversation",
        "conversation-1",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert captured["transport"] == "browser-owned"
    assert runtime.health_conversation == "conversation-1"
    assert payload["transport"] == "browser-owned"
    assert payload["health"]["ready"] is True
    assert payload["governance"]["fallback_transport"] is None


def test_runtime_send_cli_returns_machine_readable_product_result(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main([
        "runtime",
        "send",
        "hello",
        "--conversation",
        "conversation-1",
        "--timeout",
        "25",
        "--poll-interval",
        "0.25",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert runtime.send_call == (
        "hello",
        {
            "conversation": "conversation-1",
            "timeout": 25.0,
            "poll_interval": 0.25,
        },
    )
    assert payload["ok"] is True
    assert payload["conversation_id"] == "conversation-1"
    assert payload["message_id"] == "assistant-1"
    assert payload["backend_status"] == 200
    assert payload["runtime_observation"]["runtime_tab_id"] == 77
