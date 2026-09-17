from __future__ import annotations

import json
import os
from pathlib import Path

import chatgpt_web_adapter.browser_native_install as install_mod
from chatgpt_web_adapter.browser_native_install import (
    EXTENSION_ID,
    _extension_tree_digest,
    _materialize_extension,
    _resolve_host_executable,
    _write_deployment_manifest,
    browser_native_deployment_status,
    browser_native_extension_dir,
    extension_id_from_public_key,
    packaged_browser_native_extension_dir,
)


def test_packaged_extension_identity_and_manifest() -> None:
    assert extension_id_from_public_key() == EXTENSION_ID
    assert EXTENSION_ID == "kjfnkhajljnkbhikmfijcchenlfglaie"
    root = packaged_browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["minimum_chrome_version"] == "118"
    worker = manifest["background"]["service_worker"]
    assert isinstance(worker, str) and worker.endswith(".js")
    assert (root / worker).is_file()
    assert set(manifest["permissions"]) == {
        "debugger",
        "tabs",
        "storage",
        "nativeMessaging",
    }
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]


def test_materialize_extension_copies_exact_tree_to_stable_target(
    tmp_path: Path,
) -> None:
    source = packaged_browser_native_extension_dir()
    target = tmp_path / "browser-native" / "extension"

    digest = _materialize_extension(source, target)

    assert target.is_dir()
    assert (target / "manifest.json").is_file()
    assert digest == _extension_tree_digest(source)
    assert digest == _extension_tree_digest(target)


def test_materialize_extension_replaces_stale_tree(tmp_path: Path) -> None:
    source = packaged_browser_native_extension_dir()
    target = tmp_path / "browser-native" / "extension"
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("stale", encoding="utf-8")

    digest = _materialize_extension(source, target)

    assert not (target / "stale.txt").exists()
    assert digest == _extension_tree_digest(target)


def test_host_resolution_prefers_current_python_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    current = tmp_path / "current"
    other = tmp_path / "other"
    current.mkdir()
    other.mkdir()
    suffix = ".exe" if os.name == "nt" else ""
    python = current / ("python.exe" if os.name == "nt" else "python")
    python.write_text("", encoding="utf-8")
    current_host = current / f"chatgpt-web-adapter-native-host{suffix}"
    current_host.write_text("", encoding="utf-8")
    other_host = other / f"chatgpt-web-adapter-native-host{suffix}"
    other_host.write_text("", encoding="utf-8")

    monkeypatch.setattr(install_mod.sys, "executable", str(python))
    monkeypatch.setattr(install_mod.shutil, "which", lambda _name: str(other_host))

    assert _resolve_host_executable() == current_host.resolve()


def test_deployment_status_binds_package_extension_and_current_host(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    current_host = tmp_path / "chatgpt-web-adapter-native-host"
    current_host.write_text("host", encoding="utf-8")
    monkeypatch.setattr(install_mod, "default_browser_native_state_dir", lambda: state)
    monkeypatch.setattr(
        install_mod,
        "_current_environment_host_executable",
        lambda: current_host.resolve(),
    )
    monkeypatch.setattr(
        install_mod,
        "_package_identity",
        lambda: {
            "package": "chatgpt-web-adapter",
            "package_version": "test-version",
            "source_revision": "abc123",
        },
    )

    target = state / "extension"
    digest = _materialize_extension(packaged_browser_native_extension_dir(), target)
    _write_deployment_manifest(
        extension_id=EXTENSION_ID,
        extension_digest=digest,
        host_executable=current_host,
    )

    status = browser_native_deployment_status()
    assert status["healthy"] is True
    assert status["extension_digest_matches"] is True
    assert status["source_revision_matches"] is True
    assert status["host_matches_current_environment"] is True

    (target / "manifest.json").write_text("{}", encoding="utf-8")
    stale = browser_native_deployment_status()
    assert stale["healthy"] is False
    assert stale["extension_digest_matches"] is False


def test_extension_dir_returns_stable_path_only_for_healthy_deployment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    current_host = tmp_path / "chatgpt-web-adapter-native-host"
    current_host.write_text("host", encoding="utf-8")
    monkeypatch.setattr(install_mod, "default_browser_native_state_dir", lambda: state)
    monkeypatch.setattr(
        install_mod,
        "_current_environment_host_executable",
        lambda: current_host.resolve(),
    )
    monkeypatch.setattr(
        install_mod,
        "_package_identity",
        lambda: {
            "package": "chatgpt-web-adapter",
            "package_version": "test-version",
            "source_revision": "abc123",
        },
    )
    monkeypatch.setattr(
        install_mod,
        "_user_native_manifest_path",
        lambda: state / "native-host.json",
    )

    target = state / "extension"
    digest = _materialize_extension(packaged_browser_native_extension_dir(), target)
    _write_deployment_manifest(
        extension_id=EXTENSION_ID,
        extension_digest=digest,
        host_executable=current_host,
    )

    assert browser_native_extension_dir() == target.resolve()

    (target / "manifest.json").write_text("{}", encoding="utf-8")
    assert browser_native_extension_dir() == target.resolve() / ".deployment-unhealthy"


def test_extension_dir_fails_closed_for_legacy_host_without_stable_install(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    legacy_manifest = state / "native-host.json"
    legacy_manifest.parent.mkdir(parents=True)
    legacy_manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(install_mod, "default_browser_native_state_dir", lambda: state)
    monkeypatch.setattr(
        install_mod,
        "_user_native_manifest_path",
        lambda: legacy_manifest,
    )

    assert browser_native_extension_dir() == (
        state / "extension" / ".deployment-unhealthy"
    ).resolve()


def test_extension_dir_remains_readable_before_first_install(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(install_mod, "default_browser_native_state_dir", lambda: state)
    monkeypatch.setattr(
        install_mod,
        "_user_native_manifest_path",
        lambda: state / "missing-native-host.json",
    )

    root = browser_native_extension_dir()
    assert root == packaged_browser_native_extension_dir()
    assert root.is_dir()
    assert (root / "manifest.json").is_file()
