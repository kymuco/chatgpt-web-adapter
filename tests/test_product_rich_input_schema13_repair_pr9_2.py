from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

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
    assert "async function _pr92Schema13FullyBoundedStage" in text
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
        "SCHEMA13_STAGE_RELEASE_OBJECT",
        "SCHEMA13_STAGE_DEBUGGER_DETACH",
    ]
    for stage in required_stages:
        assert f'"{stage}"' in text
    assert text.count("await _pr92Schema7RunUntil(") >= 9
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
    assert (
        "if (!Number.isFinite(deadlineEpochMs) || Date.now() >= deadlineEpochMs)"
        in text
    )
    assert "if (Date.now() >= deadlineEpochMs) return null;" in text
    assert "button.click();" in text


def test_schema_13_success_cleanup_is_bounded_before_poststage_observer():
    text = SCHEMA13.read_text(encoding="utf-8")
    selection = text.index('"SCHEMA13_STAGE_FILE_SELECTION"')
    release = text.index('"SCHEMA13_STAGE_RELEASE_OBJECT"')
    detach = text.index('"SCHEMA13_STAGE_DEBUGGER_DETACH"')
    returned = text.index("return attachmentPaths.length;")
    assert selection < release < detach < returned
    assert "stagingPostSelectionCleanupDeadlineBounded: true" in text


def test_schema_13_timeout_cleanup_is_best_effort_and_non_awaited():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "_pr92Schema13BestEffortReleaseObject(debuggee, objectId);" in text
    assert "if (attached) _pr92Schema13BestEffortDetach(debuggee);" in text
    finally_tail = text.split("} finally {", 1)[1].split("}\n}\n", 1)[0]
    assert "await chrome.debugger.detach" not in finally_tail
    assert "await chrome.debugger.sendCommand" not in finally_tail
    assert "postSelectionCleanupBestEffortAfterTimeout: true" in text


def test_schema_13_late_debugger_attach_is_auto_detached():
    text = SCHEMA13.read_text(encoding="utf-8")
    assert "attachPending.then(" in text
    assert "() => _pr92Schema13BestEffortDetach(debuggee)" in text
    assert "lateStagingDebuggerAttachAutoDetached: true" in text


def test_schema_13_gate_requires_complete_staging_deadline_contract():
    text = GATE13.read_text(encoding="utf-8")
    assert "SCHEMA = 13" in text
    assert "class ProductRichInputSchema13LiveProvider" in text
    assert 'legacy["schema"] = _v12.SCHEMA' in text
    required = [
        "attachment_staging_primitive_deadline_bounded",
        "staging_debugger_setup_deadline_bounded",
        "staging_composer_readiness_deadline_bounded",
        "staging_file_input_lookup_deadline_bounded",
        "staging_fence_persistence_deadline_bounded",
        "staging_file_selection_deadline_bounded",
        "staging_post_selection_cleanup_deadline_bounded",
        "late_staging_debugger_attach_auto_detached",
        "late_file_selection_fails_closed_behind_durable_fence",
        "post_selection_cleanup_best_effort_after_timeout",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v12.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


@pytest.mark.parametrize(
    ("multiple", "expected_batches"),
    [
        (True, [["a.md", "b.md", "c.md"]]),
        (False, [["a.md"], ["b.md"], ["c.md"]]),
    ],
)
def test_three_file_stage_selects_all_files_without_submit(
    multiple: bool, expected_batches: list[list[str]]
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const code = fs.readFileSync(process.argv[1], "utf8");
const multiple = process.argv[2] === "true";
const batches = [], staged = [], verified = [];
const chrome = {debugger: {
  attach: async () => {},
  detach: async () => {},
  sendCommand: async (_target, command, payload) => {
    if (command === "Runtime.callFunctionOn") {
      return {result: {value: multiple}};
    }
    if (command === "DOM.setFileInputFiles") {
      if (!multiple && payload.files.length !== 1) {
        throw Error("input cannot receive multiple files");
      }
      batches.push(payload.files);
      staged.push(...payload.files);
    }
    return {};
  }
}};
const ctx = {
  chrome, performance, console,
  CDP_PROTOCOL_VERSION: "1.3",
  DEFAULT_READY_TIMEOUT_MS: 1000,
  _pr92DirtyAttachmentTabId: null,
  _pr92Schema7RunUntil: async (_deadline, _stage, op) => op(),
  _pr92RemainingTurnMs: () => 10000,
  _pr92BoundedSleep: async () => {},
  _pr92FindFileInputObjectId: async () => "file-input",
  _pr92PersistDirtyAttachmentFence: async (tabId) => {
    ctx._pr92DirtyAttachmentTabId = tabId;
  },
  _pr92ClosureWaitForPageOwnedAttachmentEvidence: async (
    _target, expected
  ) => {
    verified.push(expected);
    if (JSON.stringify(expected) !== JSON.stringify(staged)) {
      throw Error("partial attachment set not accepted");
    }
    return expected.length;
  },
  waitForComposerReady: async () => {},
};
vm.createContext(ctx);
vm.runInContext(code, ctx);
vm.runInContext(
  "_pr92Schema13StageFileSelection(7, ['a.md','b.md','c.md'], {deadlineAt: 1e10})",
  ctx
).then((count) => {
  console.log(JSON.stringify({count, batches, verified}));
}).catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
"""
    completed = subprocess.run(
        [node, "-e", script, str(SCHEMA13), str(multiple).lower()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["count"] == 3
    assert result["batches"] == expected_batches
    assert len(result["verified"]) == (0 if multiple else 3)
