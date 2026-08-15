from __future__ import annotations

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_pr811_recovery_worker_is_packaged() -> None:
    root = browser_native_extension_dir()
    recovery = (root / "service_worker_recovery.js").read_text(encoding="utf-8")
    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")

    assert 'importScripts("service_worker_recovery.js")' in observability
    assert recovery.startswith('importScripts("service_worker_hotfix.js")')
    assert "STALE_UI_COMPLETION_EVIDENCE_MAX_AGE_MS = 5_000" in recovery
    assert "STALE_UI_RELOAD_TIMEOUT_MS = 45_000" in recovery
    assert "canonicalCompletedAtMs" in recovery
    assert "runtimeReloaded" in recovery
    assert "runtimeReloadMs" in recovery
