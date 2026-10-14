from __future__ import annotations

from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.qwen_web import QwenBrowserTurnProvider

EXT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)


def test_auth_snapshot_requires_explicit_operation_and_scoped_cookie_access():
    source = (EXT / "service_worker_qwen_provider.js").read_text(encoding="utf-8")
    assert "allowAuthExport !== true" in source
    assert "Network.getCookies" in source
    assert 'CWA_QWEN_ORIGIN + "/"' in source
    assert "https://accounts.google.com" not in source
    assert "await chrome.debugger.detach" in source
    assert "localStorage.getItem('qwen_access_token_state')" in source


def test_auth_snapshot_rpc_is_explicit_and_does_not_write():
    provider = QwenBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)
    captured = []

    def fake(payload, *, timeout, on_event=None):
        captured.append(dict(payload))
        return {
            "request_id": payload["request_id"],
            "ok": True,
            "providerId": "qwen",
            "operation": "auth_snapshot",
            "accessToken": "sample-token",
            "cookies": {"session": "sample"},
            "expiresAt": None,
        }

    provider._rpc = fake
    result = provider.export_auth()
    assert result.access_token == "sample-token"
    assert result.cookies == {"session": "sample"}
    assert captured[0]["operation"] == "export_auth"
    assert captured[0]["allowAuthExport"] is True
    assert "text" not in captured[0]


def test_auth_snapshot_fails_closed_on_uncertain_bridge():
    provider = QwenBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)
    provider._rpc = lambda payload, *, timeout, on_event=None: {"ok": False}
    with pytest.raises(RequestError, match="QWEN_AUTH_SNAPSHOT_UNAVAILABLE"):
        provider.export_auth()
