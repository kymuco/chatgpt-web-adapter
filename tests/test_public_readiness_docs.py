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
    assert (
        "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY" in text
    )


def test_status_distinguishes_release_from_unreleased_main_and_provider_tiers() -> None:
    text = _read("STATUS.md")

    assert "latest public release   v0.3.0" in text
    assert "current main            post-0.3 development" in text
    assert "PR15 provider architecture frozen" in text
    assert "ChatGPT       PRODUCTION / default" in text
    assert "DeepSeek Web  EXPERIMENTAL" in text
    assert "Gemini Web    EXPERIMENTAL" in text
    normalized = " ".join(text.split())
    assert (
        "Current `main` contains substantial product/runtime work newer than the "
        "`v0.3.0` tag"
        in normalized
    )
    assert "PR16  public positioning/documentation alignment" in text


def test_roadmap_is_current_and_post_pr15_consumer_driven() -> None:
    text = _read("ROADMAP.md")

    assert "_Last updated: 2026-09-26_" in text
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
        "Local Python SDK and CLI bridge for an existing ordinary ChatGPT web session."
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
        ".github/ISSUE_TEMPLATE/config.yml",
    ):
        assert (ROOT / path).is_file(), path
