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
OWNER = EXT / "service_worker_rich_input_schema24_repair_pr9_2.js"
NODE = shutil.which("node")

_JS = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("const PR92_SCHEMA24_MOUNT_OBSERVATION_CAP_MS =");
const end = source.indexOf("function _pr92Schema24EvidenceIsClean(", start);
assert(start >= 0 && end > start);
const helper = source.slice(start, end);
const scenario = process.argv[2];
let now = 0;
let polls = 0;
let writes = 0;
const warnings = [];

const context = {
  performance: {now: () => now},
  _pr92Schema7RunUntil: async (deadline, stage, operation) => {
    if (scenario === "stalled-evaluate" &&
        stage === "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_MOUNT_READ") {
      now = deadline;
      throw new Error("PR9_2_TOTAL_TURN_TIMEOUT:" + stage);
    }
    return operation();
  },
  _pr92ClosureReadPageOwnedAttachmentEvidence: async () => {
    polls++;
    if (scenario === "late-mounted" && polls === 4) {
      return {officialComposerMounted: true, evidenceKind: "mounted"};
    }
    return {
      officialComposerMounted: false,
      evidenceKind: "official-composer-missing"
    };
  },
  _pr92BoundedSleep: async (_context, ms) => {now += ms;},
  PR92_PAGE_ATTACHMENT_POLL_MS: 150,
  chrome: {
    tabs: {
      get: async id => {
        assert.equal(id, 73);
        return {
          status: "complete",
          active: false,
          discarded: false,
          frozen: false
        };
      }
    }
  },
  console: {warn: (...args) => warnings.push(args)},
};
vm.createContext(context);
vm.runInContext(helper, context);

(async () => {
  const deadlineContext = {deadlineAt: 240_000};
  let result = null;
  let error = null;
  try {
    result = await context._pr92Schema24WaitForOfficialComposerMounted(
      {tabId: 73},
      deadlineContext,
      73
    );
  } catch (caught) {
    error = String(caught.message);
  }
  console.log(JSON.stringify({
    now, polls, writes, warnings,
    mounted: result?.officialComposerMounted === true, error
  }));
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""


def _scenario(name: str) -> dict:
    if NODE is None:
        pytest.skip("Node.js unavailable")
    result = subprocess.run(
        [NODE, "-e", _JS, str(OWNER), name],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_late_mounted_composer_is_accepted_using_original_evidence() -> None:
    result = _scenario("late-mounted")
    assert result["mounted"] is True
    assert result["error"] is None
    assert result["polls"] == 4
    assert result["writes"] == 0
    assert result["warnings"] == []


def test_blank_background_tab_fails_before_outer_turn_timeout() -> None:
    result = _scenario("never-mounted")
    assert result["mounted"] is False
    assert result["now"] <= 26_000
    assert result["polls"] > 2
    assert result["error"].startswith("PR9_2_OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED:")
    assert ":tabStatus=complete:tabActive=false:tabDiscarded=false" in result["error"]
    assert ":evidence=official-composer-missing:" in result["error"]
    assert result["writes"] == 0
    assert len(result["warnings"]) == 1


def test_stalled_runtime_evaluate_does_not_silently_consume_240_seconds() -> None:
    result = _scenario("stalled-evaluate")
    assert result["mounted"] is False
    assert result["now"] == 25_000
    assert result["polls"] == 0
    assert ":evidence=read-timeout:" in result["error"]
    assert result["writes"] == 0
    assert len(result["warnings"]) == 1


def test_mount_await_remains_pre_file_selection_and_protected_send() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "PR92_SCHEMA24_MOUNT_OBSERVATION_CAP_MS = 25_000" in source
    assert "_pr92Schema24WaitForOfficialComposerMounted(debuggee, context, tabId)" in source
    assert '"SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_MOUNT_READ"' in source
    assert "await _pr92BoundedSleep(" in source
    assert "button.click()" not in source
    assert "DOM.setFileInputFiles" not in source
