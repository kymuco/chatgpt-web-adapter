from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_authentication_and_troubleshooting_guides_preserve_session_and_diagnostic_flow() -> (
    None
):
    authentication = _read("docs/authentication.md")
    troubleshooting = _read("docs/troubleshooting.md")

    assert "chatgpt-web-adapter auth login" in authentication
    assert "browserCookies" in authentication
    assert "auto_login=True" in authentication
    assert "auto_sentinel=True" in authentication
    assert "sentinel_headless=True" in authentication
    assert "Headless is not browserless" in authentication
    assert "chatgpt-web-adapter auth status" in troubleshooting
    assert "provider.last_diagnostics" in troubleshooting
    assert "Raw HAR" in troubleshooting
    assert "can still contain secrets" in troubleshooting


def test_primary_usage_positioning_is_provider_aware_and_runtime_first() -> None:
    readme = _read("README.md")
    usage = _read("USAGE.md")
    architecture = _read("docs/architecture.md")
    providers = _read("docs/providers.md")
    classification = _read("docs/public_surface_pr8_6.md")

    assert "ChatGPTProductRuntime" in readme
    assert "assemble_product_runtime" in readme
    assert "ProductProviderBoundary" in readme
    assert "DeepSeek Web" in readme
    assert "Gemini Web" in readme
    assert "docs/providers.md" in readme
    assert "ChatGPTProductRuntime" in usage
    assert "Compatibility:" in usage
    assert "ChatGPTWebClient" in usage
    assert "ProductWriteTransport" in architecture
    assert "CanonicalConversationClient" in architecture
    assert "metadata and invariant validation" in architecture
    assert "ChatGPT" in providers
    assert "DeepSeek Web" in providers
    assert "Gemini Web" in providers
    assert "ChatGPTWebClient" in classification
    assert "does **not** deprecate" in classification
    assert "RESEARCH_DIAGNOSTIC" in classification


def test_current_usage_guide_keeps_compatibility_without_stale_model_defaults() -> None:
    usage = _read("USAGE.md")

    assert "ChatGPTProductRuntime" in usage
    assert "browser-owned" in usage
    assert "DeepSeekWebRuntime" in usage
    assert "GeminiWebRuntime" in usage
    assert "Compatibility:" in usage
    assert "ChatGPTWebClient" in usage
    assert "Historical compatibility features" in usage
    assert "gpt-5-3-mini" not in usage
    assert "gpt-4o-mini" not in usage
    assert "gpt-5-5-thinking" not in usage


def test_primary_product_example_does_not_enable_sentinel() -> None:
    primary = _read("examples/product_runtime.py")

    assert "assemble_product_runtime" in primary
    assert "auto_sentinel=True" not in primary
    assert "sentinel_headless=True" not in primary


def test_compatibility_write_examples_are_retained_not_rebranded_as_primary() -> None:
    write_examples = [
        "examples/basic_send.py",
        "examples/continue_saved.py",
        "examples/diagnose_latency.py",
        "examples/approve_tools.py",
        "examples/github_auto_approve.py",
        "examples/watch_conversation.py",
    ]

    for path in write_examples:
        text = _read(path)
        assert "auto_sentinel=True" in text, path
        assert "sentinel_headless=True" in text, path

    readme = _read("README.md")
    assert "Primary production example:" in readme
    assert "examples/product_runtime.py" in readme
    assert "Compatibility examples:" in readme
    assert "Research/diagnostic examples:" in readme


def test_raw_payload_docs_do_not_claim_current_product_runtime_support() -> None:
    text = _read("docs/raw_payload.md")

    assert "legacy single-step requirements path" in text
    assert "does not transparently convert" in text
