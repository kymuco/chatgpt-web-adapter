from __future__ import annotations

import shutil
import subprocess

import pytest

from chatgpt_web_adapter.browser_native_install import (
    packaged_browser_native_extension_dir,
)


NODE = shutil.which("node")

_JS = r"""
const assert = require("node:assert/strict");

const source = process.argv[1];
const scenario = process.argv[2];
const tabId = 73;
let status = "loading";
let reads = 0;
const listeners = new Set();

const chrome = {
  tabs: {
    get: async (id) => {
      assert.equal(id, tabId);
      reads += 1;
      if (scenario === "completed-between-read-and-subscribe" && reads === 1) {
        // Return the old state even though Chrome has already finished loading.
        status = "complete";
        return { id, status: "loading" };
      }
      return { id, status };
    },
    onUpdated: {
      addListener: (listener) => listeners.add(listener),
      removeListener: (listener) => listeners.delete(listener)
    }
  }
};

const waitForTab = new Function(
  "chrome",
  "setTimeout",
  "clearTimeout",
  source + "\nreturn _cwaBaseWaitForTabComplete;"
)(chrome, setTimeout, clearTimeout);

(async () => {
  if (scenario === "normal-event") {
    setTimeout(() => {
      status = "complete";
      for (const listener of [...listeners]) {
        listener(tabId, { status: "complete" });
      }
    }, 5);
  }
  if (scenario === "already-complete") status = "complete";
  if (scenario === "timeout") {
    await assert.rejects(
      waitForTab(tabId, 30),
      /CHATGPT_RUNTIME_TAB_LOAD_TIMEOUT/
    );
  } else {
    const result = await waitForTab(tabId, 100);
    assert.equal(result.status, "complete");
  }
  assert.equal(listeners.size, 0, "listener must be released");
  console.log("PASS");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    "scenario",
    [
        "completed-between-read-and-subscribe",
        "normal-event",
        "already-complete",
        "timeout",
    ],
)
def test_runtime_tab_load_wait_handles_completion_races(scenario: str) -> None:
    root = packaged_browser_native_extension_dir()
    source = (root / "service_worker.js").read_text(encoding="utf-8")
    start = source.index("async function _cwaBaseWaitForTabComplete(")
    end = source.index("async function _cwaBaseStoredRuntimeTabId(", start)
    function_source = source[start:end]

    completed = subprocess.run(
        [NODE, "-e", _JS, function_source, scenario],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout
