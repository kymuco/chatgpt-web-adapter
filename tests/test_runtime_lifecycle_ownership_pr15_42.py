from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
NATIVE_OWNER = EXT / "service_worker_native_turn_lifecycle.js"
PAGE_OWNER = EXT / "service_worker_official_page_turn_lifecycle.js"
OBSERVABILITY_PAGE = EXT / "service_worker_observability_page_turn_lifecycle.js"
RUNTIME = EXT / "service_worker_runtime.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_root_lifecycle_public_names_have_one_owner_each() -> None:
    core = _source(CORE)
    native = _source(NATIVE_OWNER)
    page = _source(PAGE_OWNER)

    assert "async function _cwaBaseExecuteNativeTurn(" in core
    assert "async function executeNativeTurn(" not in core
    assert native.count("async function executeNativeTurn(") == 1
    assert "executeNativeTurn =" not in native
    assert "_cwaNativeTurnBaseExecute" not in native

    assert "async function _cwaBaseExecuteOfficialPageTurn(" in core
    assert "async function executeOfficialPageTurn(" not in core
    assert page.count("async function executeOfficialPageTurn(") == 1
    assert "executeOfficialPageTurn =" not in page


def test_native_root_terminates_in_named_base_and_keeps_public_page_handoff() -> None:
    core = _source(CORE)
    native = _source(NATIVE_OWNER)

    assert "return _cwaBaseExecuteNativeTurn(message);" in native

    start = core.index("async function _cwaBaseExecuteNativeTurn")
    end = core.index("function safeTurnFailureEvidence", start)
    block = core[start:end]
    assert "const result = await executeOfficialPageTurn({" in block
    assert "_cwaBaseExecuteOfficialPageTurn({" not in block


def test_active_official_page_terminal_remains_recovery_boundary() -> None:
    page = _source(PAGE_OWNER)
    observability = _source(OBSERVABILITY_PAGE)

    assert "_cwaOfficialPageTurnObservability" in page
    assert "_executeOfficialPageTurnWithObservabilityLifecycle(args)" in page
    assert "_executeOfficialPageTurnWithEarlyTerminalBoundary(args)" in observability
    assert "_cwaBaseExecuteOfficialPageTurn(" not in page
    assert "_cwaBaseExecuteOfficialPageTurn(" not in observability


def test_runtime_loads_page_owner_before_native_owner() -> None:
    runtime = _source(RUNTIME)
    page = 'importScripts("service_worker_official_page_turn_lifecycle.js");'
    native = 'importScripts("service_worker_native_turn_lifecycle.js");'

    assert runtime.index(page) < runtime.index(native)
    assert runtime.rstrip().endswith(native)
