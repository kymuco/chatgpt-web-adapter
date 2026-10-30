"""Canonical GET degrades its hint after curl 28, without write retries."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from chatgpt_web_adapter.conversation_read_v2 import _read_current_page
from chatgpt_web_adapter.exceptions import RequestError


def _error(exit_code: int, status_code: int = 200) -> RequestError:
    return RequestError(
        f"curl failed: exit_code={exit_code}; http_status={status_code}",
        request_stage="transport_timeout" if exit_code == 28 else "transport",
        status_code=status_code,
    )


class _Client:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def _json_request(self, method, url, payload, headers):
        assert method == "GET"
        assert payload is None
        assert headers == {"accept": "application/json"}
        self.calls.append(url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _read(client):
    return _read_current_page(
        client,
        current_base_url="https://chatgpt.com/backend-api/conversations",
        conversation_id="conversation-1",
        headers={"accept": "application/json"},
    )


def _hints(client):
    return [
        int(parse_qs(urlparse(url).query)["num_turns"][0])
        for url in client.calls
    ]


def test_curl_timeout_downshifts_and_accepts_complete_get():
    payload = {"messages": [], "current_node": None}
    client = _Client([_error(28), (200, payload)])
    assert _read(client) == (200, payload)
    assert _hints(client) == [20, 10]


def test_three_curl_timeouts_fail_closed_with_original_transport_error():
    failures = [_error(28), _error(28), _error(28)]
    client = _Client(failures)
    with pytest.raises(RequestError) as caught:
        _read(client)
    assert caught.value is failures[-1]
    assert caught.value.request_stage == "transport_timeout"
    assert _hints(client) == [20, 10, 5]


@pytest.mark.parametrize("exit_code", [18, 56])
def test_non_timeout_transfer_failure_does_not_retry(exit_code):
    failure = _error(exit_code)
    client = _Client([failure])
    with pytest.raises(RequestError) as caught:
        _read(client)
    assert caught.value is failure
    assert _hints(client) == [20]


def test_successful_first_get_is_never_retried():
    payload = {"messages": []}
    client = _Client([(200, payload)])
    assert _read(client) == (200, payload)
    assert _hints(client) == [20]


def test_explicit_http_timeout_still_downshifts_without_transport_exception():
    payload = {"messages": []}
    client = _Client([(504, {}), (200, payload)])
    assert _read(client) == (200, payload)
    assert _hints(client) == [20, 10]


def test_transport_timeout_after_http_timeout_preserves_final_exception():
    failure = _error(28)
    client = _Client([(504, {}), _error(28), failure])
    with pytest.raises(RequestError) as caught:
        _read(client)
    assert caught.value is failure
    assert _hints(client) == [20, 10, 5]


def test_timeout_does_not_retry_post_or_finalize():
    # This helper is only a GET reader. Its mock rejects POST, so it has no
    # code path to Sentinel finalize, a conversation write or an upload.
    client = _Client([_error(28), (200, {"messages": []})])
    _read(client)
    assert len(client.calls) == 2
    assert all("/backend-api/conversations/" in url for url in client.calls)
