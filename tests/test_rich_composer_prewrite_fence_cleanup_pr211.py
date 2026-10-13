from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

EXT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
OWNER = EXT / "service_worker_rich_input_pr9_2.js"
NODE = shutil.which("node")

_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const owner = fs.readFileSync(process.argv[1], "utf8");
const start = owner.indexOf("async function _executeNativeTurnWithPr92RichInput");
if (start < 0) throw new Error("owner missing");
const end = owner.indexOf("\n};", start);
if (end < 0) throw new Error("owner end missing");
const functionSource = owner.slice(start, end + 3);

async function runCase(error, stagedTabId, closerProvesAbsent) {
  const calls = [];
  const context = {
    deadlineAt: 10000,
    staged: false,
    stagedTabId: null,
    attachmentCount: 0
  };
  const env = {
    _pr92ActiveTurnContext: null,
    _pr92ActiveRichInputContext: null,
    PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE: true,
    _pr92DirtyAttachmentTabId: 73,
    _pr92CreateTurnContext: () => context,
    _pr92RequireCleanAttachmentState: async () => {},
    _pr92NormalizeAttachmentPaths: (paths) => paths,
    _pr92RemainingTurnMs: () => 5000,
    _pr92RemainingTurnMsOrZero: () => 5000,
    _pr92ClearOfficialPageAttachments: async (tabId) => {
      const inactive = env._pr92ActiveRichInputContext === null;
      calls.push(["close", tabId, inactive]);
      return inactive && closerProvesAbsent === true;
    },
    _pr92TryClearDirtyAttachmentFence: async () => {
      const inactive = env._pr92ActiveRichInputContext === null;
      calls.push(["clear", inactive]);
      if (!inactive) return false;
      env._pr92DirtyAttachmentTabId = null;
      return true;
    },
    Error,
    Number,
    Object,
    Array,
    String
  };
  vm.createContext(env);
  vm.runInContext(functionSource, env);
  let failure;
  let dispatched = 0;
  try {
    await env._executeNativeTurnWithPr92RichInput(
      {attachmentPaths: ["a", "b", "c"], text: "some text"},
      async () => {
        dispatched++;
        context.staged = true;
        context.stagedTabId = stagedTabId;
        context.attachmentCount = 3;
        throw new Error(error);
      }
    );
  } catch (err) {
    failure = String(err.message);
  }
  return {
    failure,
    calls,
    fenceTabId: env._pr92DirtyAttachmentTabId,
    active: env._pr92ActiveRichInputContext !== null,
    turnActive: env._pr92ActiveTurnContext !== null,
    dispatched
  };
}

(async () => {
  const proofError = "CWA_RICH_COMPOSER_TEXT_NOT_INSERTED";
  console.log(JSON.stringify({
    prewriteClean: await runCase(proofError, 73, true),
    prewriteUnproven: await runCase(proofError, 73, false),
    mismatchedTab: await runCase(proofError, 74, true),
    ambiguousFailure: await runCase("NETWORK_FAILURE_UNKNOWN", 73, true)
  }));
})().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
def test_exact_pre_submit_abort_can_clear_only_after_proven_tab_absence() -> None:
    completed = subprocess.run(
        [NODE, "-e", _JS, str(OWNER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    cleaned = result["prewriteClean"]
    assert cleaned["failure"] == "CWA_RICH_COMPOSER_TEXT_NOT_INSERTED"
    assert cleaned["calls"] == [["close", 73, True], ["clear", True]]
    assert cleaned["fenceTabId"] is None

    for case in ("prewriteUnproven", "mismatchedTab", "ambiguousFailure"):
        outcome = result[case]
        assert outcome["fenceTabId"] == 73, (case, outcome)
        assert outcome["failure"].startswith(
            "PR9_2_DOWNSTREAM_FAILED_AND_ATTACHMENT_CLEANUP_UNPROVEN:"
        )
        assert all(call[0] != "clear" for call in outcome["calls"]), outcome

    assert result["prewriteUnproven"]["calls"] == [["close", 73, True]]
    assert result["mismatchedTab"]["calls"] == [["close", 73, False]]
    assert result["ambiguousFailure"]["calls"] == [["close", 73, False]]
    for value in result.values():
        assert value["active"] is False
        assert value["turnActive"] is False
        assert value["dispatched"] == 1
