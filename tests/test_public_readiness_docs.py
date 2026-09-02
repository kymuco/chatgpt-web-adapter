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
    ):
        assert (ROOT / path).is_file(), path


def test_readme_points_to_current_status_and_post_0_3_boundaries() -> None:
    text = _read("README.md")

    assert "[Documentation](docs/README.md)" in text
    assert "[Status](STATUS.md)" in text
    assert "v0.3.0" in text
    assert "PR10.0" in text
    assert "PR10.1" in text
    assert "tools_connectors" in text
    assert (
        "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY"
        in text
    )


def test_status_distinguishes_release_from_unreleased_main() -> None:
    text = _read("STATUS.md")

    assert "latest public release   v0.3.0" in text
    assert "current main            post-0.3 development" in text
    assert "PR10.0 + PR10.1 merged" in text
    assert "Current `main` contains product/runtime work newer than the `v0.3.0` tag" in text
    assert "consumer-driven runtime hardening" in text


def test_roadmap_is_current_and_consumer_driven() -> None:
    text = _read("ROADMAP.md")

    assert "_Last updated: 2026-09-02_" in text
    assert "PR10.0" in text
    assert "PR10.1" in text
    assert "consumer-driven runtime hardening" in text
    assert "0.4.0" in text


def test_usage_is_runtime_first_not_legacy_curl_first() -> None:
    text = _read("USAGE.md")

    assert "ChatGPTProductRuntime" in text
    assert "assemble_product_runtime" in text
    assert "send_text_observed" in text
    assert "media=" in text
    assert "Compatibility: `ChatGPTWebClient`" in text
    assert "Detailed usage guide for the dependency-free Python SDK" not in text
    assert "CLI only manages auth" not in text


def test_architecture_covers_current_planes_and_artifact_boundary() -> None:
    text = _read("docs/architecture.md")

    assert "## 5. Structured Product Observation Plane" in text
    assert "## 6. Generated-Artifact Boundary" in text
    assert "Browser-owned transport — `PRODUCTION`" in text
    assert "Browserless request transport — `EXPERIMENTAL`" in text
    assert (
        "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY"
        in text
    )


def test_docs_map_distinguishes_current_docs_from_historical_evidence() -> None:
    text = _read("docs/README.md")

    assert "current operational/product documentation" in text
    assert "historical PR-specific evidence" in text
    assert "do not rewrite historical evidence" in text.lower()
    assert "generated_artifact_handoff_pr10_1.md" in text


def test_unreleased_changelog_records_post_0_3_milestones() -> None:
    text = _read("CHANGELOG.md")
    unreleased = text.split("## Unreleased", 1)[1].split("## 0.3.0", 1)[0]

    assert "connectors / required actions" in unreleased
    assert "generated artifacts" in unreleased
    assert "ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY" in unreleased
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
