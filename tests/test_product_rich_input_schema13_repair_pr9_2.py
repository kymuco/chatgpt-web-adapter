from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA13 = EXT / "service_worker_rich_input_schema13_repair_pr9_2.js"
GATE13 = PKG / "product_rich_input_live_gate_schema13_pr9_2.py"


def test_schema_13_overlay_is_loaded_after_schema_12():
    text = LOADER.read_text(encoding="utf-8")
    schema12 = 'importScripts("service_worker_rich_input_schema12_repair_pr9_2.js");'
    schema13 = 'importScripts("service_worker_rich_input_schema13_repair_pr9_2.js");'
    assert schema12 in text
    assert schema13 in text
    assert text.index(schema12) < text.index(schema13)


def test_schema_13_replaces_captured_raw_staging_primitive():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA13_REPAIR_SCHEMA = 13;" in text
    assert "async function _pr92Schema13StageFileSelection" in text
    assert "_pr92ClosurePriorStageOfficialPageAttachments" not in text
    assert "_pr92StageOfficialPageAttachments = async function _pr92Schema13FullyBoundedStage" in text
    assert "await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(" in text
    assert "return _pr92Schema12ObservePostStageAttachmentEvidence(" in text


def test_schema_13_bounds_every_awaited_staging_phase():
    text = SCHEMA13.read_text(encoding="utf-8")
    required_stages = [
        "SCHEMA13_STAGE_DEBUGGER_ATTACH",
        "SCHEMA13_STAGE_RUNTIME_ENABLE",
        "SCHEMA13_STAGE_DOM_ENABLE",
        "SCHEMA13_STAGE_COMPOSER_READY",
        "SCHEMA13_STAGE_FILE_INPUT_LOOKUP",
        "SCHEMA13_REVEAL_FILE_INPUT_EVALUATE",
        "SCHEMA13_STAGE_FILE_INPUT_LOOKUP_AFTER_REVEAL",
        "SCHEMA13_STAGE_FENCE_PERSIST",
        "SCHEMA13_STAGE_FILE_SELECTION",
    ]
    for stage in required_stages:
        assert f'"{stage}"' in text
    assert text.count("await _pr92Schema7RunUntil(") >= 7
    assert "() => waitForComposerReady(debuggee, readyBudget)" in text
    assert "() => _pr92PersistDirtyAttachmentFence(tabId)" in text
    assert '() => chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles"' in text


def test_schema_13_persists_durable_fence_before_file_selection_dispatch():
    text = SCHEMA13.read_text(encoding="utf-8")
    persist = text.index('"SCHEMA13_STAGE_FENCE_PERSIST"')
    fence_check = text.index("_pr92DirtyAttachmentTabId !== tabId")
    selection = text.index('"SCHEMA13_STAGE_FILE_SELECTION"')
    assert persist < fence_check < selection
    assert "lateFileSelectionFailsClosedBehindDurableFence: true" in text


def test_schema_13_uses_page_deadline_for_side_effecting_reveal():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "const pageDeadlineEpochMs = Date.now() + remaining;" in text
    assert "if (!Number.isFinite(deadlineEpochMs) || Date.now() >= deadlineEpochMs)" in text
    assert "if (Date.now() >= deadlineEpochMs) return null;" in text
    assert "button.click();" in text


def test_schema_13_post_selection_release_and_detach_are_non_blocking():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "_pr92Schema13BestEffortReleaseObject(debuggee, objectId);" in text
    assert "if (attached) _pr92Schema13BestEffortDetach(debuggee);" in text
    finally_tail = text.split("} finally {", 1)[1].split("}\n}\n", 1)[0]
    assert "await chrome.debugger.detach" not in finally_tail
    assert "await chrome.debugger.sendCommand" not in finally_tail
    assert "postSelectionCleanupNonBlocking: true" in text


def test_schema_13_late_debugger_attach_is_auto_detached():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "attachPending.then(" in text
    assert "() => _pr92Schema13BestEffortDetach(debuggee)" in text
    assert "lateStagingDebuggerAttachAutoDetached: true" in text


def test_schema_13_gate_requires_complete_staging_deadline_contract():
    text = GATE13.read_text(encoding="utf-8")
    assert "SCHEMA = 13" in text
    assert "class ProductRichInputSchema13LiveProvider" in text
    assert "legacy[\"schema\"] = _v12.SCHEMA" in text
    required = [
        "attachment_staging_primitive_deadline_bounded",
        "staging_debugger_setup_deadline_bounded",
        "staging_composer_readiness_deadline_bounded",
        "staging_file_input_lookup_deadline_bounded",
        "staging_fence_persistence_deadline_bounded",
        "staging_file_selection_deadline_bounded",
        "late_staging_debugger_attach_auto_detached",
        "late_file_selection_fails_closed_behind_durable_fence",
        "post_selection_cleanup_non_blocking",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v12.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
