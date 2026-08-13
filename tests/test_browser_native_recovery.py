from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_pr811_recovery_worker_is_packaged() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    recovery = (root / "service_worker_recovery.js").read_text(encoding="utf-8")

    assert manifest["version"] == "0.1.3"
    assert manifest["background"]["service_worker"] == "service_worker_recovery.js"
    assert recovery.startswith('importScripts("service_worker_hotfix.js")')
    assert "STALE_UI_COMPLETION_EVIDENCE_MAX_AGE_MS = 5_000" in recovery
    assert "STALE_UI_RELOAD_TIMEOUT_MS = 45_000" in recovery
    assert "canonicalCompletedAtMs" in recovery
    assert "runtimeReloaded" in recovery
    assert "runtimeReloadMs" in recovery
