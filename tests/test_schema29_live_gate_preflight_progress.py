from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter.product_rich_input_live_gate_pr9_2 as legacy_gate
import chatgpt_web_adapter.product_rich_input_live_gate_schema29_pr9_2 as gate


def test_preflight_is_one_read_only_support_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_support(self, *, timeout: float):
        calls.append(timeout)
        return {"schema": 29, "supported": True}

    monkeypatch.setattr(
        legacy_gate.ProductRichInputLiveProvider, "rich_input_support", fake_support
    )
    result = gate.run_preflight(timeout=4.0)

    assert calls == [4.0]
    assert result["ok"] is True
    assert result["support_rpc_count"] == 1
    assert result["write_attempts"] == result["write_completions"] == 0
    assert result["automatic_write_retry"] is False


def test_preflight_reports_unsupported_without_live_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        legacy_gate.ProductRichInputLiveProvider,
        "rich_input_support",
        lambda self, *, timeout: {"schema": 28, "supported": True},
    )
    result = gate.run_preflight()
    assert result["ok"] is False
    assert result["write_attempts"] == 0


def test_live_gate_reports_stage_before_first_attempt_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Provider:
        def rich_input_support(self, *, timeout: float):
            return {"schema": 29, "supported": True}

    class Runtime:
        def __init__(self) -> None:
            self.calls = 0

        def send_text_observed(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("SIMULATED_PREWRITE_FAILURE")

    runtime = Runtime()
    monkeypatch.setattr(gate, "ProductRichInputSchema29LiveProvider", Provider)
    monkeypatch.setattr(gate, "ChatGPTWebClient", lambda **kwargs: object())
    monkeypatch.setattr(gate, "assemble_product_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(gate, "_validate_support", lambda support: None)
    monkeypatch.setattr(
        legacy_gate,
        "_write_fixtures",
        lambda root: (Path("image.png"), Path("file.txt"), Path("continuation.txt")),
    )
    progress = []
    with pytest.raises(RuntimeError, match="SIMULATED_PREWRITE_FAILURE"):
        gate.run_live_gate(
            timeout=1.0,
            progress=lambda stage, attempts, completed: progress.append(
                (stage, attempts, completed)
            ),
        )

    assert progress == [
        ("support_chain_started", 0, 0),
        ("support_chain_validated", 0, 0),
        ("image_write_attempt_started", 1, 0),
    ]
    assert runtime.calls == 1


def test_cli_preflight_needs_no_live_write_approval(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        gate,
        "run_preflight",
        lambda *, timeout: {
            "ok": True,
            "supported": True,
            "schema": 29,
            "support_rpc_count": 1,
            "write_attempts": 0,
            "write_completions": 0,
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        ["schema29", "--preflight-only", "--timeout", "7"],
    )
    assert gate.main() == 0
    out = capsys.readouterr()
    assert '"support_rpc_count": 1' in out.out
    assert out.err == ""
