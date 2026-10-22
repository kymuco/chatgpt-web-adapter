from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from chatgpt_web_adapter.browser_auth_sync import sync_browser_auth
from chatgpt_web_adapter.conversation_read_v2 import read_conversation_payload_v2
from chatgpt_web_adapter.exceptions import AuthError

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
globalThis.CDP_PROTOCOL_VERSION = "1.3";
globalThis.BRIDGE_PROTOCOL_VERSION = 1;
globalThis.activeRequestId = null;
globalThis.safePortPost = () => true;
globalThis.chrome = {{
  tabs: {{
    query: async () => {{
      events.push("query");
      return mode === "missing" ? [] : [{{
        id: 42, status: "complete", url: "https://chatgpt.com/"
      }}];
    }},
    create: () => {{ throw new Error("CREATE_FORBIDDEN"); }},
    update: () => {{ throw new Error("NAVIGATION_FORBIDDEN"); }}
  }},
  debugger: {{
    attach: async () => {{ events.push("attach"); }},
    detach: async () => {{ events.push("detach"); }},
    sendCommand: async (_target, command, args) => {{
      events.push(command);
      if (command === "Runtime.evaluate") {{
        if (!args.expression.includes("/api/auth/session")) throw new Error("wrong URL");
        if (mode === "rejected") return {{ result: {{ value: {{
          ok: false, reason: "BROWSER_AUTH_SESSION_HTTP_ERROR"
        }} }} }};
        return {{ result: {{ value: {{
          ok: true, accessToken: "test-token", sessionToken: "test-session",
          expires: "2030-01-01"
        }} }} }};
      }}
      if (command === "Network.getCookies") {{
        return {{ cookies: [{{
          name: "__Secure-next-auth.session-token", value: "test-session",
          domain: ".chatgpt.com", path: "/", secure: true, httpOnly: true
        }}, {{
          name: "unrelated", value: "private",
          domain: ".example.org", path: "/"
        }}] }};
      }}
      throw new Error("UNKNOWN_CDP_COMMAND");
    }}
  }}
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


def test_browser_auth_only_uses_existing_tab_and_scoped_cookies() -> None:
    result = _run_node("ok")
    assert result["ok"] is True
    assert result["scoped"] == ["__Secure-next-auth.session-token"]
    assert result["events"] == [
        "query",
        "attach",
        "Runtime.evaluate",
        "Network.getCookies",
        "detach",
    ]


def test_browser_auth_no_tab_fails_without_creating_or_navigating() -> None:
    result = _run_node("missing")
    assert result["error"] == "BROWSER_AUTH_EXISTING_TAB_REQUIRED"
    assert result["events"] == ["query"]


def test_browser_auth_rejected_session_fails_closed() -> None:
    result = _run_node("rejected")
    assert result["error"] == "BROWSER_AUTH_SESSION_HTTP_ERROR"
    assert result["events"] == ["query", "attach", "Runtime.evaluate", "detach"]
