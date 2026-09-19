from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import retained_conversation_tabs_live_gate as subject


class _Observation:
    def __init__(self, tab_id: int) -> None:
        self.runtime_tab_id = tab_id

    def to_dict(self) -> dict[str, object]:
        return {"runtime_tab_id": self.runtime_tab_id}


def _execution(text: str, conversation_id: str, tab_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        response=SimpleNamespace(
            text=text,
            conversation=SimpleNamespace(
                conversation_id=conversation_id,
                message_id=f"message-{text.lower()}",
            ),
        ),
        observation=_Observation(tab_id),
    )


class _Runtime:
    def __init__(self, *, shared_saved_tab: bool = False) -> None:
        tab_b = 10 if shared_saved_tab else 20
        self._executions = iter(
            [
                _execution(subject.A_SEED, "conversation-a", 10),
                _execution(subject.A_BIND, "conversation-a", 10),
                _execution(subject.B_SEED, "conversation-b", tab_b),
                _execution(subject.B_BIND, "conversation-b", tab_b),
                _execution(subject.A_REVISIT, "conversation-a", 10),
                _execution(subject.B_REVISIT, "conversation-b", tab_b),
                _execution(subject.TEMPORARY_EXPECTED, "temporary-c", 30),
            ]
        )
        self.send_calls: list[dict[str, object]] = []
        self.end_calls = 0

    def send_text_observed(self, text: str, **kwargs: object) -> SimpleNamespace:
        self.send_calls.append({"text": text, **kwargs})
        return next(self._executions)

    def end_temporary_chat(self) -> bool:
        self.end_calls += 1
        return True

    def temporary_lifecycle_snapshot(self) -> dict[str, object]:
        return {
            "state": "NOT_ESTABLISHED",
            "conversation_id": None,
            "token_present": False,
            "token_exported": False,
        }


def _deployment_status() -> dict[str, object]:
    revision = "a" * 40
    return {
        "healthy": True,
        "source_revision": revision,
        "deployment": {"source_revision": revision},
        "extension_digest_matches": True,
        "host_matches_current_environment": True,
        "installed_extension_digest": "digest",
        "installed_extension_dir": "extension",
        "current_host_executable": "native-host",
    }


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    runtime: _Runtime,
) -> None:
    monkeypatch.setattr(
        subject,
        "browser_native_deployment_status",
        _deployment_status,
    )
    monkeypatch.setattr(
        subject,
        "assemble_product_runtime",
        lambda **kwargs: runtime,
    )
    monkeypatch.setattr(
        subject,
        "_validate_temporary_execution",
        lambda execution, **kwargs: {
            "response": execution.response.text,
            "conversation_id": execution.response.conversation.conversation_id,
            "browser_authority_lease_id": "temporary-lease",
            "temporary_mode_proven": True,
            "temporary_prewrite_proof": (
                "FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE"
            ),
        },
    )


def test_live_gate_proves_distinct_retained_tabs_and_temporary_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime()
    _patch_dependencies(monkeypatch, runtime)

    report = subject.run_live_gate(auth_file="auth.json", timeout=30.0)

    assert report["ok"] is True
    assert report["product_write_budget"] == 7
    assert report["product_write_completions"] == 7
    assert report["summary"]["distinct_retained_tabs_proven"] is True
    assert report["summary"]["conversation_a_exact_tab_reuse_proven"] is True
    assert report["summary"]["conversation_b_exact_tab_reuse_proven"] is True
    assert report["summary"]["temporary_close_entered_after_proven_turn"] is True
    assert report["summary"]["consumer_dependency"] is False
    assert runtime.end_calls == 1
    assert len(runtime.send_calls) == 7
    assert runtime.send_calls[-1]["conversation_mode"] == "temporary"


def test_live_gate_rejects_two_saved_conversations_sharing_one_tab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime(shared_saved_tab=True)
    _patch_dependencies(monkeypatch, runtime)

    with pytest.raises(
        RuntimeError,
        match="PR14_8_DISTINCT_CONVERSATIONS_SHARE_RETAINED_TAB",
    ):
        subject.run_live_gate(auth_file="auth.json", timeout=30.0)

    assert runtime.end_calls == 0
