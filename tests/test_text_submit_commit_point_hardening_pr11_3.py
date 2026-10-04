from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OVERLAY = EXTENSION / "service_worker_text_submit_commit_hardening_pr11_3.js"
SCHEMA_LOADER = EXTENSION / "service_worker_rich_input_schema7_repair_pr9_2.js"
WRITE = EXTENSION / "service_worker_runtime_write.js"
READ = EXTENSION / "service_worker_runtime_read.js"
RUNTIME = EXTENSION / "service_worker_runtime.js"


def test_text_submit_hardening_loads_after_rich_authority_before_observation_layers() -> (
    None
):
    schema_loader = SCHEMA_LOADER.read_text(encoding="utf-8")
    write = WRITE.read_text(encoding="utf-8")
    read = READ.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    rich = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    hardening = (
        'importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");'
    )
    observation = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    canonical_read = 'importScripts("service_worker_canonical_read_v2.js");'

    assert rich in schema_loader
    assert hardening in write
    assert read.index(observation) < read.index(canonical_read)
    assert runtime.index(
        'importScripts("service_worker_runtime_write.js");'
    ) < runtime.index('importScripts("service_worker_runtime_read.js");')


def test_text_submit_hardening_declares_exact_protected_boundaries() -> None:
    text = OVERLAY.read_text(encoding="utf-8")

    assert "PR11_3_TEXT_MOUSE_RELEASE_OUTCOME_UNCONFIRMED" in text
    assert "PR11_3_TEXT_ENTER_KEYDOWN_OUTCOME_UNCONFIRMED" in text
    assert 'type: "mouseReleased"' in text
    assert 'type: "keyDown"' in text
    assert 'type: "keyUp"' in text
    assert "_pr113IsMouseReleaseOutcomeUnconfirmed(error)" in text
    assert "_pr813TemporaryTurnContext" in text
    assert "_pr92ActiveRichInputContext" in text
    assert "throw error;" in text
    assert "return _pr113SubmitTextWithEnterOnce(debuggee);" in text
    assert "_pr113RuntimeTabActive" in text
    assert "_pr113EnableBackgroundKeyboardFocus" in text
    assert "_pr113DisableBackgroundKeyboardFocus" in text
    assert "Emulation.setFocusEmulationEnabled" in text
    assert "PR11_3_BACKGROUND_FOCUS_EMULATION_NOT_PROVEN" in text
    assert "PR11_3_MOUSE_COMMIT_REQUIRES_ALREADY_ACTIVE_TAB" in text
    assert "chrome.tabs.update" not in text
    assert text.index("throw error;") < text.rindex(
        "return _pr113SubmitTextWithEnterOnce(debuggee);"
    )


def _run_node_scenario(tmp_path: Path, scenario: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; source-contract tests remain active")

    harness = tmp_path / f"pr11_3_{scenario}.js"
    harness.write_text(
        """
const fs = require("fs");
const overlaySource = fs.readFileSync(process.argv[2], "utf8");
const scenario = process.argv[3];
const log = [];
let _pr92ActiveRichInputContext = null;
let _pr813TemporaryTurnContext = null;
const DEFAULT_SUBMIT_READY_TIMEOUT_MS = 10000;
const runtimeActive = ["already_active", "move_fail", "press_fail", "release_fail"].includes(
  scenario
);
const tabState = new Map([
  [66, { id: 66, active: !runtimeActive, windowId: 1 }],
  [77, { id: 77, active: runtimeActive, windowId: 1 }]
]);
const chrome = {
  tabs: {
    get: async (tabId) => ({ ...tabState.get(tabId) }),
    query: async ({ active, windowId }) => Array.from(tabState.values())
      .filter((tab) => (
        (active !== true || tab.active === true) &&
        (!Number.isInteger(windowId) || tab.windowId === windowId)
      ))
      .map((tab) => ({ ...tab })),
    update: async (tabId, patch) => {
      const target = tabState.get(tabId);
      if (!target) throw new Error("tab-missing");
      if (patch?.active === true) {
        for (const tab of tabState.values()) {
          if (tab.windowId === target.windowId) tab.active = false;
        }
        target.active = true;
        log.push(`tabs.update:${tabId}:active=true`);
      }
      return { ...target };
    }
  }
};

async function submitOfficialPageTurn() {
  log.push("prior_submit");
  return { strategy: "prior_specialized", selector: null };
}

let waitButtonCalls = 0;
async function waitForSendButtonPoint() {
  log.push("wait_button");
  waitButtonCalls += 1;
  if (scenario === "wait_fail" || scenario === "enter_keyup_fail" || scenario === "enter_keydown_fail") {
    throw new Error("button-not-ready");
  }
  if (scenario === "success" && waitButtonCalls >= 2) {
    return { x: 13, y: 24, selector: "send-selector" };
  }
  return { x: 10, y: 20, selector: "send-selector" };
}

async function locateAndFocusComposer() {
  log.push("focus_composer");
  return "test";
}

async function sendCommand(_debuggee, method, params) {
  const marker = `${method}:${params?.type || "none"}:${params?.key || "none"}`;
  log.push(marker);
  if (method === "Emulation.setFocusEmulationEnabled") {
    log.push(`focus_emulation:${params?.enabled === true}`);
    return {};
  }
  if (
    method === "Runtime.evaluate" &&
    String(params?.expression || "").includes("document.hasFocus()")
  ) {
    return { result: { value: { hasFocus: true } } };
  }
  if (method === "Input.dispatchMouseEvent") {
    log.push(`mouse_point:${params?.x}:${params?.y}`);
  }
  if (scenario === "move_fail" && params?.type === "mouseMoved") {
    throw new Error("move-failed");
  }
  if (scenario === "press_fail" && params?.type === "mousePressed") {
    throw new Error("press-failed");
  }
  if (scenario === "release_fail" && params?.type === "mouseReleased") {
    throw new Error("release-ack-lost");
  }
  if (scenario === "enter_keydown_fail" && params?.type === "keyDown" && params?.key === "Enter") {
    throw new Error("enter-keydown-failed");
  }
  if (scenario === "enter_keyup_fail" && params?.type === "keyUp" && params?.key === "Enter") {
    throw new Error("enter-keyup-failed");
  }
  return {};
}

eval(overlaySource);
if (scenario === "rich") {
  _pr92ActiveRichInputContext = { staged: true };
}
if (scenario === "temporary") {
  _pr813TemporaryTurnContext = { tabId: 77 };
}

(async () => {
  try {
    const result = await _pr113SubmitOfficialTextWithoutPostCommitRetry(\n      { tabId: 77 },\n      1000,\n      submitOfficialPageTurn\n    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    console.log(JSON.stringify({ ok: true, result, log }));
  } catch (error) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    console.log(JSON.stringify({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      log
    }));
  }
})();
""".strip()
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(harness), str(OVERLAY), scenario],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _enter_keydowns(log: list[str]) -> list[str]:
    return [item for item in log if item.endswith(":keyDown:Enter")]


def test_pre_commit_failures_allow_exactly_one_enter_fallback(tmp_path: Path) -> None:
    for scenario in ("wait_fail", "move_fail", "press_fail"):
        result = _run_node_scenario(tmp_path, scenario)
        assert result["ok"] is True, scenario
        assert result["result"]["strategy"] == "enter_fallback", scenario
        assert len(_enter_keydowns(result["log"])) == 1, scenario


def test_mouse_release_ack_loss_never_authorizes_enter_retry(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "release_fail")

    assert result["ok"] is False
    assert result["error"] == "PR11_3_TEXT_MOUSE_RELEASE_OUTCOME_UNCONFIRMED"
    assert len(_enter_keydowns(result["log"])) == 0
    assert sum("mouseReleased" in item for item in result["log"]) == 1


def test_already_active_tab_uses_one_mouse_commit_and_no_enter(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "already_active")

    assert result["ok"] is True
    assert result["result"] == {
        "strategy": "send_button_click",
        "selector": "send-selector",
    }
    assert not any(item.startswith("tabs.update:") for item in result["log"])
    assert result["log"].count("wait_button") == 1
    assert not any(item.startswith("focus_emulation:") for item in result["log"])
    assert "mouse_point:10:20" in result["log"]
    assert len(_enter_keydowns(result["log"])) == 0
    assert sum("mouseReleased" in item for item in result["log"]) == 1


def test_background_tab_uses_enter_with_focus_emulation_without_activation(
    tmp_path: Path,
) -> None:
    result = _run_node_scenario(tmp_path, "success")

    assert result["ok"] is True
    assert result["result"]["strategy"] == "enter_fallback"
    assert result["result"]["backgroundFocusEmulationAttempted"] is True
    assert result["result"]["backgroundFocusEmulationProven"] is True
    assert result["result"]["backgroundFocusEmulationRestored"] is True
    assert not any(item.startswith("tabs.update:") for item in result["log"])
    assert result["log"].count("wait_button") == 0
    assert len(_enter_keydowns(result["log"])) == 1
    assert not any("Input.dispatchMouseEvent" in item for item in result["log"])
    assert result["log"].count("focus_emulation:true") == 1
    assert result["log"].count("focus_emulation:false") == 1
    assert result["log"].index("focus_emulation:true") < result["log"].index(
        "focus_composer"
    )
    assert result["log"].index("focus_composer") < next(
        index
        for index, item in enumerate(result["log"])
        if item.endswith(":keyDown:Enter")
    )


def test_enter_keyup_failure_is_post_commit_cleanup_only(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "enter_keyup_fail")

    assert result["ok"] is True
    assert result["result"]["strategy"] == "enter_fallback"
    assert len(_enter_keydowns(result["log"])) == 1


def test_enter_keydown_ack_loss_is_ambiguous_and_never_retries(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "enter_keydown_fail")

    assert result["ok"] is False
    assert result["error"] == "PR11_3_TEXT_ENTER_KEYDOWN_OUTCOME_UNCONFIRMED"
    assert len(_enter_keydowns(result["log"])) == 1
    assert result["log"].count("focus_emulation:true") == 1
    assert result["log"].count("focus_emulation:false") == 1


@pytest.mark.parametrize("scenario", ["rich", "temporary"])
def test_specialized_submit_contexts_delegate_to_existing_authority_chain(
    tmp_path: Path,
    scenario: str,
) -> None:
    result = _run_node_scenario(tmp_path, scenario)

    assert result["ok"] is True
    assert result["result"]["strategy"] == "prior_specialized"
    assert result["log"] == ["prior_submit"]
