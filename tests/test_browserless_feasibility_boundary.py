from __future__ import annotations

from pathlib import Path


def test_operator_probe_is_strictly_read_only() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "examples" / "browserless_feasibility.py").read_text(encoding="utf-8")

    assert "auto_refresh_auth=False" in source
    assert "auto_login=False" in source
    assert "auto_sentinel=False" in source
    assert "run_browserless_read_probe" in source

    forbidden = (
        ".send(",
        "send_browser_native",
        "BrowserNativeTurnProvider",
        ".warmup(",
        "chat-requirements",
        "proof_token",
    )
    for marker in forbidden:
        assert marker not in source
