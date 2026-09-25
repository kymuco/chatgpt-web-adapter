from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
MANIFEST = EXT / "manifest.json"
RUNTIME = EXT / "service_worker_runtime.js"
WRITE = EXT / "service_worker_runtime_write.js"
READ = EXT / "service_worker_runtime_read.js"
OBSERVATION = EXT / "service_worker_runtime_observation.js"
BOOTSTRAP = EXT / "service_worker_temporary_chat_route_reopen_probe.js"
RICH_SCHEMAS = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
CONNECTOR_SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _active_imports(source: str) -> list[str]:
    return [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("importScripts(")
    ]


def test_manifest_identity_is_preserved_as_thin_pr12_bootstrap() -> None:
    manifest = json.loads(_source(MANIFEST))

    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    bootstrap = _source(BOOTSTRAP)
    assert _active_imports(bootstrap) == ['importScripts("service_worker_runtime.js");']


def test_runtime_entrypoint_is_assembly_only_with_explicit_domain_order() -> None:
    source = _source(RUNTIME)
    expected = [
        'importScripts("service_worker_runtime_tab_reconciliation.js");',
        'importScripts("service_worker_runtime_tab_id.js");',
        'importScripts("service_worker_runtime_write.js");',
        'importScripts("service_worker_submit_authority.js");',
        'importScripts("service_worker_stream_metadata.js");',
        'importScripts("service_worker_runtime_tab_resolution.js");',
        'importScripts("service_worker_runtime_read.js");',
        'importScripts("service_worker_runtime_observation.js");',
        'importScripts("service_worker_native_message_router.js");',
        'importScripts("service_worker_official_page_turn_lifecycle.js");',
        'importScripts("service_worker_native_turn_lifecycle.js");',
    ]

    positions = [source.index(line) for line in expected]
    assert positions == sorted(positions)
    assert _active_imports(source) == expected

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


def test_runtime_enters_reviewed_base_chain_without_temporary_research_bootstrap() -> (
    None
):
    source = _source(RUNTIME)

    assert 'importScripts("service_worker_runtime_tab_reconciliation.js");' in source
    assert "service_worker_runtime_legacy.js" not in source
    assert "service_worker_runtime_legacy_impl.js" not in source
    assert "service_worker_temporary_chat_manual_ground_truth.js" not in source


def test_write_domain_owns_rich_and_text_write_assembly_only() -> None:
    source = _source(WRITE)
    ordered = [
        "service_worker_retained_conversation_tabs.js",
        "service_worker_rich_input_pr9_2.js",
        "service_worker_recovery_deadline.js",
        "service_worker_rich_input_deadline_repair_pr9_2.js",
        "service_worker_rich_input_closure_repair_pr9_2.js",
        "service_worker_raw_submit_primitives.js",
        "service_worker_rich_input_schema7_repair_pr9_2.js",
        "service_worker_optional_postwrite.js",
        "service_worker_submit_readiness.js",
        "service_worker_turn_context.js",
        "service_worker_protected_submit_expression.js",
        "service_worker_conversation_write_predicate.js",
        "service_worker_attachment_evidence.js",
        "service_worker_attachment_readiness.js",
        "service_worker_attachment_fence_read.js",
        "service_worker_attachment_cleanup.js",
        "service_worker_attachment_staging.js",
        "service_worker_rich_input_lifecycle.js",
        "service_worker_request_text_shape_compat.js",
        "service_worker_browser_indent_compat.js",
        "service_worker_request_inspection.js",
        "service_worker_ui_compat_pr11_7.js",
        "service_worker_text_submit_commit_hardening_pr11_3.js",
        "service_worker_ordinary_text_identity_authority.js",
        "service_worker_send_command.js",
    ]
    positions = [source.index(name) for name in ordered]

    assert positions == sorted(positions)
    assert len(_active_imports(source)) == len(ordered)
    assert source.rstrip().endswith('importScripts("service_worker_send_command.js");')
    assert "service_worker_cwa_identity_capture_diag.js" not in source
    assert "service_worker_canonical_read.js" not in source
    assert "service_worker_canonical_read_v2.js" not in source
    assert "service_worker_ui_liveness.js" not in source
    assert "service_worker_connector_support_pr10_0.js" not in source

    rich = _source(RICH_SCHEMAS)
    assert "service_worker_rich_input_schema7_core_pr9_2.js" in rich
    assert "service_worker_rich_input_schema29_repair_pr9_2.js" in rich
    for cross_domain_import in (
        "service_worker_request_text_shape_compat.js",
        "service_worker_browser_indent_compat.js",
        "service_worker_ui_compat_pr11_7.js",
        "service_worker_text_submit_commit_hardening_pr11_3.js",
        "service_worker_ordinary_text_identity_authority.js",
        "service_worker_product_source_citations_pr9_3.js",
        "service_worker_canonical_read.js",
        "service_worker_canonical_read_v2.js",
        "service_worker_canonical_read_session_auth.js",
    ):
        assert cross_domain_import not in rich


def test_read_domain_is_explicit_and_excludes_write_and_observation() -> None:
    source = _source(READ)
    citations = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    owner = 'importScripts("service_worker_message_inspection.js");'
    canonical = 'importScripts("service_worker_canonical_read_v2.js");'

    assert source.index(citations) < source.index(owner) < source.index(canonical)
    assert _active_imports(source) == [citations, owner, canonical]
    assert "service_worker_canonical_read_session_auth.js" not in source
    assert "service_worker_request_text_shape_compat.js" not in source
    assert "service_worker_browser_indent_compat.js" not in source
    assert "service_worker_text_submit_commit_hardening_pr11_3.js" not in source
    assert "service_worker_ordinary_text_identity_authority.js" not in source
    assert "service_worker_connector_support_pr10_0.js" not in source
    assert "service_worker_ui_liveness.js" not in source


def test_observation_domain_registers_connector_diagnostics_before_liveness() -> None:
    source = _source(OBSERVATION)
    connector = 'importScripts("service_worker_connector_support_pr10_0.js");'
    liveness = 'importScripts("service_worker_ui_liveness.js");'

    assert source.index(connector) < source.index(liveness)
    assert len(_active_imports(source)) == 2

    support = _source(CONNECTOR_SUPPORT)
    assert "service_worker_ui_liveness.js" not in support
    assert "registerNativeTurnDiagnosticHandler(" in support
    assert "executeNativeTurn = async function" not in support
