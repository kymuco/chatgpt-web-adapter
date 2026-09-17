from __future__ import annotations

import json
from pathlib import Path

from chatgpt_web_adapter.browser_native_install import (
    EXTENSION_ID,
    _extension_tree_digest,
    _materialize_extension,
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
    assert set(manifest["permissions"]) == {"debugger", "tabs", "storage", "nativeMessaging"}
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]


def test_materialize_extension_copies_exact_tree_to_stable_target(tmp_path: Path) -> None:
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


def test_extension_dir_remains_readable_before_first_install() -> None:
    root = browser_native_extension_dir()
    assert root.is_dir()
    assert (root / "manifest.json").is_file()
