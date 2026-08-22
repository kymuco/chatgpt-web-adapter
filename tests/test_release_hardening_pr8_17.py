from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from tools import installed_wheel_smoke, release_gate


VERSION = "0.2.0"


def _root(tmp_path: Path, *, changelog: str = "# Changelog\n\n## Unreleased\n") -> Path:
    root = tmp_path / "repo"
    extension = root / "src" / "chatgpt_web_adapter" / "browser_native_extension"
    extension.mkdir(parents=True)
    (extension / "manifest.json").write_text("{}\n", encoding="utf-8")
    (extension / "service_worker.js").write_text("// worker\n", encoding="utf-8")
    (extension / "extra.js").write_text("// extra\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"chatgpt-web-adapter\"\nversion = \"0.2.0\"\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return root


def _entry_points_text(*, broken: bool = False) -> str:
    target = "chatgpt_web_adapter.cli:main" if broken else "chatgpt_web_adapter.cli_v02:main"
    return (
        "[console_scripts]\n"
        f"cwa = {target}\n"
        f"chatgpt-web-adapter = {target}\n"
        "chatgpt-web-adapter-native-host = chatgpt_web_adapter.browser_native_host:main\n"
    )


def _write_dist(root: Path, *, broken_entry_points: bool = False, omit_extra_js: bool = False) -> Path:
    dist = root / "dist"
    dist.mkdir()
    wheel = dist / f"chatgpt_web_adapter-{VERSION}-py3-none-any.whl"
    dist_info = f"chatgpt_web_adapter-{VERSION}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{dist_info}/METADATA", f"Name: chatgpt-web-adapter\nVersion: {VERSION}\n")
        archive.writestr(f"{dist_info}/entry_points.txt", _entry_points_text(broken=broken_entry_points))
        for required in release_gate.REQUIRED_WHEEL_FILES:
            archive.writestr(required, "x\n")
        if not omit_extra_js:
            archive.writestr("chatgpt_web_adapter/browser_native_extension/extra.js", "x\n")
    sdist = dist / f"chatgpt_web_adapter-{VERSION}.tar.gz"
    root_name = f"chatgpt_web_adapter-{VERSION}"
    with tarfile.open(sdist, "w:gz") as archive:
        for suffix in release_gate.REQUIRED_SDIST_SUFFIXES:
            info = tarfile.TarInfo(root_name + suffix)
            payload = b"x\n"
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return dist


def test_repository_package_version_is_staged_for_0_2() -> None:
    repo = Path(__file__).resolve().parents[1]
    assert release_gate.project_version(repo / "pyproject.toml") == VERSION


def test_candidate_gate_allows_changelog_finalization_to_remain_separate(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = release_gate.run_release_gate(root=root)
    assert report["ok"] is True
    assert report["version"] == VERSION
    assert report["tag"] is None
    assert report["changelog_release_date"] is None


def test_tagged_gate_requires_dated_changelog(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(release_gate.ReleaseGateError, match="CHANGELOG"):
        release_gate.run_release_gate(root=root, tag="v0.2.0")


def test_tagged_gate_requires_exact_version_match(tmp_path: Path) -> None:
    root = _root(tmp_path, changelog="# Changelog\n\n## 0.2.0 - 2026-08-22\n")
    with pytest.raises(release_gate.ReleaseGateError, match="tag/version mismatch"):
        release_gate.run_release_gate(root=root, tag="v0.2.1")
    report = release_gate.run_release_gate(root=root, tag="refs/tags/v0.2.0")
    assert report["tag"] == VERSION
    assert report["changelog_release_date"] == "2026-08-22"


def test_installed_smoke_normalizes_release_tag_versions() -> None:
    assert installed_wheel_smoke.normalize_expected_version("0.2.0") == VERSION
    assert installed_wheel_smoke.normalize_expected_version("v0.2.0") == VERSION
    assert installed_wheel_smoke.normalize_expected_version("refs/tags/v0.2.0") == VERSION


def test_release_gate_accepts_complete_wheel_and_sdist(tmp_path: Path) -> None:
    root = _root(tmp_path)
    dist = _write_dist(root)
    report = release_gate.run_release_gate(root=root, dist_dir=dist)
    assert report["artifacts"]["wheel"]["filename"].endswith(".whl")
    assert report["artifacts"]["wheel"]["extension_files"] == 3
    assert report["artifacts"]["sdist"]["filename"].endswith(".tar.gz")


def test_release_gate_rejects_omitted_extension_package_data(tmp_path: Path) -> None:
    root = _root(tmp_path)
    dist = _write_dist(root, omit_extra_js=True)
    with pytest.raises(release_gate.ReleaseGateError, match="omitted packaged browser extension"):
        release_gate.run_release_gate(root=root, dist_dir=dist)


def test_release_gate_rejects_console_entrypoint_drift(tmp_path: Path) -> None:
    root = _root(tmp_path)
    dist = _write_dist(root, broken_entry_points=True)
    with pytest.raises(release_gate.ReleaseGateError, match="console entry points mismatch"):
        release_gate.run_release_gate(root=root, dist_dir=dist)


def test_release_gate_rejects_ambiguous_distribution_set(tmp_path: Path) -> None:
    root = _root(tmp_path)
    dist = _write_dist(root)
    (dist / "extra.whl").write_bytes(b"not-a-wheel")
    with pytest.raises(release_gate.ReleaseGateError, match="exactly one wheel"):
        release_gate.run_release_gate(root=root, dist_dir=dist)


def test_pyproject_freezes_console_scripts_and_extension_package_data() -> None:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.2.0"' in text
    assert 'cwa = "chatgpt_web_adapter.cli_v02:main"' in text
    assert 'chatgpt-web-adapter = "chatgpt_web_adapter.cli_v02:main"' in text
    assert 'chatgpt-web-adapter-native-host = "chatgpt_web_adapter.browser_native_host:main"' in text
    assert '"browser_native_extension/*.json"' in text
    assert '"browser_native_extension/*.js"' in text


def test_ci_builds_once_then_smokes_exact_wheel_on_linux_and_windows() -> None:
    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python tools/release_gate.py --dist-dir dist" in text
    assert "actions/upload-artifact@v4" in text
    assert "actions/download-artifact@v4" in text
    assert "installed-wheel-smoke:" in text
    assert "ubuntu-latest" in text and "windows-latest" in text
    assert '"3.10"' in text and '"3.14"' in text
    assert "python tools/installed_wheel_smoke.py --wheel-dir dist --expected-version 0.2.0" in text


def test_publish_workflow_gates_tag_and_exact_wheel_before_upload() -> None:
    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    tag_gate = text.index("python tools/release_gate.py")
    wheel_smoke = text.index("python tools/installed_wheel_smoke.py")
    publish = text.index("pypa/gh-action-pypi-publish@release/v1")
    assert "github.event.release.tag_name" in text
    assert tag_gate < wheel_smoke < publish


def test_readme_and_release_checklist_present_0_2_user_and_release_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    checklist = (root / "docs" / "release_checklist.md").read_text(encoding="utf-8")
    for command in ("cwa doctor", "cwa status", "cwa capabilities", "cwa send", "cwa messages", "cwa snapshot", "cwa export"):
        assert command in readme
    assert "GitHub tag version == pyproject package version == dated CHANGELOG release heading" in readme
    assert "installed-wheel smoke" in checklist
    assert "Post-publish verification" in checklist
