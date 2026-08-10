from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import chatgpt_web_adapter as adapter


def _response(secret_prefix: str = "secret") -> dict:
    return {
        "persona": "chatgpt-paid",
        "prepare_token": f"{secret_prefix}-prepare-token",
        "turnstile": {
            "required": True,
            "dx": f"{secret_prefix}-turnstile-dx",
        },
        "proofofwork": {
            "required": True,
            "seed": f"{secret_prefix}-pow-seed",
            "difficulty": f"{secret_prefix}-pow-difficulty",
        },
        "so": {
            "required": True,
            "collector_dx": f"{secret_prefix}-collector",
            "snapshot_dx": f"{secret_prefix}-snapshot",
        },
    }


def test_sentinel_prepare_probe_retains_structure_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import chatgpt_web_adapter.sentinel_requirements as sentinel

    derived_p = "secret-derived-p"
    monkeypatch.setattr(
        sentinel.client_mod,
        "_get_requirements_token",
        lambda value: derived_p,
    )

    class TraceClient(adapter.ChatGPTWebClient):
        def __init__(self) -> None:
            self.auth = SimpleNamespace(proof_token=["browser-fingerprint"])
            self.debug_trace_dir = tmp_path
            self.debug_trace_sanitize = False
            self._debug_trace_counter = 0

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        def _json_request(self, method, url, payload, headers):
            assert payload == {"p": derived_p}
            response = _response()
            self._write_debug_trace(
                "http",
                {
                    "request_body": payload,
                    "response_body": response,
                },
            )
            return 200, response

    result = adapter.probe_sentinel_requirements_prepare(TraceClient())

    assert result.status_ok is True
    assert result.observed_shape_matches is True
    assert result.verdict == "TWO_PHASE_SENTINEL_PREPARE_OBSERVED"
    assert result.prepare_token_present is True
    assert result.turnstile_required is True
    assert result.proofofwork_required is True
    assert result.so_required is True
    assert result.response_keys == (
        "persona",
        "prepare_token",
        "proofofwork",
        "so",
        "turnstile",
    )
    assert result.turnstile_keys == ("dx", "required")
    assert result.proofofwork_keys == ("difficulty", "required", "seed")
    assert result.so_keys == ("collector_dx", "required", "snapshot_dx")

    traces = sorted(tmp_path.glob("*.json"))
    assert len(traces) == 1
    rendered = traces[0].read_text(encoding="utf-8")
    for secret in (
        derived_p,
        "secret-prepare-token",
        "secret-turnstile-dx",
        "secret-pow-seed",
        "secret-pow-difficulty",
        "secret-collector",
        "secret-snapshot",
    ):
        assert secret not in rendered

    payload = json.loads(rendered)
    assert payload["p_present"] is True
    assert payload["observed_shape_matches"] is True
    assert payload["raw_request_recorded"] is False
    assert payload["raw_response_recorded"] is False
    assert payload["challenge_values_recorded"] is False
    assert payload["prepare_token_present"] is True


def test_sentinel_prepare_probe_uses_observed_request_shape(monkeypatch) -> None:
    captured = {}

    class Client:
        auth = SimpleNamespace(proof_token=["browser-fingerprint"])
        debug_trace_dir = None

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        @staticmethod
        def _json_request(method, url, payload, headers):
            captured.update(
                method=method,
                url=url,
                payload=payload,
                headers=headers,
            )
            return 200, _response("different")

    import chatgpt_web_adapter.sentinel_requirements as sentinel

    monkeypatch.setattr(
        sentinel.client_mod,
        "_get_requirements_token",
        lambda value: "derived-p",
    )

    result = adapter.probe_sentinel_requirements_prepare(Client())

    assert result.observed_shape_matches is True
    assert result.verdict == "TWO_PHASE_SENTINEL_PREPARE_OBSERVED"
    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/backend-api/sentinel/chat-requirements/prepare"
    )
    assert captured["payload"] == {"p": "derived-p"}
    assert captured["headers"]["x-openai-target-path"].endswith(
        "/sentinel/chat-requirements/prepare"
    )
    assert captured["headers"]["x-openai-target-route"].endswith(
        "/sentinel/chat-requirements/prepare"
    )


def test_sentinel_prepare_verdict_detects_nested_schema_drift() -> None:
    response = _response("drift")
    del response["turnstile"]["dx"]

    class Client:
        auth = SimpleNamespace(proof_token=None)
        debug_trace_dir = None

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        @staticmethod
        def _json_request(method, url, payload, headers):
            return 200, response

    result = adapter.probe_sentinel_requirements_prepare(Client())

    assert result.status_ok is True
    assert result.turnstile_present is True
    assert result.observed_shape_matches is False
    assert result.verdict == "SENTINEL_PREPARE_PARTIAL_SHAPE"


def test_sentinel_prepare_allows_additive_keys_and_nonrequired_challenges() -> None:
    response = _response("additive")
    response["server_extension"] = {"version": 2}
    response["turnstile"]["required"] = False
    response["turnstile"]["extra"] = "ignored"
    response["proofofwork"]["required"] = False
    response["proofofwork"]["extra"] = "ignored"
    response["so"]["required"] = False
    response["so"]["extra"] = "ignored"

    class Client:
        auth = SimpleNamespace(proof_token=None)
        debug_trace_dir = None

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        @staticmethod
        def _json_request(method, url, payload, headers):
            return 200, response

    result = adapter.probe_sentinel_requirements_prepare(Client())

    assert result.status_ok is True
    assert result.turnstile_required is False
    assert result.proofofwork_required is False
    assert result.so_required is False
    assert "server_extension" in result.response_keys
    assert "extra" in result.turnstile_keys
    assert "extra" in result.proofofwork_keys
    assert "extra" in result.so_keys
    assert result.observed_shape_matches is True
    assert result.verdict == "TWO_PHASE_SENTINEL_PREPARE_OBSERVED"


def test_two_phase_finalize_shape_is_public_contract() -> None:
    assert adapter.OBSERVED_FINALIZE_REQUEST_KEYS == (
        "prepare_token",
        "proofofwork",
        "turnstile",
    )
    assert adapter.OBSERVED_FINALIZE_RESPONSE_KEYS == (
        "persona",
        "token",
        "expire_after",
        "expire_at",
    )
    assert "OBSERVED_FINALIZE_REQUEST_KEYS" in adapter.__all__
    assert "OBSERVED_FINALIZE_RESPONSE_KEYS" in adapter.__all__
