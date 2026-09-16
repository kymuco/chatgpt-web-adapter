from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_owned_write_runtime as base_subject
from chatgpt_web_adapter.browser_authority_commit_provider import (
    CommitBoundProductModelProfileProvider,
)
from chatgpt_web_adapter.browser_authority_commit_runtime import (
    CommitBoundBrowserOwnedProductWriteRuntime,
    WRITE_NOT_SUBMITTED,
)
from chatgpt_web_adapter.browser_owned_write_runtime import BrowserOwnedWriteRuntimeError
from chatgpt_web_adapter.exceptions import RequestError


class _Provider(CommitBoundProductModelProfileProvider):
    def __init__(self) -> None:
        super().__init__(connect_timeout=0.1, turn_timeout=1.0)

    def status(self):
        return SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=17,
        )


class _Client:
    def __init__(self, provider: _Provider) -> None:
        self.provider = provider
        self.read_count = 0

    def get_status(self, conversation):
        del conversation
        self.read_count += 1
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        del conversation, kwargs
        self.read_count += 1
        return []

    def complete_canonical_readback(self):
        return True


def test_prewrite_failure_is_not_misclassified_as_possible_write(monkeypatch) -> None:
    provider = _Provider()
    client = _Client(provider)
    runtime = CommitBoundBrowserOwnedProductWriteRuntime(client, provider=provider)

    def fail_before_provider_delegation(*args, **kwargs):
        del args, kwargs
        raise RequestError("prewrite baseline failed", request_stage="test_prewrite")

    monkeypatch.setattr(
        base_subject,
        "send_browser_native",
        fail_before_provider_delegation,
    )

    with pytest.raises(BrowserOwnedWriteRuntimeError) as captured:
        runtime.send_text("continue", conversation="conversation-1")

    error = captured.value
    assert error.failure_kind == WRITE_NOT_SUBMITTED
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert error.manual_retry_safe_after_repair is True
    assert error.automatic_retry_allowed is False
    assert error.request_stage == "browser_owned_write_prewrite"
    assert provider._browser_authority_write_boundary_entered("missing") is False


def test_entered_provider_boundary_preserves_ambiguity(monkeypatch) -> None:
    provider = _Provider()
    client = _Client(provider)
    runtime = CommitBoundBrowserOwnedProductWriteRuntime(client, provider=provider)

    def fail_after_provider_boundary(*args, **kwargs):
        del args, kwargs
        provider._activate_pending_browser_authority_lease()
        raise RequestError("delegated outcome unknown", request_stage="test_write")

    monkeypatch.setattr(base_subject, "send_browser_native", fail_after_provider_boundary)

    with pytest.raises(BrowserOwnedWriteRuntimeError) as captured:
        runtime.send_text("continue", conversation="conversation-1")

    error = captured.value
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert error.manual_retry_safe_after_repair is False
    assert error.request_stage == "browser_owned_write"
