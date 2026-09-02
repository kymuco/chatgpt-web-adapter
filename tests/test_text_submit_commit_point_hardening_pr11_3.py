from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OVERLAY = EXTENSION / "service_worker_text_submit_commit_hardening_pr11_3.js"
LOADER = EXTENSION / "service_worker_rich_input_schema7_repair_pr9_2.js"


def test_text_submit_hardening_loads_after_rich_authority_before_observation_layers() -> None:
    text = LOADER.read_text(encoding="utf-8")
    rich = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    hardening = 'importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");'
    observation = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    canonical_read = 'importScripts("service_worker_canonical_read.js");'

    assert text.index(rich) < text.index(hardening) < text.index(observation)
    assert text.index(hardening) < text.index(canonical_read)


def test_text_submit_hardening_declares_exact_protected_boundaries() -> None:
    text = OVERLAY.read_text(encoding="utf-8")

    assert 'PR11_3_TEXT_MOUSE_RELEASE_OUTCOME_UNCONFIRMED' in text
    assert 'type: "mouseReleased"' in text
    assert 'type: "keyDown"' in text
    assert 'type: "keyUp"' in text
    assert "_pr113IsMouseReleaseOutcomeUnconfirmed(error)" in text
    assert "_pr813TemporaryTurnContext" in text
    assert "_pr92ActiveRichInputContext" in text
    assert "throw error;" in text
    assert "return _pr113SubmitTextWithEnterOnce(debuggee);" in text
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

async function submitOfficialPageTurn() {
  log.push("prior_submit");
  return { strategy: "prior_specialized", selector: null };
}

async function waitForSendButtonPoint() {
  log.push("wait_button");
  if (scenario === "wait_fail" || scenario === "enter_keyup_fail" || scenario === "enter_keydown_fail") {
    throw new Error("button-not-ready");
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
    const result = await submitOfficialPageTurn({}, 1000);
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


def test_successful_click_uses_one_mouse_commit_and_no_enter(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "success")

    assert result["ok"] is True
    assert result["result"] == {
        "strategy": "send_button_click",
        "selector": "send-selector",
    }
    assert len(_enter_keydowns(result["log"])) == 0
    assert sum("mouseReleased" in item for item in result["log"]) == 1


def test_enter_keyup_failure_is_post_commit_cleanup_only(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "enter_keyup_fail")

    assert result["ok"] is True
    assert result["result"]["strategy"] == "enter_fallback"
    assert len(_enter_keydowns(result["log"])) == 1


def test_enter_keydown_failure_propagates_without_second_submit(tmp_path: Path) -> None:
    result = _run_node_scenario(tmp_path, "enter_keydown_fail")

    assert result["ok"] is False
    assert result["error"] == "enter-keydown-failed"
    assert len(_enter_keydowns(result["log"])) == 1


@pytest.mark.parametrize("scenario", ["rich", "temporary"])
def test_specialized_submit_contexts_delegate_to_existing_authority_chain(
    tmp_path: Path,
    scenario: str,
) -> None:
    result = _run_node_scenario(tmp_path, scenario)

    assert result["ok"] is True
    assert result["result"]["strategy"] == "prior_specialized"
    assert result["log"] == ["prior_submit"]
