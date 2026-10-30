"""Offline regression for Direct HTTP streaming-POST curl deadline selection.

No curl subprocess, network access, authentication or model send is performed.
"""

from __future__ import annotations

import pytest

from chatgpt_web_adapter.browserless_http import (
    STREAM_POST_LOW_SPEED_LIMIT_BYTES_PER_SECOND,
    STREAM_POST_LOW_SPEED_TIME_SECONDS,
    STREAM_POST_MAX_TIME_SECONDS,
    BrowserlessHTTPClient,
)


def _client(timeout: int = 60) -> BrowserlessHTTPClient:
    # Building curl arguments requires neither auth credentials nor Node.
    client = BrowserlessHTTPClient.__new__(BrowserlessHTTPClient)
    client.curl_bin = "curl"
    client.timeout = timeout
    return client


def _option(command: list[str], flag: str) -> str | None:
    if flag not in command:
        return None
    return command[command.index(flag) + 1]


@pytest.mark.parametrize(
    ("timeout", "expected_max", "expected_stall"),
    [
        (60, 1800, 180),
        (90, 1800, 180),
        (300, 1800, 300),
        (2400, 2400, 2400),
    ],
)
def test_streaming_post_uses_bounded_long_lifetime(
    timeout, expected_max, expected_stall
):
    client = _client(timeout)
    command = client._build_curl_command(
        "POST",
        "https://chatgpt.com/backend-api/f/conversation",
        {"accept": "text/event-stream"},
        "fake-headers.txt",
        "fake-payload.json",
        no_buffer=True,
    )
    assert _option(command, "--connect-timeout") == "10"
    assert _option(command, "--max-time") == str(expected_max)
    assert _option(command, "--speed-limit") == str(
        STREAM_POST_LOW_SPEED_LIMIT_BYTES_PER_SECOND
    )
    assert _option(command, "--speed-time") == str(expected_stall)
    assert _option(command, "--data-binary") == "@fake-payload.json"
    assert command.count("--max-time") == 1
    assert command.count("--speed-time") == 1
    assert command.count("--speed-limit") == 1
    assert "-N" in command
    assert STREAM_POST_MAX_TIME_SECONDS == 1800
    assert STREAM_POST_LOW_SPEED_TIME_SECONDS == 180


@pytest.mark.parametrize(
    ("method", "no_buffer"),
    [
        ("GET", False),
        ("POST", False),
        ("GET", True),
        ("PUT", True),
    ],
)
def test_non_stream_write_or_read_retains_existing_curl_deadline(
    method, no_buffer
):
    client = _client()
    command = client._build_curl_command(
        method,
        "https://chatgpt.com/backend-api/resource",
        {},
        "fake-headers.txt",
        no_buffer=no_buffer,
    )
    assert _option(command, "--max-time") == "60"
    assert _option(command, "--connect-timeout") == "10"
    assert "--speed-time" not in command
    assert "--speed-limit" not in command


def test_streaming_arguments_keep_other_curl_options_unchanged():
    client = _client(60)
    command = client._build_curl_command(
        "POST",
        "https://chatgpt.com/backend-api/f/conversation",
        {"content-type": "application/json"},
        "fake-headers.txt",
        "fake-payload.json",
        no_buffer=True,
        follow_redirects=False,
    )
    assert command.count("-X") == 1
    assert command[command.index("-X") + 1] == "POST"
    assert "-L" not in command
    assert "-D" in command
    assert "fake-headers.txt" in command
    assert "content-type: application/json" in command
    assert "-N" in command


def test_timeout_options_never_trigger_a_second_request():
    # The builder only returns one argv vector. It cannot run curl, retry
    # a POST, access Sentinel, or write to any persistent state.
    client = _client()
    first = client._build_curl_command(
        "POST", "https://chatgpt.com/backend-api/f/conversation",
        {}, "fake-headers.txt", "fake-body.json", no_buffer=True,
    )
    second = client._build_curl_command(
        "POST", "https://chatgpt.com/backend-api/f/conversation",
        {}, "fake-headers.txt", "fake-body.json", no_buffer=True,
    )
    assert first == second
    assert _option(first, "--max-time") != str(client.timeout)
