from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RICH = EXT / "service_worker_rich_input_pr9_2.js"
MOUNT = EXT / "service_worker_rich_input_schema24_repair_pr9_2.js"
NODE = shutil.which("node")

_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const owner = fs.readFileSync(process.argv[1], "utf8");
const scenario = process.argv[2];
const start = owner.indexOf("const PR92_PRESTAGE_MOUNT_RECOVERY_RESERVE_MS");
const end = owner.indexOf("function _pr92RichInputBaseSupportResult", start);
if (start < 0 || end < start) throw Error("Production recovery seam absent");
const production = owner.slice(start, end);

const calls = [];
const c = {
  staged: false,
  stagedTabId: null,
  attachmentCount: 0,
  attachmentPaths: ["a.md", "b.md", "c.md"],
  deadlineAt: 240000
};
const missing = () => new Error(
  "PR9_2_OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED:" +
  "tabStatus=complete:tabActive=false:tabDiscarded=false:" +
  "evidence=official-composer-missing:polls=100"
);
const tab = {
  id: 42,
  url: scenario === "route-drift" ? "https://chatgpt.com/c/foreign" :
       "https://chatgpt.com/",
  active: scenario === "active-tab",
  discarded: false,
  frozen: false,
  status: "complete"
};
const ctx = {
  _pr92ActiveRichInputContext: c,
  _pr92DirtyAttachmentTabId: scenario === "fenced" ? 42 : null,
  _pr811BaseMaybeRecoverStaleRuntimeUi: async () =>
    ({runtimeReloaded: false, runtimeReloadMs: null}),
  _pr92RemainingTurnMs: () => 200000,
  _pr92RemainingTurnMsOrZero: () =>
    scenario === "near-deadline" ? 5000 : 200000,
  _pr92Schema7RunUntil: async (_deadline, _stage, operation) => operation(),
  storedRuntimeTabId: async () => scenario === "foreign-owner" ? 999 : 42,
  chrome: {tabs: {get: async () => ({...tab})}},
  isChatGPTUrl: url => url.startsWith("https://chatgpt.com/"),
  ensureRuntimeTab: async () => {calls.push("ensure-tab"); return {...tab};},
  _pr92ReloadRuntimeTabWithinTurn: async () => {calls.push("reload");},
  _pr92StageOfficialPageAttachments: async () => {
    calls.push("stage");
    if (scenario === "ambiguous-error") {
      throw new Error("PR9_2_FILE_INPUT_NOT_FOUND");
    }
    if (scenario === "double-missing") throw missing();
    if (calls.filter(x => x === "stage").length === 1) throw missing();
    return 3;
  },
  URL,
  Error,
  Number
};
vm.createContext(ctx);
vm.runInContext(production, ctx);
(async () => {
  let result = null;
  let error = null;
  try {
    result = await ctx._pr92RecoverThenStage({
      conversationId: scenario === "continuation" ? "saved" : null,
      timeoutMs: 240000
    });
  } catch (cause) {
    error = cause.message;
  }
  console.log(JSON.stringify({
    result: result !== null,
    error,
    calls,
    staged: c.staged,
    attachmentCount: c.attachmentCount,
    messageWrites: 0
  }));
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""


def _scenario(name: str) -> dict[str, object]:
    if NODE is None:
        pytest.skip("Node.js unavailable")
    run = subprocess.run(
        [NODE, "-e", _JS, str(RICH), name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_untouched_new_chat_recovers_page_mount_once_before_first_file_selection() -> None:
    result = _scenario("blank-new-chat")
    assert result["calls"] == ["ensure-tab", "stage", "reload", "stage"]
    assert result["result"] is True
    assert result["staged"] is True
    assert result["attachmentCount"] == 3
    assert result["messageWrites"] == 0


@pytest.mark.parametrize(
    "scenario",
    [
        "continuation",
        "fenced",
        "near-deadline",
        "active-tab",
        "foreign-owner",
        "route-drift",
        "ambiguous-error",
    ],
)
def test_prewrite_recovery_fails_closed_without_navigation(scenario: str) -> None:
    result = _scenario(scenario)
    assert result["result"] is False
    assert result["calls"] == ["ensure-tab", "stage"]
    assert result["staged"] is False
    assert result["attachmentCount"] == 0
    assert result["error"]
    assert result["messageWrites"] == 0


def test_second_mount_failure_is_terminal_with_no_second_reload() -> None:
    result = _scenario("double-missing")
    assert result["result"] is False
    assert result["calls"] == ["ensure-tab", "stage", "reload", "stage"]
    assert "OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED" in result["error"]
    assert result["messageWrites"] == 0


def test_production_mount_failure_relinquishes_debugger_before_recovery() -> None:
    source = MOUNT.read_text(encoding="utf-8")
    start = source.index("try {\n      evidence = await _pr92Schema24WaitForOfficialComposerMounted")
    end = source.index("// The evidence that first proves mount", start)
    block = source[start:end]
    assert "SCHEMA24_PRESTAGE_MOUNT_FAILURE_DEBUGGER_DETACH" in block
    assert "await _pr92Schema15DetachWithinDeadline" in block
    assert "attached = false;" in block


def test_production_recovery_cannot_repeat_file_stage_after_unrelated_error() -> None:
    source = RICH.read_text(encoding="utf-8")
    start = source.index("async function _pr92RecoverBlankNewChatPageOnce")
    end = source.index("function _pr92RichInputBaseSupportResult", start)
    block = source[start:end]
    assert 'detail.startsWith("PR9_2_OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED:")' in block
    assert "conversationId !== null" in block
    assert "context.staged === true" in block
    assert "Number.isInteger(_pr92DirtyAttachmentTabId)" in block
    assert "storedRuntimeTabId()" in block
    assert "current.active === true" in block
    assert "_pr92ReloadRuntimeTabWithinTurn(tab.id, null)" in block
    assert "Input.insertText" not in block
    assert "DOM.setFileInputFiles" not in block
    assert "submitOfficialPageTurn" not in block
