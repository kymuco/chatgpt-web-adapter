"""Installed cwa send must use primary Direct HTTP without breaking legacy runtime."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import cli_direct_http
from chatgpt_web_adapter import cli_v02 as cli
from chatgpt_web_adapter.exceptions import RequestError


def _response(text="hello world"):
    return SimpleNamespace(
        text=text,
        title="Test conversation",
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id="message-1",
            finish_reason="stop",
        ),
        request=SimpleNamespace(observed_model=None, temporary=False),
        metrics=SimpleNamespace(backend_status=200),
    )


class FakeHTTP:
    def __init__(self, *, auth_file, timeout):
        self.auth_file = auth_file
        self.timeout = timeout
        self.calls = []

    def send(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        callback = kwargs.get("on_token")
        if callback:
            callback("hello")
            callback(" world")
        return _response()


@pytest.fixture
def fake_http(monkeypatch):
    created = []

    def factory(**kwargs):
        client = FakeHTTP(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(cli_direct_http, "BrowserlessHTTPClient", factory)
    return created


def test_default_send_uses_direct_http_and_requests_gpt6_high(fake_http, capsys):
    assert cli.main(["send", "hello"]) == 0
    assert capsys.readouterr().out == "hello world\n"
    assert len(fake_http) == 1
    assert fake_http[0].calls == [
        (
            "hello",
            {
                "model": "gpt-6",
                "reasoning_effort": "high",
                "conversation": None,
                "temporary": False,
                "media": None,
                "on_token": None,
            },
        )
    ]


@pytest.mark.parametrize(
    ("profile", "model", "effort"),
    [
        ("INSTANT", "gpt-6-instant", None),
        ("medium", "gpt-6", "medium"),
        ("DEEP", "gpt-6", "high"),
    ],
)
def test_profile_mapping_is_explicit(fake_http, capsys, profile, model, effort):
    assert cli.main(["send", "hello", "--profile", profile]) == 0
    assert fake_http[0].calls[0][1]["model"] == model
    assert fake_http[0].calls[0][1]["reasoning_effort"] == effort


def test_streaming_prints_tokens_and_retains_final_text(fake_http, capsys):
    assert cli.main(["send", "hello", "--stream"]) == 0
    assert capsys.readouterr().out == "hello world\n"
    assert len(fake_http[0].calls) == 1


def test_final_only_has_no_intermediate_token_output(fake_http, capsys):
    assert cli.main(["send", "hello", "--stream", "--final-only"]) == 0
    assert capsys.readouterr().out == "hello world\n"
    assert fake_http[0].calls[0][1]["on_token"] is None


def test_json_is_honest_about_unavailable_browser_runtime_provenance(fake_http, capsys):
    assert cli.main(["send", "hello", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["transport"] == "direct-http"
    assert data["conversation_id"] == "conversation-1"
    assert data["message_id"] == "message-1"
    assert data["runtime_observation"] is None
    assert data["provenance"] is None
    assert len(fake_http[0].calls) == 1


def test_continuation_and_files_and_explicit_model(fake_http, tmp_path):
    doc = tmp_path / "attached.md"
    doc.write_text("# Source", encoding="utf-8")
    assert (
        cli.main(
            [
                "send",
                "hello",
                "--conversation",
                "conversation-1",
                "--file",
                str(doc),
                "--model",
                "gpt-6",
            ]
        )
        == 0
    )
    kwargs = fake_http[0].calls[0][1]
    assert kwargs["conversation"] == "conversation-1"
    assert kwargs["media"] == [doc]
    assert kwargs["model"] == "gpt-6"


def test_temporary_is_direct_and_does_not_assume_durable_continuation(fake_http):
    assert cli.main(["send", "hello", "--temporary"]) == 0
    assert fake_http[0].calls[0][1]["temporary"] is True


@pytest.mark.parametrize(
    "options",
    [
        ["--temporary", "--conversation", "conversation-1"],
        ["--timings", "--stream"],
        ["--poll-interval", "2"],
        ["--file", "/file/that/does/not/exist.md"],
    ],
)
def test_invalid_direct_flags_fail_before_constructing_client(fake_http, options):
    assert cli.main(["send", "hello", *options]) != 0
    assert not fake_http


def test_explicit_browser_owned_is_preserved(monkeypatch, fake_http):
    observed = []

    def legacy(args):
        observed.append(args.transport)
        return 0

    monkeypatch.setattr(cli.legacy_cli, "_run_send", legacy)
    assert cli.main(["send", "hello", "--transport", "browser-owned"]) == 0
    assert cli.main(["send", "hello", "--transport", "browserless-request"]) == 0
    assert observed == ["browser-owned", "browserless-request"]
    assert not fake_http


def test_legacy_mode_cannot_silently_ignore_direct_only_files(fake_http):
    assert (
        cli.main(["send", "hello", "--transport", "browser-owned", "--file", "foo.md"])
        != 0
    )
    assert not fake_http


def test_direct_http_timeout_marks_outcome_unknown_and_does_not_retry(
    monkeypatch, capsys
):
    calls = []

    class TimedOut:
        def __init__(self, **kwargs):
            pass

        def send(self, *args, **kwargs):
            calls.append(1)
            raise RequestError(
                "curl failed: exit_code=28; http_status=200",
                status_code=200,
                request_stage="transport_timeout",
            )

    monkeypatch.setattr(cli_direct_http, "BrowserlessHTTPClient", TimedOut)
    result = cli.main(["send", "hello", "--json"])
    payload = json.loads(capsys.readouterr().err)
    assert result == cli.EXIT_RECONCILIATION_REQUIRED
    assert payload["error"]["reconciliation_required"] is True
    assert payload["error"]["write_may_have_been_submitted"] is True
    assert payload["error"]["request_stage"] == "transport_timeout"
    assert payload["error"]["status_code"] == 200
    assert calls == [1]


def test_direct_http_non_timeout_does_not_fabricate_write_admission(
    monkeypatch, capsys
):
    calls = []

    class Rejected:
        def __init__(self, **kwargs):
            pass

        def send(self, *args, **kwargs):
            calls.append(1)
            raise RequestError(
                "request rejected",
                status_code=401,
                request_stage="transport",
            )

    monkeypatch.setattr(cli_direct_http, "BrowserlessHTTPClient", Rejected)
    result = cli.main(["send", "hello", "--json"])
    payload = json.loads(capsys.readouterr().err)
    assert result == cli.EXIT_OPERATION_FAILED
    assert payload["error"]["request_stage"] == "transport"
    assert "reconciliation_required" not in payload["error"]
    assert calls == [1]


def test_text_mode_reports_safe_direct_http_phase_without_signed_url(
    monkeypatch, capsys
):
    calls = []

    class FailedUpload:
        def __init__(self, **kwargs):
            pass

        def send(self, *args, **kwargs):
            calls.append(1)
            raise RequestError(
                "curl failed: exit_code=28; http_status=200",
                status_code=200,
                request_stage="transport_timeout",
                endpoint="file_upload",
            )

    monkeypatch.setattr(cli_direct_http, "BrowserlessHTTPClient", FailedUpload)
    result = cli.main(["send", "hello"])
    output = capsys.readouterr()
    assert result == cli.EXIT_RECONCILIATION_REQUIRED
    assert output.out == ""
    assert "phase: file_upload" in output.err
    assert "inspect canonical conversation history" in output.err
    assert calls == [1]


def test_text_mode_never_echoes_untrusted_phase(monkeypatch, capsys):
    calls = []

    class UnsafePhase:
        def __init__(self, **kwargs):
            pass

        def send(self, *args, **kwargs):
            calls.append(1)
            raise RequestError(
                "request failed",
                request_stage="transport",
                endpoint="https://upload.invalid/private?sig=SECRET",
            )

    monkeypatch.setattr(cli_direct_http, "BrowserlessHTTPClient", UnsafePhase)
    result = cli.main(["send", "hello"])
    output = capsys.readouterr()
    assert result == cli.EXIT_OPERATION_FAILED
    assert "SECRET" not in output.err
    assert "phase:" not in output.err
    assert calls == [1]


@pytest.mark.parametrize(
    ("failure", "expected_phase"),
    [
        (
            RequestError(
                "curl failed: exit_code=18; http_status=200",
                status_code=200,
                request_stage="transport",
                endpoint="file_upload",
            ),
            "file_upload",
        ),
        (
            RequestError(
                "curl failed: curl: (28) Operation timed out",
                request_stage="transport",
            ),
            "conversation_write",
        ),
        (
            RequestError(
                "curl failed: curl: (56) Recv failure",
                request_stage="transport",
            ),
            "conversation_write",
        ),
    ],
)
def test_partial_http_200_and_sse_transport_failure_require_reconciliation(
    monkeypatch, capsys, failure, expected_phase
):
    calls = []

    class StreamInterrupted:
        def __init__(self, **kwargs):
            pass

        def send(self, *args, **kwargs):
            calls.append(1)
            raise failure

    monkeypatch.setattr(
        cli_direct_http, "BrowserlessHTTPClient", StreamInterrupted
    )
    exit_code = cli.main(["send", "hello", "--json"])
    error = json.loads(capsys.readouterr().err)["error"]
    assert exit_code == cli.EXIT_RECONCILIATION_REQUIRED
    assert error["reconciliation_required"] is True
    assert error["write_may_have_been_submitted"] is True
    assert error["endpoint"] == expected_phase
    assert "Recv failure" not in error["message"]
    assert calls == [1]
