from __future__ import annotations

import json
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter import auth_current_chrome
from chatgpt_web_adapter.exceptions import AuthError, RequestError


def _capture_payload(**changes):
    payload = {
        "ok": True,
        "type": "current_chrome_auth_result",
        "request_id": "request-1",
        "accessToken": "access-token",
        "sessionToken": "session-token",
        "expires": "2030-01-01T00:00:00Z",
        "browserCookies": [
            {
                "name": "__Secure-next-auth.session-token",
                "value": "session-token",
                "domain": ".chatgpt.com",
                "path": "/",
                "secure": True,
                "http_only": True,
            }
        ],
        "userAgent": "Current Chrome",
        "tabId": 42,
    }
    payload.update(changes)
    return payload


def test_public_current_tab_login_persists_only_captured_account(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "old-access",
                "sessionToken": "old-session",
                "cookies": {"old-cookie": "old-value"},
                "unknownOldField": "must-not-cross-accounts",
            }
        ),
        encoding="utf-8",
    )

    class Provider:
        def __init__(self, *, state_dir=None):
            assert state_dir == tmp_path / "bridge"

        def capture_current_chrome_auth(self, *, timeout):
            assert timeout == 120
            return _capture_payload()

    monkeypatch.setattr(auth_current_chrome, "BrowserNativeTurnProvider", Provider)

    result = adapter.browser_login_current_tab(
        auth_file,
        timeout=120,
        persist=True,
        fresh=True,
        state_dir=tmp_path / "bridge",
    )

    saved = json.loads(auth_file.read_text(encoding="utf-8"))
    assert result.auth_file == auth_file
    assert result.tab_id == 42
    assert result.persisted is True
    assert saved["accessToken"] == "access-token"
    assert saved["sessionToken"] == "session-token"
    assert saved["authSource"] == "current-chrome-tab"
    assert saved["headers"]["user-agent"] == "Current Chrome"
    assert "old-cookie" not in saved["cookies"]
    assert "unknownOldField" not in saved
    assert "old-access" not in auth_file.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "payload",
    [
        _capture_payload(accessToken=""),
        _capture_payload(browserCookies=[]),
        _capture_payload(
            browserCookies=[
                {
                    "name": "__Secure-next-auth.session-token",
                    "value": "secret",
                    "domain": "evilchatgpt.com",
                    "path": "/",
                }
            ]
        ),
        _capture_payload(
            browserCookies=[
                {
                    "name": "__Secure-next-auth.session-token",
                    "value": "secret",
                    "domain": ".chatgpt.com.evil.example",
                    "path": "/",
                }
            ]
        ),
    ],
)
def test_current_tab_login_rejects_invalid_secret_payload_without_persisting(
    tmp_path, monkeypatch, payload
) -> None:
    class Provider:
        def __init__(self, *, state_dir=None):
            pass

        def capture_current_chrome_auth(self, *, timeout):
            return payload

    monkeypatch.setattr(auth_current_chrome, "BrowserNativeTurnProvider", Provider)
    auth_file = tmp_path / "auth.json"

    with pytest.raises(AuthError):
        adapter.browser_login_current_tab(auth_file, timeout=1)

    assert not auth_file.exists()


def test_current_tab_login_errors_never_echo_captured_secrets(tmp_path, monkeypatch) -> None:
    class Provider:
        def __init__(self, *, state_dir=None):
            pass

        def capture_current_chrome_auth(self, *, timeout):
            raise RequestError(
                "BROWSER_NATIVE_EXTENSION_TIMEOUT: secret-value",
                request_stage="browser_native_bridge",
            )

    monkeypatch.setattr(auth_current_chrome, "BrowserNativeTurnProvider", Provider)

    with pytest.raises(AuthError) as captured:
        adapter.browser_login_current_tab(tmp_path / "auth.json", timeout=1)

    assert "secret-value" not in str(captured.value)
    assert "Current Chrome" in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_current_tab_login_rejects_invalid_timeout_before_bridge(tmp_path, timeout) -> None:
    with pytest.raises(ValueError):
        adapter.browser_login_current_tab(tmp_path / "auth.json", timeout=timeout)


def test_current_chrome_auth_status_does_not_require_sdk_profile(tmp_path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "authSource": "current-chrome-tab",
                "cookies": {
                    "__Secure-next-auth.session-token": "session-token"
                },
                "browserCookies": [
                    {
                        "name": "__Secure-next-auth.session-token",
                        "value": "session-token",
                        "domain": ".chatgpt.com",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status = adapter.get_auth_status(auth_file, profile_dir=tmp_path / "missing-profile")

    assert status.auth_source == "current-chrome-tab"
    assert status.current_chrome_auth is True
    assert status.browser_profile_exists is False


def test_auth_status_cli_reports_current_chrome_provenance(tmp_path, capsys) -> None:
    from chatgpt_web_adapter import cli

    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "authSource": "current-chrome-tab",
                "cookies": {"__Secure-next-auth.session-token": "session"},
            }
        ),
        encoding="utf-8",
    )

    assert cli.main(["auth", "status", "--auth-file", str(auth_file)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["auth_source"] == "current-chrome-tab"
    assert payload["current_chrome_auth"] is True


def test_extension_current_chrome_auth_is_bounded_and_uses_active_new_tab() -> None:
    root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "chatgpt_web_adapter"
        / "browser_native_extension"
    )
    source = (root / "service_worker_current_chrome_auth.js").read_text(encoding="utf-8")
    loader = (root / "service_worker_rich_input_schema7_repair_pr9_2.js").read_text(
        encoding="utf-8"
    )
    base = (root / "service_worker.js").read_text(encoding="utf-8")

    assert 'chrome.tabs.create({ url: CHATGPT_ORIGIN + "/", active: true })' in source
    assert '"Network.getCookies"' in source
    assert "Network.getAllCookies" not in source
    assert "chrome.cookies" not in source
    assert "Login Data" not in source
    assert "User Data" not in source
    assert "Network/Cookies" not in source
    assert "document.cookie" not in source
    assert "MAX_AUTH_COOKIE_COUNT" in source
    assert "MAX_AUTH_PAYLOAD_BYTES" in source
    assert "credentials: 'include'" in source
    assert "current_chrome_auth" in base
    assert 'importScripts("service_worker_current_chrome_auth.js")' in loader


def test_current_chrome_auth_uses_the_shared_browser_authority_lane(tmp_path) -> None:
    from chatgpt_web_adapter.browser_native_host import BrowserNativeBroker

    broker = BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    assert broker.turn_lock.acquire(blocking=False) is True
    try:
        response = broker.handle_local_request(
            {
                "protocol": 1,
                "type": "current_chrome_auth",
                "request_id": "auth-1",
                "token": broker.token,
            }
        )
    finally:
        broker.turn_lock.release()

    assert response["ok"] is False
    assert response["error"] == "BROWSER_NATIVE_BRIDGE_BUSY"


def test_provider_sends_one_bounded_current_chrome_auth_operation(tmp_path, monkeypatch) -> None:
    from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider

    provider = BrowserNativeTurnProvider(state_dir=tmp_path)
    captured = {}

    def rpc(payload, *, timeout, on_event=None):
        captured.update(payload)
        captured["rpc_timeout"] = timeout
        return {
            "protocol": 1,
            "type": "current_chrome_auth_result",
            "request_id": payload["request_id"],
            "ok": True,
        }

    monkeypatch.setattr(provider, "_rpc", rpc)
    response = provider.capture_current_chrome_auth(timeout=12)

    assert captured["type"] == "current_chrome_auth"
    assert captured["timeoutMs"] == 12_000
    assert captured["rpc_timeout"] == 17
    assert response["ok"] is True
