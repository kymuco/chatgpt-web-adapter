from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
LIVENESS = EXT / "service_worker_ui_liveness.js"
SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"


def test_liveness_worker_wraps_native_messages_without_wrapping_turn_dispatch() -> None:
    source = LIVENESS.read_text(encoding="utf-8")

    assert "const _cwaUiLivenessPriorOnNativeMessage = onNativeMessage;" in source
    assert 'message?.type !== "ui_liveness"' in source
    assert "onNativeMessage = async function" in source
    assert "executeNativeTurn =" not in source
    assert "queryComposerReadiness(debuggee)" in source


def test_liveness_worker_requires_positive_generating_evidence() -> None:
    source = LIVENESS.read_text(encoding="utf-8")

    assert '"READY_FOR_INPUT", "COMPOSER_READY"' in source
    assert '"GENERATING", "GENERATION_CONTROL_VISIBLE"' in source
    assert "generationControlVisible: true" in source
    assert '"UNKNOWN", "COMPOSER_BUSY"' in source
    assert '"UNKNOWN", "ACTIVE_REQUEST_IN_PROGRESS"' in source
    assert '"UNAVAILABLE", "RUNTIME_TAB_ABSENT"' in source


def test_liveness_worker_serializes_non_liveness_messages_behind_active_probe() -> None:
    source = LIVENESS.read_text(encoding="utf-8")

    assert "let _cwaUiLivenessProbePromise = null;" in source
    assert "const activeProbe = _cwaUiLivenessProbePromise;" in source
    assert "if (activeProbe)" in source
    assert "await activeProbe" in source
    assert "_cwaUiLivenessProbePromise = probe;" in source
    assert "_cwaUiLivenessProbePromise = null;" in source


def test_liveness_worker_has_no_write_navigation_or_runtime_creation_primitives() -> None:
    source = LIVENESS.read_text(encoding="utf-8")

    for forbidden in (
        "Input.insertText",
        "Input.dispatchKeyEvent",
        "Input.dispatchMouseEvent",
        "DOM.setFileInputFiles",
        "executeOfficialPageTurn",
        "submitOfficialPageTurn",
        "ensureRuntimeTab",
        "chrome.tabs.create",
        "chrome.tabs.update",
        "fetch(",
    ):
        assert forbidden not in source

    for contract in (
        "rawDomExported: false",
        "navigationPerformed: false",
        "runtimeTabCreated: false",
        "writePerformed: false",
        "canonicalReadPerformed: false",
        "canonicalFinalityProven: false",
        "grantsWriteAuthority: false",
        "grantsRetryAuthority: false",
    ):
        assert contract in source


def test_liveness_worker_loads_inside_outer_turn_support_without_replacing_it() -> None:
    support = SUPPORT.read_text(encoding="utf-8")

    liveness_import = 'importScripts("service_worker_ui_liveness.js");'
    final_wrapper = "executeNativeTurn = async function _pr100"
    assert liveness_import in support
    assert support.index(liveness_import) < support.index(final_wrapper)
    assert support.rstrip().endswith("};")
