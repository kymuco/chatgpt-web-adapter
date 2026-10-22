"""Read-only canonical history token refresh, without product write replay."""

from __future__ import annotations

from typing import Any

import pytest

from chatgpt_web_adapter import AuthData, ChatGPTWebClient
from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.conversation_read_v2 import read_conversation_payload_v2
from chatgpt_web_adapter.exceptions import AuthError, RequestError

CURRENT_URL = "https://chatgpt.com/backend-api/conversations"
LEGACY_URL = "https://chatgpt.com/backend-api/conversation/{conversation_id}"


def _message(message_id: str) -> dict[str, Any]:
    return {
        "id": message_id,
        "author": {"role": "assistant"},
        "recipient": "all",
        "content": {"content_type": "text", "parts": [message_id]},
    }


def _page(message_id: str, *, cursor: str | None = None) -> dict[str, Any]:
    return {
        "conversation_id": "conversation-1",
        "current_node": message_id,
        "messages": [_message(message_id)],
        "page_info": {
            "has_previous_page": cursor is not None,
            **({"start_cursor": cursor} if cursor else {}),
        },
    }


TOKEN_EXPIRED = (401, {"error": {"code": "token_expired", "message": "expired"}})


class _Client:
    def __init__(
        self,
        responses: list[tuple[int, Any]],
        *,
        allowed: bool = True,
        persist: bool = True,
        fail_refresh: bool = False,
    ) -> None:
        self.responses = list(responses)
        self.token = "old"
        self._read_auth_refresh_allowed = allowed
        self.persist_browser_auth = persist
        self.fail_refresh = fail_refresh
        self.gets: list[tuple[str, str]] = []
        self.refreshed: list[bool] = []

    def _build_headers(self, extra: dict[str, str]) -> dict[str, str]:
        return {**extra, "authorization": f"Bearer {self.token}"}

    def _json_request(
        self,
        method: str,
        url: str,
        payload: None,
        headers: dict[str, str],
    ) -> tuple[int, Any]:
        assert method == "GET"
        assert payload is None
        self.gets.append((url, headers["authorization"]))
        return self.responses.pop(0)

    def refresh_auth(self, *, persist: bool) -> None:
        self.refreshed.append(persist)
        if self.fail_refresh:
            raise AuthError("session rejected")
        self.token = "new"


def _read(client: _Client, *, full: bool = False) -> dict[str, Any]:
    return read_conversation_payload_v2(
        client,
        "conversation-1",
        current_base_url=CURRENT_URL,
        legacy_url_template=LEGACY_URL,
        include_all_pages=full,
    )


def test_explicit_token_expired_refreshes_and_retries_one_read_only_get() -> None:
    client = _Client([TOKEN_EXPIRED, (200, _page("a1"))])
    result = _read(client)
    assert result["mapping"]["a1"]["message"]["id"] == "a1"
    assert client.refreshed == [True]
    assert len(client.gets) == 2
    assert client.gets[0][0] == client.gets[1][0]
    assert [auth for _, auth in client.gets] == ["Bearer old", "Bearer new"]


def test_refresh_during_pagination_repeats_only_failed_cursor_get() -> None:
    client = _Client(
        [(200, _page("a2", cursor="prior")), TOKEN_EXPIRED, (200, _page("a1"))],
        persist=False,
    )
    result = _read(client, full=True)
    assert list(result["mapping"]) == ["a1", "a2"]
    assert client.refreshed == [False]
    assert len(client.gets) == 3
    assert client.gets[0][0] != client.gets[1][0]
    assert client.gets[1][0] == client.gets[2][0]
    assert "before=prior" in client.gets[1][0]
    assert [auth for _, auth in client.gets] == [
        "Bearer old",
        "Bearer old",
        "Bearer new",
    ]


def test_refresh_is_bounded_to_one_attempt_even_on_second_expired_get() -> None:
    client = _Client([TOKEN_EXPIRED, TOKEN_EXPIRED])
    with pytest.raises(RequestError, match="status=401"):
        _read(client)
    assert client.refreshed == [True]
    assert len(client.gets) == 2


@pytest.mark.parametrize(
    "status,data",
    [
        (401, {"error": {"code": "invalid_token"}}),
        (401, {"detail": {"code": "token_expired"}}),
        (403, {"error": {"code": "token_expired"}}),
        (500, {"error": {"code": "token_expired"}}),
    ],
)
def test_unrelated_auth_failures_are_not_automatically_retried(
    status: int, data: dict[str, Any]
) -> None:
    client = _Client([(status, data)])
    with pytest.raises(RequestError):
        _read(client)
    assert client.gets and len(client.gets) == 1
    assert client.refreshed == []


def test_explicit_auto_refresh_opt_out_is_respected() -> None:
    client = _Client([TOKEN_EXPIRED], allowed=False)
    with pytest.raises(RequestError, match="status=401"):
        _read(client)
    assert client.refreshed == []
    assert len(client.gets) == 1


def test_failed_session_refresh_fails_closed_without_a_second_get() -> None:
    client = _Client([TOKEN_EXPIRED], fail_refresh=True)
    with pytest.raises(AuthError, match="session rejected"):
        _read(client)
    assert client.refreshed == [True]
    assert len(client.gets) == 1


def test_legacy_read_fallback_has_same_one_get_only_refresh_boundary() -> None:
    legacy = {
        "conversation_id": "conversation-1",
        "current_node": "a1",
        "mapping": {
            "a1": {
                "id": "a1",
                "message": _message("a1"),
                "parent": None,
                "children": [],
            }
        },
    }
    client = _Client([(404, {"detail": "missing"}), TOKEN_EXPIRED, (200, legacy)])
    result = _read(client)
    assert result["mapping"]["a1"]["message"]["id"] == "a1"
    assert client.refreshed == [True]
    assert len(client.gets) == 3
    assert client.gets[1][0] == client.gets[2][0]
    assert [auth for _, auth in client.gets] == [
        "Bearer old",
        "Bearer old",
        "Bearer new",
    ]


def test_real_client_constructor_retains_auth_refresh_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chatgpt_web_adapter.auth_refresh.auth_needs_refresh",
        lambda token: False,
    )
    auth = AuthData(
        accessToken="opaque-but-present",
        cookies={CHATGPT_SESSION_COOKIE: "existing-session"},
    )
    disabled = ChatGPTWebClient(
        auth=auth,
        auto_refresh_auth=False,
        curl_bin="curl",
    )
    assert disabled._read_auth_refresh_allowed is False

    enabled = ChatGPTWebClient(
        auth=auth,
        auto_refresh_auth=True,
        curl_bin="curl",
    )
    assert enabled._read_auth_refresh_allowed is True
