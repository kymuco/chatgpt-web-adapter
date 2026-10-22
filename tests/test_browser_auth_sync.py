from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from chatgpt_web_adapter import ChatGPTWebClient
from chatgpt_web_adapter.auth_store import persist_auth_data
from chatgpt_web_adapter.browser_auth_sync import (
    BrowserAuthSyncResult,
    sync_browser_auth,
)
from chatgpt_web_adapter.conversation_read_v2 import read_conversation_payload_v2
from chatgpt_web_adapter.exceptions import AuthError
from chatgpt_web_adapter.types import AuthData

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_auth_sync.js"
)


class _FakeProvider:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.requests: list[dict] = []

    def _rpc(self, payload: dict, *, timeout: float) -> dict:
        self.requests.append(dict(payload))
        assert timeout <= 25
        if not self.valid:
            return {
                "protocol": 1,
                "type": "auth_sync_result",
                "request_id": payload["request_id"],
                "ok": False,
                "reasonCode": "BROWSER_AUTH_EXISTING_TAB_REQUIRED",
            }
        return {
            "protocol": 1,
            "type": "auth_sync_result",
            "request_id": payload["request_id"],
            "ok": True,
            "session": {
                "accessToken": "new-synthetic-access",
                "sessionToken": "new-synthetic-session",
                "expires": "2030-01-01T00:00:00.000Z",
                "cookies": {
                    "__Secure-next-auth.session-token": "new-synthetic-session",
                    "oai-did": "device-test",
                },
                "browserCookies": [
                    {
                        "name": "__Secure-next-auth.session-token",
                        "value": "new-synthetic-session",
                        "domain": ".chatgpt.com",
                        "path": "/",
                        "secure": True,
                        "http_only": True,
                    },
                    {
                        "name": "oai-did",
                        "value": "device-test",
                        "domain": ".chatgpt.com",
                        "path": "/",
                        "secure": True,
                        "http_only": False,
                    },
                ],
            },
        }


def test_sync_browser_auth_atomically_replaces_credentials_and_preserves_headers(
    tmp_path: Path,
) -> None:
    target = tmp_path / "auth_data.json"
    target.write_text(
        json.dumps(
            {
                "accessToken": "old-access",
                "cookies": {"__Secure-next-auth.session-token.0": "old-chunk"},
                "headers": {"user-agent": "existing-browser"},
                "custom": "retained",
            }
        ),
        encoding="utf-8",
    )
    provider = _FakeProvider()
    result = sync_browser_auth(target, provider=provider)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert result.persisted is True
    assert result.auth.accessToken == "new-synthetic-access"
    assert saved["accessToken"] == "new-synthetic-access"
    assert saved["sessionToken"] == "new-synthetic-session"
    assert saved["cookies"] == {
        "__Secure-next-auth.session-token": "new-synthetic-session",
        "oai-did": "device-test",
    }
    assert saved["custom"] == "retained"
    assert saved["headers"]["user-agent"] == "existing-browser"
    assert provider.requests[0]["type"] == "auth_sync"


def test_browser_auth_requires_explicit_persist_and_no_file_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "auth_data.json"
    result = sync_browser_auth(target, provider=_FakeProvider(), persist=False)
    assert result.persisted is False
    assert result.auth.accessToken == "new-synthetic-access"
    assert not target.exists()


def test_browser_auth_errors_are_reason_only_without_credentials(
    tmp_path: Path,
) -> None:
    target = tmp_path / "auth_data.json"
    with pytest.raises(AuthError, match="BROWSER_AUTH_EXISTING_TAB_REQUIRED"):
        sync_browser_auth(target, provider=_FakeProvider(valid=False))
    assert not target.exists()


class _HistoryReader:
    _read_auth_refresh_allowed = True
    _browser_auth_sync_allowed = True
    persist_browser_auth = True

    def __init__(self) -> None:
        self.token = "old"
        self.calls: list[str] = []
        self.synced: list[bool] = []

    def _build_headers(self, extra: dict) -> dict:
        return {**extra, "authorization": f"Bearer {self.token}"}

    def _json_request(self, method, url, data, headers):
        assert method == "GET"
        assert data is None
        self.calls.append(headers["authorization"])
        if self.token == "old":
            return 401, {"error": {"code": "token_expired"}}
        return 200, {
            "conversation_id": "conversation-1",
            "messages": [{"id": "node-1", "author": {"role": "assistant"}}],
            "page_info": {"has_previous_page": False},
        }

    def sync_browser_auth(self, *, persist: bool) -> None:
        self.synced.append(persist)
        self.token = "new"


def test_canonical_401_automatically_syncs_opted_in_browser_auth() -> None:
    client = _HistoryReader()
    result = read_conversation_payload_v2(
        client,
        "conversation-1",
        current_base_url="https://chatgpt.com/backend-api/conversations",
        legacy_url_template=(
            "https://chatgpt.com/backend-api/conversation/{conversation_id}"
        ),
    )
    assert "node-1" in result["mapping"]
    assert client.synced == [True]
    assert client.calls == ["Bearer old", "Bearer new"]


def _run_node(mode: str) -> dict:
    source = SOURCE.read_text(encoding="utf-8")
    script = f"""
const mode = {json.dumps(mode)};
const events = [];
globalThis.BRIDGE_PROTOCOL_VERSION = 1;
globalThis.activeRequestId = null;
globalThis.safePortPost = () => true;
globalThis.chrome = {{
  tabs: {{
    query: () => {{ throw new Error("TAB_QUERY_FORBIDDEN"); }},
    create: () => {{ throw new Error("TAB_CREATE_FORBIDDEN"); }},
    update: () => {{ throw new Error("TAB_UPDATE_FORBIDDEN"); }}
  }},
  debugger: {{
    attach: () => {{ throw new Error("DEBUGGER_FORBIDDEN"); }},
    sendCommand: () => {{ throw new Error("DEBUGGER_FORBIDDEN"); }}
  }},
  cookies: {{
    getAll: async (options) => {{
      events.push(["COOKIES", options.url]);
      if (mode === "no_cookies_permission") throw new Error("No cookies permission");
      if (mode === "no_session_cookie") return [];
      return [{{
        name: "__Secure-next-auth.session-token", value: "test-session",
        domain: ".chatgpt.com", path: "/", secure: true, httpOnly: true
      }}, {{
        name: "unrelated", value: "private",
        domain: ".example.org", path: "/"
      }}];
    }}
  }}
}};
globalThis.fetch = async (url, options) => {{
  events.push(["FETCH", url, options.method, options.credentials]);
  if (url !== "https://chatgpt.com/api/auth/session") {{
    throw new Error("WRONG_ENDPOINT");
  }}
  if (mode === "rejected") return {{ status: 401 }};
  if (mode === "fetch_exception") throw new Error("network offline");
  return {{
    status: 200,
    json: async () => ({{
      accessToken: "test-token",
      sessionToken: "test-session",
      expires: "2030-01-01"
    }})
  }};
}};
{source}
(async () => {{
  try {{
    const session = await _cwaReadBrowserAuthSession();
    process.stdout.write(JSON.stringify({{
      ok: session.accessToken === "test-token",
      scoped: Object.keys(session.cookies),
      events
    }}));
  }} catch (error) {{
    process.stdout.write(JSON.stringify({{
      error: error.message, events
    }}));
  }}
}})();
"""
    run = subprocess.run(
        ["node", "-e", script],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(run.stdout)


def test_browser_auth_uses_service_worker_only_and_scoped_cookies() -> None:
    result = _run_node("ok")
    assert result["ok"] is True
    assert result["scoped"] == ["__Secure-next-auth.session-token"]
    assert result["events"] == [
        ["FETCH", "https://chatgpt.com/api/auth/session", "GET", "include"],
        ["COOKIES", "https://chatgpt.com/"],
    ]


def test_browser_auth_no_tab_required_even_if_no_tabs_exist() -> None:
    result = _run_node("no_tabs")
    assert result["ok"] is True
    assert len(result["events"]) == 2


def test_browser_auth_rejected_session_fails_closed() -> None:
    result = _run_node("rejected")
    assert result["error"] == "BROWSER_AUTH_SESSION_HTTP_ERROR"
    assert result["events"] == [
        ["FETCH", "https://chatgpt.com/api/auth/session", "GET", "include"]
    ]


def test_browser_auth_cookie_permission_failure_is_specific() -> None:
    result = _run_node("no_cookies_permission")
    assert result["error"] == "BROWSER_AUTH_COOKIE_ACCESS_FAILED"


def test_browser_auth_without_cookie_fails_closed() -> None:
    result = _run_node("no_session_cookie")
    assert result["error"] == "BROWSER_AUTH_SESSION_COOKIE_MISSING"


def test_browser_auth_fetch_failure_fails_closed() -> None:
    result = _run_node("fetch_exception")
    assert result["error"] == "BROWSER_AUTH_SESSION_REQUEST_FAILED"


def test_opted_in_client_recovers_missing_auth_before_startup_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "auth_data.json"
    calls: list[tuple[Path, bool]] = []

    def fake_browser_sync(auth_file, *, persist=True):
        target = Path(auth_file)
        calls.append((target, persist))
        auth = AuthData(
            accessToken="fresh-synthetic-access",
            cookies={"__Secure-next-auth.session-token": "fresh-synthetic-cookie"},
        )
        if persist:
            persist_auth_data(auth, target)
        return BrowserAuthSyncResult(auth=auth, persisted=persist, auth_file=target)

    monkeypatch.setattr(
        "chatgpt_web_adapter.client._sync_browser_auth", fake_browser_sync
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.auth_refresh.refresh_auth_session",
        lambda *_args, **_kwargs: pytest.fail("legacy refresh must not run"),
    )
    client = ChatGPTWebClient(
        auth_file=path,
        auto_browser_auth_sync=True,
        curl_bin="curl",
    )
    assert calls == [(path, True)]
    assert client.auth.accessToken == "fresh-synthetic-access"
    assert client._browser_auth_sync_allowed is True
    assert path.exists()


def test_opted_in_client_does_not_export_when_valid_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "auth_data.json"
    persist_auth_data(
        AuthData(
            accessToken="still-valid-synthetic",
            cookies={"__Secure-next-auth.session-token": "cookie"},
        ),
        path,
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.client._sync_browser_auth",
        lambda *_args, **_kwargs: pytest.fail("browser must not be contacted"),
    )
    client = ChatGPTWebClient(
        auth_file=path,
        auto_browser_auth_sync=True,
        curl_bin="curl",
    )
    assert client.auth.accessToken == "still-valid-synthetic"


def test_opted_in_startup_sync_respects_no_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "auth_data.json"
    auth = AuthData(
        accessToken="transient-synthetic",
        cookies={"__Secure-next-auth.session-token": "transient-cookie"},
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.client._sync_browser_auth",
        lambda target, *, persist: BrowserAuthSyncResult(
            auth=auth, persisted=False, auth_file=Path(target)
        ),
    )
    client = ChatGPTWebClient(
        auth_file=path,
        auto_browser_auth_sync=True,
        persist_refreshed_auth=False,
        curl_bin="curl",
    )
    assert client.auth.accessToken == "transient-synthetic"
    assert not path.exists()


def test_supplied_auth_never_replaced_by_browser_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "chatgpt_web_adapter.client._sync_browser_auth",
        lambda *_args, **_kwargs: pytest.fail("explicit auth must not be replaced"),
    )
    auth = AuthData(
        accessToken="explicit-synthetic",
        cookies={"__Secure-next-auth.session-token": "explicit-cookie"},
    )
    client = ChatGPTWebClient(
        auth=auth,
        auto_browser_auth_sync=True,
        curl_bin="curl",
    )
    assert client.auth is auth
