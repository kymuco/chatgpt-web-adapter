from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_authentication_and_troubleshooting_guides_cover_current_session_flow() -> None:
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


def test_usage_uses_current_defaults_and_runtime_boundary() -> None:
    usage = _read("USAGE.md")

    assert "gpt-5-3-mini" in usage
    assert "gpt-5-6-thinking" in usage
    assert "Python SDK for using an existing ChatGPT web session" in _read("README.md")
    assert "Current protected writes" in usage
    assert "no auth capture flow" not in usage
    assert "gpt-4o-mini" not in usage
    assert "gpt-5-5-thinking" not in usage


def test_supported_write_examples_enable_headless_sentinel() -> None:
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


def test_raw_payload_docs_do_not_claim_current_sentinel_support() -> None:
    text = _read("docs/raw_payload.md")

    assert "legacy single-step requirements path" in text
    assert "does not transparently convert" in text
