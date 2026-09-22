from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

TEMPORARY_CHARACTERIZATION_FILES = (
    "service_worker_temporary_chat.js",
    "service_worker_temporary_chat_state_semantics.js",
    "service_worker_temporary_chat_ax_semantics.js",
    "service_worker_temporary_chat_turn_probe.js",
    "service_worker_temporary_chat_history_probe.js",
    "service_worker_temporary_chat_manual_ground_truth.js",
)


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def test_temporary_characterization_sources_no_longer_own_production_dispatch() -> None:
    sources = {name: _source(name) for name in TEMPORARY_CHARACTERIZATION_FILES}

    for name, source in sources.items():
        assert "executeNativeTurn = async function" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name

    runtime = _source("service_worker_runtime.js")
    assert "service_worker_runtime_legacy.js" not in runtime
    assert "service_worker_runtime_legacy_impl.js" not in runtime
    assert "service_worker_temporary_chat_manual_ground_truth.js" not in runtime


def test_historical_characterization_sources_remain_non_runtime_evidence() -> None:
    for name in TEMPORARY_CHARACTERIZATION_FILES:
        source = _source(name)
        assert 'registerNativeTurnDiagnosticHandler(' not in source


def test_temporary_mode_composition_remains_snapshot_based() -> None:
    base = _source("service_worker_temporary_chat.js")
    state = _source("service_worker_temporary_chat_state_semantics.js")
    ax = _source("service_worker_temporary_chat_ax_semantics.js")
    semantic = _source("service_worker_temporary_chat_semantic_notice.js")

    assert "async function _pr87HandleTemporaryModeProbe(message)" in base
    assert "_pr87TemporaryControlSnapshotExpression =" in state
    assert "executeNativeTurn" not in state
    assert "async function _pr87HandleTemporaryModeProbeWithAX(message)" in ax
    assert "await _pr87HandleTemporaryModeProbe(message)" in ax
    assert 'temporaryStateSemantics: "accessibility_tree_v1"' in ax
    assert "_pr87TemporaryControlSnapshot =" in semantic
    assert "modeMarkerObserved" in semantic


def test_writeful_characterization_remains_explicitly_guarded() -> None:
    turn = _source("service_worker_temporary_chat_turn_probe.js")
    manual = _source("service_worker_temporary_chat_manual_ground_truth.js")

    assert "async function _pr87HandleTemporaryTurnCharacterization(message)" in turn
    assert "TEMPORARY_CHAT_TURN_PROBE_DURABLE_RISK_ACK_REQUIRED" in turn
    assert "message?.acknowledgeDurableRisk !== true" in turn

    assert "async function _pr87HandleManualTemporaryGroundTruth(message)" in manual
    assert "TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_CONFIRMATION_REQUIRED" in manual
    assert "message?.manualTemporaryConfirmed !== true" in manual


def test_pr813_production_temporary_lifecycle_remains_separate() -> None:
    observation = _source("service_worker_observability.js")

    for production in (
        "service_worker_temporary_chat_production_pr8_13.js",
        "service_worker_temporary_session_identity_pr8_13.js",
        "service_worker_temporary_fresh_identity_flush_pr8_13.js",
        "service_worker_temporary_startup_readiness_pr8_13_2.js",
    ):
        assert f'importScripts("{production}");' in observation
