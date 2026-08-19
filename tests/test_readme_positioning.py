from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

TAGLINE = (
    "Product-runtime adapter for using an existing ordinary ChatGPT web session "
    "from Python, HDE-style local runtimes, and terminal tools."
)
REQUIRED_WARNING_LINES = [
    "Not the official OpenAI API.",
    "Uses an existing ChatGPT web session and ordinary ChatGPT product semantics.",
    "Browser and web-product behavior may change.",
]


def test_readme_starts_with_product_runtime_positioning() -> None:
    text = README.read_text(encoding="utf-8")
    intro = text[:1200]

    assert TAGLINE in intro
    assert "ChatGPTProductRuntime" in intro
    assert "browser-owned" in intro
    assert "ChatGPTWebClient" in intro
    assert "compatibility" in intro.lower()
    for line in REQUIRED_WARNING_LINES:
        assert line in intro


def test_readme_explains_primary_compatibility_experimental_and_research_tiers() -> None:
    text = README.read_text(encoding="utf-8")

    assert "## Public Surface Tiers" in text
    assert "### Primary production" in text
    assert "### Shared support" in text
    assert "### Compatibility" in text
    assert "### Experimental" in text
    assert "### Research / diagnostic" in text
    assert "PUBLIC_SURFACE_CLASSIFICATION" in text
    assert "public_surface_tier" in text


def test_readme_primary_quick_start_uses_product_runtime_not_sentinel() -> None:
    text = README.read_text(encoding="utf-8")
    production_section = text.split("## Production Python Quick Start", 1)[1].split(
        "## Capabilities", 1
    )[0]

    assert "assemble_product_runtime" in production_section
    assert "runtime.capabilities()" in production_section
    assert "send_text_observed" in production_section
    assert "auto_sentinel=True" not in production_section
    assert "sentinel_headless=True" not in production_section


def test_readme_keeps_compatibility_and_research_paths_discoverable() -> None:
    text = README.read_text(encoding="utf-8")

    assert "ChatGPTWebClient" in text
    assert "auto_sentinel=True" in text
    assert "BrowserNativeTurnProvider" in text
    assert "docs/raw_payload.md" in text
    assert "PayloadBuilder" in text
    assert "validate_payload" in text
    assert "send_payload" in text
    assert "docs/rename_compatibility.md" in text
    assert "examples/diagnose_latency.py" in text


def test_readme_documents_current_runtime_setup_and_docs() -> None:
    text = README.read_text(encoding="utf-8")

    assert "chatgpt-web-adapter browser-native install" in text
    assert "chatgpt-web-adapter browser-native extension-dir" in text
    assert "chatgpt-web-adapter browser-native status" in text
    assert "chatgpt-web-adapter runtime status" in text
    assert "chatgpt-web-adapter runtime send" in text
    assert "ROADMAP.md" in text
    assert "docs/public_surface_pr8_6.md" in text
    assert "docs/authentication.md" in text
    assert "docs/troubleshooting.md" in text
    assert "Python 3.10-3.14" in text
