import json
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import browserless_diagnostics as diagnostics


def test_connection_probe_keeps_secrets_off_argv_and_out_of_result(monkeypatch):
    client = SimpleNamespace(
        curl_bin="curl",
        _build_headers=lambda: {
            "authorization": "Bearer SECRET",
            "cookie": "session=COOKIE",
            "openai-sentinel-proof-token": "STALE",
        },
    )

    def run(command, **kwargs):
        assert command == ["curl", "--config", "-"]
        assert "SECRET" in kwargs["input"]
        assert "STALE" not in kwargs["input"]
        assert kwargs["input"].count("output = ") == 2
        rows = [
            {
                "http_code": 200,
                "num_connects": n,
                "time_starttransfer": 0.4,
                "arbitrary_secret": "DO_NOT_RETURN",
            }
            for n in (1, 0)
        ]
        return SimpleNamespace(returncode=0, stdout="\n".join(map(json.dumps, rows)))

    monkeypatch.setattr(diagnostics.subprocess, "run", run)
    result = diagnostics.connection_samples(client, samples=2)
    assert [row["connection_reused"] for row in result] == [False, True]
    assert "DO_NOT_RETURN" not in json.dumps(result)


@pytest.mark.parametrize("value", ["x\ny", "x\ry", "x\0y"])
def test_config_rejects_injected_options(value):
    with pytest.raises(ValueError):
        diagnostics._config_string(value)


def test_diagnostics_do_not_confuse_preflight_or_catalogue_with_inference(monkeypatch):
    calls = []

    class Client:
        base_headers = {"x-conduit-token": "STALE"}
        auth = SimpleNamespace(cookies={})

        def _build_headers(self, extra=None):
            return dict(extra or {})

        def _json_request(self, method, url, payload, headers):
            calls.append((method, url, payload))
            if method == "GET":
                return 200, {"models": [{"slug": "new-model", "secret": "HIDDEN"}]}
            return 200, {
                "prepare_token": "SECRET",
                "turnstile": {"required": True, "dx": "HIDDEN"},
                "proofofwork": {"required": True, "seed": "HIDDEN"},
                "so": {"required": True, "collector_dx": "HIDDEN"},
            }

    monkeypatch.setattr(diagnostics, "connection_samples", lambda *a, **k: [])
    report = diagnostics.inspect_client(Client(), samples=1)
    assert report["inference_verified"] is False
    assert report["ttft_seconds"] is None
    assert report["conversation_write_attempts"] == 0
    assert report["sentinel_prepare"]["required"]["turnstile"] is True
    assert len(calls) == 2
    assert calls[-1][-1] == {"p": None}
    assert "SECRET" not in json.dumps(report)
    assert "HIDDEN" not in json.dumps(report)


def test_failed_timing_probe_does_not_echo_stderr(monkeypatch):
    client = SimpleNamespace(curl_bin="curl", _build_headers=lambda: {})
    monkeypatch.setattr(
        diagnostics.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=7, stdout="", stderr="SECRET"),
    )
    with pytest.raises(RuntimeError, match="incomplete data") as error:
        diagnostics.connection_samples(client, samples=1)
    assert "SECRET" not in str(error.value)
