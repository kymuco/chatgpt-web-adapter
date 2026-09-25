from __future__ import annotations

import json
from pathlib import Path

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir
from tools.browser_worker_ownership_closure_gate import RETIRED_HISTORICAL_WORKERS

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_retired_pr87_characterization_workers_are_not_packaged() -> None:
    root = browser_native_extension_dir()

    assert all(not (root / name).exists() for name in RETIRED_HISTORICAL_WORKERS)


def test_no_extension_worker_imports_retired_characterization_source() -> None:
    for path in EXT.glob("*.js"):
        source = path.read_text(encoding="utf-8")
        for name in RETIRED_HISTORICAL_WORKERS:
            assert f'importScripts("{name}")' not in source, (path.name, name)


def test_production_temporary_runtime_keeps_copied_readiness_semantics() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]

    assert worker_name == "service_worker_temporary_chat_route_reopen_probe.js"

    bootstrap = (root / worker_name).read_text(encoding="utf-8")
    assert 'importScripts("service_worker_runtime.js")' in bootstrap

    runtime = (root / "service_worker_runtime.js").read_text(encoding="utf-8")
    assert 'importScripts("service_worker_runtime_tab_reconciliation.js")' in runtime

    readiness = (root / "service_worker_temporary_startup_readiness.js").read_text(
        encoding="utf-8"
    )
    assert "_cwaTemporaryControlSnapshot" in readiness
    assert "_pr87TemporaryControlSnapshot" not in readiness


def test_production_temporary_product_and_startup_readiness_remain_loaded() -> None:
    observation = (
        EXT / "service_worker_observability.js"
    ).read_text(encoding="utf-8")

    assert 'importScripts("service_worker_temporary_startup_readiness.js");' in observation
    assert 'importScripts("service_worker_temporary_product.js");' in observation
    assert 'importScripts("service_worker_temporary_lifecycle.js");' in observation
