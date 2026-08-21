from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.cli_v02 as cli


class _Health:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.reason = "ready" if ready else "bridge unavailable"
        self.conversation_id = "conversation-1"
        self.canonical_status = "completed" if ready else None
        self.extension_connected = ready

    def to_dict(self):
        return {
            "transport": "browser-owned",
            "ready": self.ready,
            "reason": self.reason,
            "conversation_id": self.conversation_id,
            "canonical_status": self.canonical_status,
            "canonical_read_checked": True,
            "read_plane": "BROWSERLESS_CANONICAL_HTTP",
            "session_plane": "CANONICAL_SESSION",
            "write_plane": "BROWSER_NATIVE_PAGE_OWNED_WRITE",
            "automatic_write_retry": False,
            "fallback_transport": None,
            "bridge_available": self.ready,
            "extension_connected": self.extension_connected,
            "runtime_tab_id": 7 if self.ready else None,
            "runtime_tab_preexisting": True if self.ready else None,
        }


class _CapabilitySet:
    def to_dict(self):
        return {
            "transport": "browser-owned",
            "product_semantics": "ordinary-chatgpt",
            "capabilities": {
                "streaming": {
                    "state": "AVAILABLE",
                    "owner": "TRANSPORT",
                    "evidence": "test",
                },
                "temporary_chat": {
                    "state": "AVAILABLE",
                    "owner": "TRANSPORT",
                    "evidence": "test",
                },
            },
        }


class _Message:
    def __init__(self, role: str, text: str) -> None:
        self.role = role
        self.text = text

    def to_dict(self):
        return {
            "node_id": f"node-{self.role}",
            "message_id": f"message-{self.role}",
            "role": self.role,
            "text": self.text,
            "create_time": 1.0,
            "recipient": None,
            "model": None,
            "finish_reason": None,
            "metadata_preview": {},
        }


class _Runtime:
    transport = "browser-owned"

    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.message_call = None
        self.write_called = False

    def health(self, conversation=None):
        return _Health(ready=self.ready)

    def capabilities(self):
        return _CapabilitySet()

    def get_messages(self, conversation, **kwargs):
        self.message_call = (conversation, kwargs)
        return [_Message("user", "hello"), _Message("assistant", "world")]

    def send_text_observed(self, *args, **kwargs):
        self.write_called = True
        raise AssertionError("PR8.14 inspection commands must not write")


def test_product_native_and_semantic_profile_names_normalize_to_proven_keys() -> None:
    assert cli.normalize_public_model_profile("INSTANT") == "FAST"
    assert cli.normalize_public_model_profile("fast") == "FAST"
    assert cli.normalize_public_model_profile("MEDIUM") == "BALANCED"
    assert cli.normalize_public_model_profile("balanced") == "BALANCED"
    assert cli.normalize_public_model_profile("HIGH") == "DEEP"
    assert cli.normalize_public_model_profile("deep") == "DEEP"
    assert cli.product_native_model_profile("DEEP") == "HIGH"

    with pytest.raises(ValueError, match="unsupported profile"):
        cli.normalize_public_model_profile("MAX")


def test_send_accepts_product_native_alias_and_delegates_canonical_profile(monkeypatch) -> None:
    captured = {}

    def fake_run_send(args):
        captured["profile"] = args.profile
        return 0

    monkeypatch.setattr(cli.legacy_cli, "_run_send", fake_run_send)

    assert cli.main(["send", "hello", "--profile", "HIGH"]) == 0
    assert captured["profile"] == "DEEP"

    assert cli.main(["send", "hello", "--profile", "medium"]) == 0
    assert captured["profile"] == "BALANCED"

    assert cli.main(["send", "hello", "--profile", "instant"]) == 0
    assert captured["profile"] == "FAST"


def test_profile_contract_exposes_product_names_first_and_keeps_semantic_aliases() -> None:
    contract = cli.model_profile_contract()

    assert contract["default"] == "HIGH"
    assert contract["product_native"] == ["INSTANT", "MEDIUM", "HIGH"]
    assert contract["semantic_aliases"] == {
        "FAST": "INSTANT",
        "BALANCED": "MEDIUM",
        "DEEP": "HIGH",
    }
    assert contract["normalization"] == {
        "INSTANT": "FAST",
        "MEDIUM": "BALANCED",
        "HIGH": "DEEP",
    }
    assert contract["max_mapped"] is False


def test_status_is_read_only_and_unhealthy_state_uses_exit_one(monkeypatch, capsys) -> None:
    runtime = _Runtime(ready=False)
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["status", "--conversation", "conversation-1", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_UNAVAILABLE
    assert payload["schema"] == 1
    assert payload["command"] == "status"
    assert payload["ok"] is False
    assert payload["health"]["ready"] is False
    assert runtime.write_called is False


def test_capabilities_is_read_only_and_exports_profile_alias_contract(monkeypatch, capsys) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(["capabilities", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert payload["schema"] == 1
    assert payload["command"] == "capabilities"
    assert payload["ok"] is True
    assert payload["product"]["capabilities"]["temporary_chat"]["state"] == "AVAILABLE"
    assert payload["model_profiles"]["default"] == "HIGH"
    assert runtime.write_called is False


def test_messages_reads_canonical_current_branch_without_creating_artifacts(
    monkeypatch,
    capsys,
) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: runtime)

    code = cli.main(
        [
            "messages",
            "https://chatgpt.com/c/conversation-1",
            "--limit",
            "2",
            "--role",
            "user",
            "--role",
            "assistant",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert payload["schema"] == 1
    assert payload["command"] == "messages"
    assert payload["conversation_id"] == "conversation-1"
    assert payload["count"] == 2
    assert [item["role"] for item in payload["messages"]] == ["user", "assistant"]
    conversation, kwargs = runtime.message_call
    assert conversation.conversation_id == "conversation-1"
    assert kwargs == {
        "limit": 2,
        "roles": ["user", "assistant"],
        "include_empty": False,
    }
    assert runtime.write_called is False


def test_negative_message_limit_is_usage_error_with_stable_json_envelope(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: _Runtime())

    code = cli.main(["messages", "conversation-1", "--limit", "-1", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert captured.out == ""
    assert code == cli.EXIT_USAGE
    assert payload["schema"] == 1
    assert payload["ok"] is False
    assert payload["error"]["exit_code"] == cli.EXIT_USAGE
    assert payload["error"]["type"] == "ValueError"


def test_operational_failure_uses_exit_three(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "assemble_product_runtime",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("transport failed")),
    )

    code = cli.main(["status", "--json"])

    payload = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_OPERATION_FAILED
    assert payload["error"]["exit_code"] == cli.EXIT_OPERATION_FAILED
    assert payload["error"]["message"] == "transport failed"


def test_reconciliation_required_failure_uses_exit_four(monkeypatch, capsys) -> None:
    class _Ambiguous(RuntimeError):
        reconciliation_required = True
        write_may_have_been_submitted = True
        request_stage = "conversation_write"

    monkeypatch.setattr(
        cli.legacy_cli,
        "_run_send",
        lambda args: (_ for _ in ()).throw(_Ambiguous("write outcome ambiguous")),
    )

    code = cli.main(["send", "hello", "--json"])

    payload = json.loads(capsys.readouterr().err)
    assert code == cli.EXIT_RECONCILIATION_REQUIRED
    assert payload["error"]["exit_code"] == cli.EXIT_RECONCILIATION_REQUIRED
    assert payload["error"]["reconciliation_required"] is True
    assert payload["error"]["write_may_have_been_submitted"] is True


def test_public_console_scripts_route_through_stable_pr814_front_controller() -> None:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert 'chatgpt-web-adapter = "chatgpt_web_adapter.cli_v02:main"' in text
    assert 'cwa = "chatgpt_web_adapter.cli_v02:main"' in text
