from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
MANIFEST = EXT / "manifest.json"
RUNTIME = EXT / "service_worker_runtime.js"
LEGACY = EXT / "service_worker_runtime_legacy.js"
WRITE = EXT / "service_worker_runtime_write.js"
READ = EXT / "service_worker_runtime_read.js"
OBSERVATION = EXT / "service_worker_runtime_observation.js"
ROUTE_REOPEN = EXT / "service_worker_temporary_chat_route_reopen_probe.js"
RICH_SCHEMAS = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
CONNECTOR_SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_manifest_uses_stable_pr12_runtime_entrypoint() -> None:
    manifest = json.loads(_source(MANIFEST))

    assert manifest["version"] == "0.1.14"
    assert manifest["background"]["service_worker"] == "service_worker_runtime.js"


def test_runtime_entrypoint_is_assembly_only_with_explicit_domain_order() -> None:
    source = _source(RUNTIME)
    expected = [
        'importScripts("service_worker_runtime_legacy.js");',
        'importScripts("service_worker_runtime_write.js");',
        'importScripts("service_worker_runtime_read.js");',
        'importScripts("service_worker_runtime_observation.js");',
    ]

    positions = [source.index(line) for line in expected]
    assert positions == sorted(positions)
    assert source.count("importScripts(") == len(expected)

    for forbidden in (
        "executeNativeTurn =",
        "submitOfficialPageTurn =",
        "onNativeMessage =",
        "chrome.debugger",
        "chrome.tabs",
        "Input.dispatch",
        "Runtime.evaluate",
        "fetch(",
    ):
        assert forbidden not in source


def test_legacy_domain_quarantines_historical_runtime_chain() -> None:
    source = _source(LEGACY)

    assert source.count("importScripts(") == 1
    assert 'importScripts("service_worker_temporary_chat_route_reopen_probe.js");' in source

    route = _source(ROUTE_REOPEN)
    for cross_domain_import in (
        "service_worker_rich_input_pr9_2.js",
        "service_worker_rich_input_deadline_repair_pr9_2.js",
        "service_worker_rich_input_closure_repair_pr9_2.js",
        "service_worker_rich_input_schema7_repair_pr9_2.js",
        "service_worker_connector_support_pr10_0.js",
    ):
        assert cross_domain_import not in route


def test_write_domain_owns_rich_and_text_write_assembly_only() -> None:
    source = _source(WRITE)
    ordered = [
        "service_worker_rich_input_pr9_2.js",
        "service_worker_rich_input_deadline_repair_pr9_2.js",
        "service_worker_rich_input_closure_repair_pr9_2.js",
        "service_worker_rich_input_schema7_repair_pr9_2.js",
        "service_worker_ui_compat_pr11_7.js",
        "service_worker_text_submit_commit_hardening_pr11_3.js",
    ]
    positions = [source.index(name) for name in ordered]

    assert positions == sorted(positions)
    assert source.count("importScripts(") == len(ordered)
    assert "service_worker_canonical_read.js" not in source
    assert "service_worker_ui_liveness.js" not in source
    assert "service_worker_connector_support_pr10_0.js" not in source

    rich = _source(RICH_SCHEMAS)
    assert "service_worker_rich_input_schema7_core_pr9_2.js" in rich
    assert "service_worker_rich_input_schema29_repair_pr9_2.js" in rich
    for cross_domain_import in (
        "service_worker_ui_compat_pr11_7.js",
        "service_worker_text_submit_commit_hardening_pr11_3.js",
        "service_worker_product_source_citations_pr9_3.js",
        "service_worker_canonical_read.js",
    ):
        assert cross_domain_import not in rich


def test_read_domain_is_explicit_and_excludes_write_and_observation() -> None:
    source = _source(READ)
    citations = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    canonical = 'importScripts("service_worker_canonical_read.js");'

    assert source.index(citations) < source.index(canonical)
    assert source.count("importScripts(") == 2
    assert "service_worker_text_submit_commit_hardening_pr11_3.js" not in source
    assert "service_worker_connector_support_pr10_0.js" not in source
    assert "service_worker_ui_liveness.js" not in source


def test_observation_domain_keeps_connector_turn_wrapper_before_liveness() -> None:
    source = _source(OBSERVATION)
    connector = 'importScripts("service_worker_connector_support_pr10_0.js");'
    liveness = 'importScripts("service_worker_ui_liveness.js");'

    assert source.index(connector) < source.index(liveness)
    assert source.count("importScripts(") == 2

    support = _source(CONNECTOR_SUPPORT)
    assert "service_worker_ui_liveness.js" not in support
    assert support.rstrip().endswith("};")
