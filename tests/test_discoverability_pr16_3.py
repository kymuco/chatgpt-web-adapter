from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_has_beginner_agent_and_capability_entrypoints() -> None:
    text = _read("README.md")

    assert "## Start here" in text
    assert "docs/quickstart.md" in text
    assert "docs/capabilities.md" in text
    assert "docs/agent_integration.md" in text
    assert "docs/adding_capability.md" in text
    assert "Google Translate Web" in text


def test_capability_map_is_discovery_not_runtime_authority() -> None:
    text = _read("docs/capabilities.md")

    assert "not** a runtime authority registry" in text
    assert "ChatGPTProductRuntime" in text
    assert "DeepSeekWebRuntime" in text
    assert "GeminiWebRuntime" in text
    assert "GoogleTranslateWebCapability" in text
    assert "PAGE_DOM_STABLE_TRANSLATION" in text
    assert "One proof is not enough" in text


def test_agent_guide_does_not_claim_mcp_is_shipped() -> None:
    text = _read("docs/agent_integration.md")

    assert "local assistant / coding agent / swarm" in text
    assert "A dedicated MCP adapter is **not shipped yet**" in text
    assert "reconciliation-required" in text
    assert "filesystem/Git/workspace authority" in text


def test_llms_txt_exposes_current_project_surface() -> None:
    text = _read("llms.txt")

    assert text.startswith("# CWA — chatgpt-web-adapter")
    assert "Quickstart" in text
    assert "capability map" in text.lower()
    assert "Agent tool-wrapper guide" in text
    assert "Google Translate Web" in text
    assert (
        "does **not** ship a general provider router or a dedicated MCP server" in text
    )
    assert "`BrowserlessHTTPClient`" in text
    assert "defaults to Direct HTTP" in text
    assert "browser-owned" in text
    assert "legacy runtime defaults" in text


def test_capability_contribution_path_is_evidence_driven() -> None:
    guide = _read("docs/adding_capability.md")
    template = _read(".github/ISSUE_TEMPLATE/capability_proposal.yml")

    assert "commitment boundary" in guide
    assert "automatic retry forbidden" in guide
    assert "temporary live" in guide
    assert "Smallest useful operation" in template
    assert "Official API relationship" in template
    assert "Result identity and finality" in template


def test_google_translate_has_discoverable_example() -> None:
    text = _read("examples/google_translate.py")

    assert "GoogleTranslateWebCapability" in text
    assert "translate_text(" in text
    assert 'target_language="es"' in text


def test_agent_instructions_follow_primary_http_contract_and_preserve_authority() -> (
    None
):
    agent = _read("AGENTS.md")
    guide = _read("docs/agent_integration.md")
    primary = _read("examples/direct_http_send.py")

    assert "BrowserlessHTTPClient" in agent
    assert "v0.4.1" in agent
    assert "legacy runtime" in agent
    assert "No automatic replay" in agent
    assert "No implicit fallback" in agent
    assert "A dedicated MCP adapter is **not shipped yet**" in guide
    assert "BrowserlessHTTPClient" in primary
    assert "client.send(args.prompt)" in primary
