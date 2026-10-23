from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 test dependency via pytest
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_repository_entrypoints_exist() -> None:
    for path in (
        "README.md",
        "STATUS.md",
        "ROADMAP.md",
        "USAGE.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/README.md",
        "docs/architecture.md",
        "docs/providers.md",
        "docs/browser_owned.md",
        "docs/quickstart.md",
        "docs/capabilities.md",
        "docs/agent_integration.md",
        "docs/adding_capability.md",
        "QWEN.md",
        "QWEN.ru.md",
        "docs/qwen.md",
        "llms.txt",
    ):
        assert (ROOT / path).is_file(), path


def test_readme_points_to_current_status_providers_and_conservative_boundaries() -> (
    None
):
    text = _read("README.md")

    assert "[Documentation](docs/README.md)" in text
    assert "[Status](STATUS.md)" in text
    assert "[Providers](docs/providers.md)" in text
    assert "v0.3.0" in text
    assert "ChatGPT" in text
    assert "DeepSeek Web" in text
    assert "Gemini Web" in text
    assert "tools_connectors = UNKNOWN" in text

    # PR14.0's governed generated-file handoff superseded the historical
    # PR10.1 blanket unsupported status; observation alone is not authority.
    assert "handoff_generated_artifact(...)" in text
    assert "file_id" in text
    assert "no implicit overwrite" in text
    assert "does not download arbitrary" in text


def test_readme_architecture_map_distinguishes_product_lanes() -> None:
    readme = _read("README.md")
    section = readme.split("## What CWA is\n", 1)[1].split(
        "## Capability matrix (current `main`)\n", 1
    )[0]
    capability_section = readme.split("## Capability matrix (current `main`)\n", 1)[1].split(
        "## Release vs current `main`\n", 1
    )[0]
    diagram = capability_section.split("```mermaid\n", 1)[1].split("\n```", 1)[0]

    for expected in (
        "Local app / agent / CLI",
        "CWA: provider-specific integrations",
        "ChatGPT browser-owned",
        "production/default",
        "ChatGPT direct HTTP",
        "experimental",
        "Qwen isolated SDK",
        "browser / HTTP",
        "DeepSeek / Gemini Web",
        "Translate / Notebook",
        "experimental non-chat",
    ):
        assert expected in diagram, expected

    for expected in (
        "ProductProviderBoundary",
        "is **not** an execution router",
        "not a universal provider selector",
        "a separate extension and Native Messaging",
    ):
        assert expected in section, expected

    assert "[full capability map](docs/capabilities.md)" in readme
    assert "Temporary Chat send" in capability_section
    assert "Download generated file + verify bytes" in capability_section


def test_qwen_reference_guide_matches_isolated_experimental_sdk() -> None:
    guide = _read("docs/qwen.md")
    quickstart = _read("QWEN.md")
    quickstart_ru = _read("QWEN.ru.md")
    index = _read("docs/README.md")
    readme = _read("README.md")

    for example in (
        "python -m chatgpt_web_adapter.qwen_native",
        "python .\\qwen_sdk.py --stream network",
        "--auto-confirm-age",
        "--foreground-tab",
        "--chat",
        "/retry",
        'QwenClient(transport="browser")',
        "client.retry(conversation=chat)",
        "on_token=lambda fragment:",
        "client.import_browser_auth()",
        'QwenClient(transport="http")',
    ):
        assert example in guide, example

    assert "com.kymuco.qwen_web_adapter" in guide
    assert "com.kymuco.chatgpt_web_adapter" in guide
    assert "not live-proven" in guide
    assert "Never automatically resend" in guide
    assert "[Qwen SDK](docs/qwen.md)" in readme
    assert "qwen.md" in index
    assert "[Qwen (EN)](QWEN.md)" in readme
    assert "../QWEN.md" in index
    assert "[Qwen-only quickstart](../QWEN.md)" in guide
    assert "python .\\qwen_sdk.py --stream network" in quickstart
    assert "python -m chatgpt_web_adapter.qwen_native" in quickstart
    assert "--extension-id YOUR_QWEN_EXTENSION_ID" in quickstart
    assert "No ChatGPT authentication" in quickstart
    assert "[Русский](QWEN.ru.md)" in quickstart
    assert "[English](QWEN.md)" in quickstart_ru
    assert "[Qwen (RU)](QWEN.ru.md)" in readme
    assert "[Русская инструкция](QWEN.ru.md)" in readme
    assert "../QWEN.ru.md" in index
    for command in (
        "git clone https://github.com/kymuco/chatgpt-web-adapter.git",
        "python -m pip install -e .",
        "python -m chatgpt_web_adapter.qwen_native",
        "--extension-id YOUR_QWEN_EXTENSION_ID",
        "python .\\qwen_sdk.py --stream network",
        "--chat YOUR_CHAT_UUID --stream network",
        "--auto-confirm-age --birth-year YOUR_BIRTH_YEAR",
        "--foreground-tab --stream network",
        'QwenClient(transport="browser")',
        "conversation=first.conversation",
    ):
        assert command in quickstart, command
        assert command in quickstart_ru, command

    for limit in (
        "com.kymuco.qwen_web_adapter",
        "com.kymuco.chatgpt_web_adapter",
        "/retry",
        "transport http",
    ):
        assert limit in quickstart, limit
        assert limit in quickstart_ru, limit


def test_status_distinguishes_release_from_unreleased_main_and_provider_tiers() -> None:
    text = _read("STATUS.md")

    assert "latest public release   v0.3.0" in text
    assert "current main            post-0.3 development" in text
    assert "PR15 provider architecture frozen" in text
    assert "ChatGPT               PRODUCTION / default conversational runtime" in text
    assert "DeepSeek Web          EXPERIMENTAL conversational runtime" in text
    assert "Gemini Web            EXPERIMENTAL conversational runtime" in text
    assert (
        "Google Translate Web  EXPERIMENTAL non-chat translate_text capability" in text
    )
    normalized = " ".join(text.split())
    assert "The newest published package remains `v0.3.0`" in normalized
    assert "direct ChatGPT HTTP" in normalized
    assert "CAPTURED_UNADMITTED" in text
    assert "PR16  public positioning/documentation alignment" in text


def test_roadmap_is_current_and_post_pr15_consumer_driven() -> None:
    text = _read("ROADMAP.md")

    assert "_Last updated:" in text
    assert "## Release readiness work" in text
    assert "exact built-wheel" in text
    assert "### PR15 — architecture reset and provider proof" in text
    assert "ProductProviderBoundary schema 2" in text
    assert "### PR16.1 — current documentation refresh" in text
    assert "consumer-driven" in text.lower()
    assert "drift-driven" in text.lower()
    assert "Future naming is a separate product decision" in text
    assert "0.4.0" in text


def test_usage_is_runtime_first_and_provider_aware_not_legacy_curl_first() -> None:
    text = _read("USAGE.md")

    assert "ChatGPTProductRuntime" in text
    assert "assemble_product_runtime" in text
    assert "send_text_observed" in text
    assert "media=" in text
    assert "DeepSeekWebRuntime" in text
    assert "GeminiWebRuntime" in text
    assert "Compatibility:" in text
    assert "ChatGPTWebClient" in text
    assert "Detailed usage guide for the dependency-free Python SDK" not in text
    assert "CLI only manages auth" not in text


def test_architecture_covers_provider_boundary_planes_and_artifact_boundary() -> None:
    text = _read("docs/architecture.md")

    assert "## 2. Frozen provider-neutral contract" in text
    assert "## 5. Canonical observation is conditional, not universal" in text
    assert "## 6. Product mutation" in text
    assert "## 7. Write ambiguity and retry authority" in text
    assert "## 13. Generated artifacts" in text
    assert "browser-owned" in text
    assert "browserless-request" in text
    assert "ProductProviderBoundary" in text
    normalized = " ".join(text.split())
    assert "It is not a request router" in normalized
    assert (
        "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY" in text
    )


def test_docs_map_distinguishes_current_docs_from_historical_evidence() -> None:
    text = _read("docs/README.md")

    assert "current product/runtime guidance" in text
    assert "historical engineering evidence" in text
    assert "Do not treat every PR-numbered document" in text
    assert "providers.md" in text
    assert "browser_owned.md" in text
    assert "generated_artifact_handoff_pr10_1.md" in text


def test_unreleased_changelog_records_post_0_3_milestones() -> None:
    text = _read("CHANGELOG.md")
    unreleased = text.split("## Unreleased", 1)[1].split("## 0.3.0", 1)[0]

    assert "connectors / required actions" in unreleased
    assert "generated artifacts" in unreleased
    assert (
        "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY"
        in unreleased
    )
    assert "docs/public readiness" in unreleased


def test_project_metadata_points_to_current_repository_docs() -> None:
    data = tomllib.loads(_read("pyproject.toml"))
    project = data["project"]
    urls = project["urls"]

    assert project["version"] == "0.3.0"
    assert project["description"] == (
        "Local Python SDK and CLI bridge for authenticated consumer AI web products "
        "and hosted capabilities."
    )
    assert urls["Documentation"].endswith("/blob/main/docs/README.md")
    assert urls["Roadmap"].endswith("/blob/main/ROADMAP.md")
    assert urls["Security"].endswith("/blob/main/SECURITY.md")
    assert urls["Releases"].endswith("/releases")


def test_github_community_templates_exist() -> None:
    for path in (
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/capability_proposal.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
    ):
        assert (ROOT / path).is_file(), path


def test_post_pr17_2_checkpoint_is_bounded_to_source_and_proven_evidence() -> None:
    status = _read("STATUS.md")
    roadmap = _read("ROADMAP.md")
    readme = _read("README.md")
    checkpoint = _read("docs/engineering/pr17_2_canonical_product_checkpoint.md")

    # The current status may advance; PR17.2 is a retained historical checkpoint.
    assert "_Last updated:" in status
    assert "PR17.1 and PR17.2 fixed" in status
    assert "Historical canonical `main` baseline after PR17.2" in status
    assert "CONVERSATION_LOCAL_DURABLE" in status
    assert "LAST_SELECTED_MODE_OBSERVED" in status
    assert "TURN_REQUIREMENT" in status
    assert "model preservation remains `UNKNOWN`" in status
    assert "### PR17.1-17.2" in roadmap
    assert "v0.3.0" in readme
    assert "PR17.2 checkpoint" in readme
    assert "main@02b56911ae132d91d35d8bb87511141351968f80" in checkpoint
    assert "CI #1945" in checkpoint
    assert "24,033-character" in checkpoint
    assert "no tab/window foreground activation" in checkpoint
    assert "model_preservation       = UNKNOWN" in checkpoint
    assert "scope_is_write_authority = false" in checkpoint
    assert "No public Video generation API" in status
