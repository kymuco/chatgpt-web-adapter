from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
TEXT_HARDENING = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"
LIVENESS = EXT / "service_worker_ui_liveness.js"


def test_compatibility_pack_is_shared_discovery_not_new_authority_layer() -> None:
    source = COMPAT.read_text(encoding="utf-8")

    assert "PR117_UI_COMPAT_SCHEMA = 1" in source
    assert '[contenteditable="true"]' in source
    assert "structuralGenericEvidence" in source
    assert "genericOnly && !structuralGenericEvidence(element)" in source
    assert "element.getAttribute('role') === 'textbox'" in source
    assert "element.getAttribute('aria-multiline') === 'true'" in source
    assert "element.closest('form')" in source
    assert "candidates.length !== 1" in source
    assert "pr11_7_structural_submit_control" in source

    for forbidden in (
        "submitOfficialPageTurn =",
        "executeNativeTurn =",
        "onNativeMessage =",
        "Input.dispatchKeyEvent",
        "Input.dispatchMouseEvent",
        "Input.insertText",
        "DOM.setFileInputFiles",
        "chrome.tabs.create",
        "chrome.tabs.update",
        "fetch(",
    ):
        assert forbidden not in source


def test_compatibility_pack_loads_after_rich_authority_before_text_hardening() -> None:
    loader = LOADER.read_text(encoding="utf-8")
    rich = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    compat = 'importScripts("service_worker_ui_compat_pr11_7.js");'
    hardening = 'importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");'
    observation = 'importScripts("service_worker_product_source_citations_pr9_3.js");'

    assert loader.index(rich) < loader.index(compat) < loader.index(hardening)
    assert loader.index(hardening) < loader.index(observation)


def test_existing_consumers_use_shared_compatibility_without_changing_ownership() -> None:
    hardening = TEXT_HARDENING.read_text(encoding="utf-8")
    liveness = LIVENESS.read_text(encoding="utf-8")

    assert "_pr117LocateAndFocusComposer" in hardening
    assert "_pr117WaitForSendButtonPoint" in hardening
    assert "_pr92ActiveRichInputContext" in hardening
    assert "_pr813TemporaryTurnContext" in hardening
    assert "_pr117QueryComposerReadiness(debuggee)" in liveness
    assert "executeNativeTurn =" not in liveness


def _run_node_scenario(tmp_path: Path, scenario: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; source-contract tests remain active")

    harness = tmp_path / f"pr11_7_{scenario}.js"
    harness.write_text(
        """
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const scenario = process.argv[3];
const log = [];
let now = 0;

const context = {
  console,
  Number,
  Error,
  Promise,
  performance: { now: () => now },
  DEFAULT_SUBMIT_READY_TIMEOUT_MS: 1000,
  elapsedMs: (startedAt) => now - startedAt,
  sleep: async (ms) => { now += ms; },
  queryComposerReadiness: async () => {
    log.push("historical_readiness");
    if (scenario === "historical_ready") return { ready: true, reason: "ready" };
    return { ready: false, reason: "composer_missing" };
  },
  locateAndFocusComposer: async () => {
    log.push("historical_focus");
    if (scenario === "focus_fallback") throw new Error("historical-miss");
    return "historical";
  },
  querySendButtonPoint: async () => {
    log.push("historical_submit_point");
    if (scenario === "historical_submit") {
      return { x: 4, y: 5, selector: "historical" };
    }
    return null;
  },
  sendCommand: async (_debuggee, method, params) => {
    log.push(`compat:${method}`);
    const expression = String(params?.expression || "");
    if (scenario === "focus_fallback") {
      return { result: { value: true } };
    }
    if (scenario === "structural_submit") {
      return {
        result: {
          value: { x: 10, y: 20, selector: "pr11_7_structural_submit_control" }
        }
      };
    }
    return { result: { value: { ready: true, reason: "ready" } } };
  }
};
context.globalThis = context;
vm.createContext(context);
vm.runInContext(
  source + `\n;globalThis.__exports = {\n` +
    `queryReadiness: _pr117QueryComposerReadiness,\n` +
    `focusComposer: _pr117LocateAndFocusComposer,\n` +
    `querySubmitPoint: _pr117QuerySendButtonPoint\n` +
  `};`,
  context
);

(async () => {
  let result;
  if (scenario === "historical_ready" || scenario === "structural_readiness") {
    result = await context.__exports.queryReadiness({});
  } else if (scenario === "focus_fallback") {
    result = await context.__exports.focusComposer({});
  } else {
    result = await context.__exports.querySubmitPoint({});
  }
  console.log(JSON.stringify({ result, log }));
})();
""".strip()
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(harness), str(COMPAT), scenario],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_historical_composer_evidence_short_circuits_compatibility_probe(
    tmp_path: Path,
) -> None:
    result = _run_node_scenario(tmp_path, "historical_ready")

    assert result["result"] == {"ready": True, "reason": "ready"}
    assert result["log"] == ["historical_readiness"]


def test_composer_missing_uses_one_bounded_structural_probe(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "structural_readiness")

    assert result["result"] == {"ready": True, "reason": "ready"}
    assert result["log"] == ["historical_readiness", "compat:Runtime.evaluate"]


def test_historical_submit_control_short_circuits_structural_fallback(
    tmp_path: Path,
) -> None:
    result = _run_node_scenario(tmp_path, "historical_submit")

    assert result["result"] == {"x": 4, "y": 5, "selector": "historical"}
    assert result["log"] == ["historical_submit_point"]


def test_structural_submit_fallback_requires_explicit_compatibility_probe(
    tmp_path: Path,
) -> None:
    result = _run_node_scenario(tmp_path, "structural_submit")

    assert result["result"] == {
        "x": 10,
        "y": 20,
        "selector": "pr11_7_structural_submit_control",
    }
    assert result["log"] == ["historical_submit_point", "compat:Runtime.evaluate"]


def test_focus_fallback_runs_only_after_historical_discovery_failure(
    tmp_path: Path,
) -> None:
    result = _run_node_scenario(tmp_path, "focus_fallback")

    assert result["result"] == "pr11_7_structural_dom_fallback"
    assert result["log"] == ["historical_focus", "compat:Runtime.evaluate"]
