from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from chatgpt_web_adapter import product_rich_input_composer_diagnostic_pr9_2 as cli

EXT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
DIAGNOSTIC = EXT / "service_worker_rich_input_schema23_diagnostic_pr9_2.js"
NODE = shutil.which("node")

_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const script = fs.readFileSync(process.argv[1], "utf8");
const start = script.indexOf("async function _pr92RunSchema23ComposerDiagnostic(");
const fn = script.slice(start);
const scenario = process.argv[2];
let tabCreatedOrNavigated = 0;
let readCalls = 0;
let attachCalls = 0;
let detachCalls = 0;
const ctx = {
  performance: {now: () => 0},
  _pr92Schema7RunUntil: async (_deadline, _stage, fn) => fn(),
  storedRuntimeTabId: async () => scenario === "missing" ? null : 42,
  ensureRuntimeTab: async () => {
    tabCreatedOrNavigated++;
    throw new Error("must not open or navigate");
  },
  chrome: {
    tabs: {
      get: async id => {
        readCalls++;
        if (id !== 42) throw new Error("unexpected tab");
        return {id, url: scenario === "foreign" ? "https://example.org/" :
          "https://chatgpt.com/"};
      }
    },
    debugger: {
      sendCommand: async (_d, method) =>
        method === "Runtime.evaluate" ? {result: {value: {officialComposerMounted: true}}} : {},
    }
  },
  isChatGPTUrl: url => url.startsWith("https://chatgpt.com/"),
  _pr92Schema13AttachWithinDeadline: async () => {
    attachCalls++;
    return true;
  },
  _pr92Schema24WaitForOfficialComposerMounted: async () =>
    ({officialComposerMounted: true, exactAttachmentSet: true}),
  _pr92Schema24EvidenceIsClean: evidence =>
    evidence.officialComposerMounted === true &&
    evidence.exactAttachmentSet === true,
  _pr92BoundedSleep: async () => {},
  PR92_SCHEMA24_REPAIR_SCHEMA: 24,
  PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS: 2,
  PR92_PAGE_ATTACHMENT_POLL_MS: 150,
  _pr92ClosureReadPageOwnedAttachmentEvidence: async () =>
    ({officialComposerMounted: true, exactAttachmentSet: true}),
  _pr92Schema23DiagnosticExpression: () => "({officialComposerMounted:true})",
  _pr92Schema15DetachWithinDeadline: async () => {detachCalls++;},
  _pr92Schema23DiagnosticBestEffortDetach: () => {detachCalls++;},
};
vm.createContext(ctx);
vm.runInContext(fn, ctx);

(async () => {
  let result = null;
  let error = null;
  try {
    result = await ctx._pr92RunSchema23ComposerDiagnostic({
      existingTabOnly: true, timeoutMs: 5000
    });
  } catch (caught) {
    error = caught.message;
  }
  console.log(JSON.stringify({
    error,
    tabCreatedOrNavigated,
    readCalls,
    attachCalls,
    detachCalls,
    diagnosticOnly: result?.diagnosticOnly ?? null,
    writePerformed: result?.writePerformed ?? null,
    protectedSubmitAttempted: result?.protectedSubmitAttempted ?? null
  }));
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
@pytest.mark.parametrize(
    ("scenario", "expected_error"),
    [
        ("existing", None),
        ("missing", "PR9_2_DIAGNOSTIC_NO_OWNED_RUNTIME_TAB"),
        ("foreign", "PR9_2_DIAGNOSTIC_OWNED_TAB_NOT_CHATGPT"),
    ],
)
def test_existing_only_diagnostic_never_creates_or_navigates_tab(
    scenario: str, expected_error: str | None
) -> None:
    proc = subprocess.run(
        [NODE, "-e", _JS, str(DIAGNOSTIC), scenario],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=8,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["tabCreatedOrNavigated"] == 0
    assert result["error"] == expected_error
    if expected_error is None:
        assert result["readCalls"] == 1
        assert result["attachCalls"] == 1
        assert result["detachCalls"] == 1
        assert result["diagnosticOnly"] is True
        assert result["writePerformed"] is False
        assert result["protectedSubmitAttempted"] is False
    else:
        assert result["attachCalls"] == 0
        assert result["detachCalls"] == 0
        assert result["readCalls"] == int(scenario == "foreign")


def test_existing_tab_only_cli_passes_explicit_flag_without_write(monkeypatch):
    class FakeProvider:
        calls = []

        def _rpc(self, message, *, timeout):
            self.calls.append(message)
            return {
                "ok": True,
                "request_id": message["request_id"],
                "diagnosticOnly": True,
                "writePerformed": False,
                "attachmentStagingPerformed": False,
                "protectedSubmitAttempted": False,
                "richInputSchemaVersion": 24,
                "productionCleanProof": {"allPollsClean": True},
            }

    provider = FakeProvider()
    monkeypatch.setattr(cli, "ProductRichInputSchema24LiveProvider", lambda: provider)

    report = cli.run_diagnostic(timeout=10.0, existing_tab_only=True)

    assert report["existing_tab_only"] is True
    assert len(provider.calls) == 1
    message = provider.calls[0]
    assert message["existingTabOnly"] is True
    assert message["timeoutMs"] == 7000
    assert "text" not in message
    assert "attachmentPaths" not in message
