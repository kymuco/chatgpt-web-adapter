from __future__ import annotations

import pytest

from chatgpt_web_adapter import product_rich_input_composer_diagnostic_pr9_2 as composer


class _FakeComposerProvider:
    requests: list[tuple[dict[str, object], float]] = []
    outcome: str = "ok"

    def _rpc(self, payload: dict[str, object], *, timeout: float):
        type(self).requests.append((payload, timeout))
        if type(self).outcome == "deadline":
            return {
                "request_id": payload["request_id"],
                "ok": False,
                "error": "PR9_2_TOTAL_TURN_TIMEOUT:SCHEMA24_DIAGNOSTIC_RUNTIME_TAB",
            }
        return {
            "request_id": payload["request_id"],
            "ok": True,
            "diagnosticOnly": True,
            "writePerformed": False,
            "attachmentStagingPerformed": False,
            "protectedSubmitAttempted": False,
            "richInputSchemaVersion": 24,
            "productionCleanProof": {"allPollsClean": True},
            "evidence": {"officialComposerMounted": True},
        }


def test_composer_diagnostic_reserves_three_seconds_for_bridge_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeComposerProvider.requests = []
    _FakeComposerProvider.outcome = "ok"
    monkeypatch.setattr(
        composer, "ProductRichInputSchema24LiveProvider", _FakeComposerProvider
    )

    result = composer.run_diagnostic(timeout=15.0)

    assert result["ok"] is True
    assert result["protected_submit_attempted"] is False
    assert len(_FakeComposerProvider.requests) == 1
    payload, outer_timeout = _FakeComposerProvider.requests[0]
    assert outer_timeout == 15.0
    assert payload["timeoutMs"] == 12_000
    assert payload["diagnosePr92ComposerEvidence"] is True
    assert "text" not in payload
    assert "attachmentPaths" not in payload


def test_composer_diagnostic_surfaces_precise_worker_timeout_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeComposerProvider.requests = []
    _FakeComposerProvider.outcome = "deadline"
    monkeypatch.setattr(
        composer, "ProductRichInputSchema24LiveProvider", _FakeComposerProvider
    )

    with pytest.raises(RuntimeError, match="SCHEMA24_DIAGNOSTIC_RUNTIME_TAB"):
        composer.run_diagnostic(timeout=15.0)

    assert len(_FakeComposerProvider.requests) == 1


def test_composer_diagnostic_rejects_timeout_without_response_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        composer,
        "ProductRichInputSchema24LiveProvider",
        lambda: pytest.fail("Should reject before initializing provider"),
    )

    with pytest.raises(ValueError, match="bridge response margin"):
        composer.run_diagnostic(timeout=4.0)
