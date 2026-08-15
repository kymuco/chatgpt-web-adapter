from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.non_tab_product_execution_feasibility import (
    base_non_tab_feasibility_report,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "non_tab_product_execution_feasibility.py"
)


def test_sources_are_primary_chrome_documentation() -> None:
    sources = base_non_tab_feasibility_report()["sources"]
    assert {row["id"] for row in sources} == {"C0", "C1", "C2", "C3"}
    for row in sources:
        assert row["source"].startswith("https://developer.chrome.com/")


def test_no_candidate_is_promoted_by_credential_or_protection_emulation() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    for forbidden in (
        "chrome.cookies.get",
        "chrome.cookies.set",
        "document.cookie",
        "network.getresponsebody",
        "turnstile_token",
        "proof_token",
        "sentinel",
    ):
        assert forbidden not in source


def test_feasibility_module_does_not_perform_product_write_or_browser_creation() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    assert ".send_text(" not in source
    assert "chrome.tabs.create" not in source
    assert "chrome.offscreen.createdocument" not in source
    assert "target.createtarget" not in source
