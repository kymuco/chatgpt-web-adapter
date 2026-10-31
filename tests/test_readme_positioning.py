from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

TAGLINE = "Use your signed-in ChatGPT web session from Python or the terminal."
REQUIRED_WARNING_LINES = [
    "CWA is not an official API client for OpenAI, Google, DeepSeek or Qwen.",
    "ordinary consumer web products",
    "Ambiguous writes are never automatically retried.",
]


def test_readme_starts_with_provider_aware_product_runtime_positioning() -> None:
    text = README.read_text(encoding="utf-8")
    intro = text[:5000]

    assert TAGLINE in intro
    assert "ChatGPT" in intro
    assert "DeepSeek Web" in intro
    assert "Gemini Web" in intro
    assert "Direct HTTP" in intro
    assert "experimental" in intro.lower()
    assert "ProductProviderBoundary" in intro
    boundary_context = intro.split("ProductProviderBoundary", 1)[1][:240].lower()
    assert "not" in boundary_context
    assert "execution router" in boundary_context
    for line in REQUIRED_WARNING_LINES:
        assert line in intro


def test_readme_explains_primary_compatibility_experimental_and_research_tiers() -> (
    None
):
    text = README.read_text(encoding="utf-8")

    assert "## Public surface tiers" in text
    assert "### Primary production" in text
    assert "### Shared support" in text
    assert "### Compatibility" in text
    assert "### Experimental" in text
    assert "### Research / diagnostic" in text
    assert "public_surface_tier" in text


def test_readme_primary_quick_start_uses_direct_http_not_sentinel() -> None:
    text = README.read_text(encoding="utf-8")
    section = text.split("## ChatGPT recommended: Direct HTTP", 1)[1].split(
        "## Capability matrix (current `main`)", 1
    )[0]

    assert "BrowserlessHTTPClient" in section
    assert 'auth_file="auth_data.json"' in section
    assert "client.send(" in section
    assert "auto_sentinel=True" not in section
    assert "sentinel_headless=True" not in section


def test_readme_keeps_compatibility_research_and_history_discoverable() -> None:
    text = README.read_text(encoding="utf-8")

    assert "ChatGPTWebClient" in text
    assert "browserless-request" in text
    assert "docs/raw_payload.md" in text
    assert "docs/rename_compatibility.md" in text
    assert "examples/diagnose_latency.py" in text
    assert "Research/diagnostic examples:" in text


def test_readme_documents_current_runtime_setup_and_provider_docs() -> None:
    text = README.read_text(encoding="utf-8")

    assert "chatgpt-web-adapter browser-native install" in text
    assert "chatgpt-web-adapter browser-native extension-dir" in text
    assert "chatgpt-web-adapter browser-native status" in text
    assert "cwa doctor --json" in text
    assert "docs/providers.md" in text
    assert "docs/browser_owned.md" in text
    assert "docs/authentication.md" in text
    assert "docs/troubleshooting.md" in text
    assert "Python 3.10-3.14" in text
    assert "Future naming is deliberately deferred" in text
