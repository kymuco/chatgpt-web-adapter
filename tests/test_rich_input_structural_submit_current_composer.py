from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
ATOMIC = EXT / "service_worker_rich_input_schema7_core_pr9_2.js"
READINESS = EXT / "service_worker_rich_input_schema12_repair_pr9_2.js"


def _simulate(scenario: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")

    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const compat = fs.readFileSync(process.argv[1], "utf8");
const atomic = fs.readFileSync(process.argv[2], "utf8");
const scenario = process.argv[3];
let clicked = 0;

class FakeElement {
  constructor(attrs = {}) { this.attrs = attrs; this.disabled = scenario === "disabled"; }
  get id() { return ""; }
  get readOnly() { return false; }
  getBoundingClientRect() { return {width: 100, height: 22, left: 6, top: 5}; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  hasAttribute(name) { return Object.hasOwn(this.attrs, name); }
  matches(_selector) { return false; }
  closest(selector) {
    if (selector === "main") return main;
    if (selector === "form") return scenario === "orphan_editor" ? null : form;
    return null;
  }
  querySelectorAll(_selector) {
    return scenario === "ambiguous" ? [button, secondButton] : [button];
  }
  click() { clicked++; }
}
const main = new FakeElement();
const form = new FakeElement();
const editor = new FakeElement({
  "role": "textbox",
  "contenteditable": "true",
  "aria-multiline": "true"
});
const button = new FakeElement({"type": "submit"});
const secondButton = new FakeElement({"type": "submit"});
const document = {
  querySelectorAll(selector) {
    if (selector === '[contenteditable="true"]' ||
        selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]')
      return [editor];
    return [];
  },
  querySelector(_selector) { return null; }
};
const scope = {
  console,
  Element: FakeElement,
  HTMLElement: FakeElement,
  document,
  getComputedStyle: () => ({
    display: "block",
    visibility: "visible",
    opacity: "1",
    pointerEvents: "auto"
  }),
  DEFAULT_SUBMIT_ACK_TIMEOUT_MS: 1000,
  _pr92ClosureAttachmentEvidenceExpression: (names) =>
    "({ready: " + (scenario !== "missing_attachment") +
    ", rejected: false, matchedCount: " +
    (scenario === "missing_attachment" ? 0 : names.length) + "})"
};
vm.createContext(scope);
vm.runInContext(compat + "\n" + atomic, scope);
const pointExpr = vm.runInContext("_pr117StructuralSubmitPointExpression()", scope);
const point = vm.runInContext(pointExpr, scope);
const atomicExpr = vm.runInContext(
  "_pr92Schema7BaseAtomicAttachmentSubmitExpression(" +
  "'pr11_7_structural_submit_control', Date.now() + 10000, ['a.png'])",
  scope
);
const result = vm.runInContext(atomicExpr, scope);
console.log(JSON.stringify({ point, result, clicked }));
"""
    completed = subprocess.run(
        [node, "-e", script, str(COMPAT), str(ATOMIC), scenario],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_current_generic_chatgpt_composer_has_one_atomic_rich_submit() -> None:
    proof = _simulate("ready")
    assert proof["point"]["selector"] == "pr11_7_structural_submit_control"
    assert proof["result"]["clicked"] is True
    assert proof["result"]["matchedCount"] == 1
    assert proof["clicked"] == 1


@pytest.mark.parametrize(
    "case", ["ambiguous", "disabled", "orphan_editor", "missing_attachment"]
)
def test_atomic_rich_submit_fails_closed_without_unique_authorized_button(
    case: str,
) -> None:
    proof = _simulate(case)
    assert proof["result"]["clicked"] is False
    assert proof["clicked"] == 0


def test_rich_readiness_uses_same_structural_fallback_with_outer_deadline() -> None:
    code = READINESS.read_text(encoding="utf-8")
    assert '"SCHEMA12_SEND_READINESS_WAIT"' in code
    assert "_pr92Schema7RunUntil(" in code
    assert "() => _pr117WaitForSendButtonPoint(debuggee, timeoutMs)" in code


def test_atomic_page_click_reuses_pr117_resolver_without_retry_or_raw_mouse() -> None:
    code = ATOMIC.read_text(encoding="utf-8")
    assert "_pr117StructuralSubmitButtonResolverSource()" in code
    assert "button.click();" in code
    assert "PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS" in code
    assert "Input.dispatchMouseEvent" not in code
