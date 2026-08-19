from __future__ import annotations

import pytest

from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider
from chatgpt_web_adapter.exceptions import RequestError


def test_release_runtime_tab_sends_exact_fences(monkeypatch):
    provider = BrowserNativeTurnProvider()
    seen = {}

    def fake_rpc(payload, *, timeout):
        seen["payload"] = payload
        seen["timeout"] = timeout
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "released": True,
            "alreadyAbsent": False,
            "runtimeTabId": 77,
            "browserAuthorityLeaseId": "lease-1",
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    result = provider.release_runtime_tab(
        expected_runtime_tab_id=77,
        browser_authority_lease_id="lease-1",
        timeout=4.0,
    )
    assert seen["payload"]["type"] == "release_runtime_tab"
    assert seen["payload"]["expectedRuntimeTabId"] == 77
    assert seen["payload"]["browserAuthorityLeaseId"] == "lease-1"
    assert result.released is True
    assert result.runtime_tab_id == 77


def test_release_runtime_tab_rejects_lease_mismatch(monkeypatch):
    provider = BrowserNativeTurnProvider()

    def fake_rpc(payload, *, timeout):
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "released": True,
            "browserAuthorityLeaseId": "newer-lease",
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    with pytest.raises(RequestError, match="AUTHORITY_LEASE_MISMATCH"):
        provider.release_runtime_tab(
            expected_runtime_tab_id=77,
            browser_authority_lease_id="old-lease",
        )


def test_thread_local_lease_is_forwarded_to_turn_and_echo_verified(monkeypatch):
    provider = BrowserNativeTurnProvider()
    seen = {}

    def fake_rpc(payload, *, timeout):
        seen.update(payload)
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": "conversation-1",
            "responseStatus": 200,
            "tabId": 77,
            "tabWasActive": False,
            "browserAuthorityLeaseId": "lease-1",
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    provider.set_browser_authority_lease("lease-1")
    try:
        result = provider.send_text("hello")
    finally:
        provider.clear_browser_authority_lease()

    assert seen["browserAuthorityLeaseId"] == "lease-1"
    assert result.browser_authority_lease_id == "lease-1"


def test_unbound_research_turn_remains_compatible(monkeypatch):
    provider = BrowserNativeTurnProvider()
    seen = {}

    def fake_rpc(payload, *, timeout):
        seen.update(payload)
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": "conversation-1",
            "responseStatus": 200,
            "tabWasActive": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    result = provider.send_text("probe")
    assert seen["browserAuthorityLeaseId"] is None
    assert result.browser_authority_lease_id is None
