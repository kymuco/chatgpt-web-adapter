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

async function runCase(
  error, stagedTabId, closerProvesAbsent,
  fresh = true, armed = false, activated = false
) {
  const calls = [];
  const context = {
    deadlineAt: 10000,
    schema20ProtectedSubmitArmed: armed,
    schema20ProtectedSubmitMarkerObserved: false,
    schema20PostArmConversationRequests: [],
    prewriteActivationListener: () => {},
    prewriteActivatedTabIds: new Set(),
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
    _pr92ClearOfficialPageAttachments: async (tabId, _ms, options) => {
      const inactive = env._pr92ActiveRichInputContext === null;
      const strictRoot = options?.requireUntouchedRootInactive === true;
      calls.push(["close", tabId, inactive, strictRoot]);
      return inactive && strictRoot && closerProvesAbsent === true;
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
        context.prewriteCleanupOwnedTabId = fresh ? stagedTabId : null;
        if (activated) context.prewriteActivatedTabIds.add(stagedTabId);
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
    ambiguousFailure: await runCase("NETWORK_FAILURE_UNKNOWN", 73, true),
    retainedTab: await runCase(proofError, 73, true, false),
    armed: await runCase(proofError, 73, true, true, true),
    previouslyActivated: await runCase(proofError, 73, true, true, false, true)
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
    assert cleaned["calls"] == [["close", 73, True, True], ["clear", True]]
    assert cleaned["fenceTabId"] is None

    for case in (
        "prewriteUnproven",
        "mismatchedTab",
        "ambiguousFailure",
        "retainedTab",
        "armed",
        "previouslyActivated",
    ):
        outcome = result[case]
        assert outcome["fenceTabId"] == 73, (case, outcome)
        assert outcome["failure"].startswith(
            "PR9_2_DOWNSTREAM_FAILED_AND_ATTACHMENT_CLEANUP_UNPROVEN:"
        )
        assert all(call[0] != "clear" for call in outcome["calls"]), outcome

    assert result["prewriteUnproven"]["calls"] == [["close", 73, True, True]]
    assert result["mismatchedTab"]["calls"] == [["close", 73, False, False]]
    assert result["ambiguousFailure"]["calls"] == [["close", 73, False, False]]
    assert result["retainedTab"]["calls"] == [["close", 73, False, False]]
    assert result["armed"]["calls"] == [["close", 73, False, False]]
    assert result["previouslyActivated"]["calls"] == [["close", 73, False, False]]
    for value in result.values():
        assert value["active"] is False
        assert value["turnActive"] is False
        assert value["dispatched"] == 1


CLOSER = EXT / "service_worker_rich_input_schema8_repair_pr9_2.js"

_CLOSER_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("function _pr92Schema8FenceIdentityMatches(");
const end = source.indexOf("function _pr92Schema8AugmentSupportResult(", start);
if (start < 0 || end <= start) throw Error("production closer seam missing");
const production = source.slice(start, end);

async function simulate(scenario) {
  const events = () => {
    const listeners = new Set();
    return {
      addListener: (fn) => listeners.add(fn),
      removeListener: (fn) => listeners.delete(fn),
      emit: (...args) => { for (const fn of [...listeners]) fn(...args); },
      size: () => listeners.size
    };
  };
  const onUpdated = events();
  const onRemoved = events();
  const onActivated = events();
  const onStorageChanged = events();
  const calls = [];
  let removed = false;
  let tab = {
    id: 73,
    url: scenario === "conversation" ? "https://chatgpt.com/c/existing" :
         "https://chatgpt.com/",
    active: scenario === "active",
    status: "complete",
    discarded: false,
    frozen: false
  };
  const ctx = {
    CHATGPT_ORIGIN: "https://chatgpt.com",
    RUNTIME_TAB_KEY: "runtime",
    PR92_DIRTY_ATTACHMENT_STORAGE_KEY: "fence",
    PR92_SCHEMA7_SESSION_IDENTITY_KEY: "identity",
    _pr92ActiveRichInputContext: null,
    _pr92DeadlineRepairDeadlineFromBudget: (ms) => ms,
    _pr92DeadlineRepairIsTimeoutError: () => false,
    _pr92DeadlineRepairIsMissingTabError: () => false,
    _pr92DeadlineRepairProveTabAbsent: async () => removed,
    _pr92Schema7RunUntil: async (_deadline, stage, operation) => {
      if (stage === "CLEANUP_RUNTIME_TAB_FINAL_LOOKUP") {
        if (scenario === "activated-during-proof") {
          onActivated.emit({ tabId: 73 });
          tab.active = true;
        }
        if (scenario === "route-changed-during-proof") {
          onUpdated.emit(73, { url: "https://chatgpt.com/c/existing" });
          tab.url = "https://chatgpt.com/c/existing";
        }
      }
      return operation();
    },
    _pr92Schema7ReadFenceRecords: async () => ({
      local: {tabId: 73, runtimeIdentity: "same"},
      session: {
        tabId: 73,
        runtimeIdentity: scenario === "wrong-fence" ? "other" : "same"
      }
    }),
    storedRuntimeTabId: async () => scenario === "wrong-owner" ? 74 : 73,
    isChatGPTUrl: (url) => url.startsWith("https://chatgpt.com/"),
    chrome: {
      tabs: {
        get: async () => ({...tab}),
        remove: async (id) => { calls.push(["remove", id]); removed = true; },
        onUpdated, onRemoved, onActivated
      },
      storage: { onChanged: onStorageChanged }
    },
    Number,
    Object,
    Error
  };
  vm.createContext(ctx);
  vm.runInContext(production, ctx);
  const result = await ctx._pr92Schema8ClearFencedRuntimeTab(
    73, 1000, {requireUntouchedRootInactive: true}
  );
  return {
    result, calls, removed,
    listenerCount:
      onUpdated.size() + onRemoved.size() +
      onActivated.size() + onStorageChanged.size()
  };
}
(async () => {
  const names = [
    "fresh",
    "active",
    "conversation",
    "wrong-fence",
    "wrong-owner",
    "activated-during-proof",
    "route-changed-during-proof"
  ];
  const results = {};
  for (const name of names) results[name] = await simulate(name);
  process.stdout.write(JSON.stringify(results));
})().catch((err) => {
  console.error(err.stack || err);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
def test_production_strict_closer_never_removes_active_or_retained_tabs() -> None:
    completed = subprocess.run(
        [NODE, "-e", _CLOSER_JS, str(CLOSER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    results = json.loads(completed.stdout)
    assert results["fresh"]["result"] is True
    assert results["fresh"]["calls"] == [["remove", 73]]
    for name in (
        "active",
        "conversation",
        "wrong-fence",
        "wrong-owner",
        "activated-during-proof",
        "route-changed-during-proof",
    ):
        result = results[name]
        assert result["result"] is False, (name, result)
        assert result["removed"] is False, (name, result)
        assert result["calls"] == [], (name, result)
    assert all(r["listenerCount"] == 0 for r in results.values())
