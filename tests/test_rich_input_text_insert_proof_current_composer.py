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
UI_COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
PAGE_TURN = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"


def _run_dom(scenario: str) -> dict[str, bool]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")

    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const code = fs.readFileSync(process.argv[1], "utf8");
const scenario = process.argv[2];
const prompt = "Inspect the attached PNG image.";
let focused = null;
class FakeElement {
  constructor(attrs) { this.attrs = attrs; this.textContent = ""; }
  get id() { return ""; }
  get disabled() { return false; }
  get readOnly() { return false; }
  get innerText() { return this.textContent; }
  getBoundingClientRect() { return {width: 100, height: 20}; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  hasAttribute(name) { return Object.hasOwn(this.attrs, name); }
  matches(_selector) { return false; }
  closest(selector) {
    if (selector === "main") return {};
    if (selector === "form") return scenario === "orphan" ? null : form;
    return null;
  }
  focus() { focused = this; }
}
const form = {};
const editor = new FakeElement({
  "contenteditable": "true",
  "role": "textbox",
  "aria-multiline": "true"
});
const document = {
  get activeElement() { return focused; },
  querySelectorAll(selector) {
    if (selector === '[contenteditable="true"]' ||
        selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]') {
      return [editor];
    }
    return [];
  }
};
const ctx = {
  document,
  Element: FakeElement,
  getComputedStyle: () => ({
    display: "block", visibility: "visible", opacity: "1"
  })
};
vm.createContext(ctx);
vm.runInContext(code, ctx);
const focusExpr = vm.runInContext("_pr117RichComposerFocusExpression()", ctx);
const focusProof = vm.runInContext(focusExpr, ctx);
if (scenario === "inserted") editor.textContent = prompt;
const proofExpr = vm.runInContext(
  "_pr117RichComposerTextProofExpression(" + JSON.stringify(prompt) + ")",
  ctx
);
const textProof = vm.runInContext(proofExpr, ctx);
console.log(JSON.stringify({focusProof, textProof}));
"""
    proc = subprocess.run(
        [node, "-e", script, str(UI_COMPAT), scenario],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("scenario,expected", [
    ("inserted", {"focusProof": True, "textProof": True}),
    ("not_inserted", {"focusProof": True, "textProof": False}),
    ("orphan", {"focusProof": False, "textProof": False}),
])
def test_rich_composer_focus_and_exact_text_proof(scenario: str, expected: dict) -> None:
    assert _run_dom(scenario) == expected


def test_rich_text_proof_must_precede_any_protected_submit() -> None:
    page = PAGE_TURN.read_text(encoding="utf-8")
    start = page.index("diagnostics.composerStrategy =")
    proof = page.index('"SCHEMA17_PAGE_TURN_TEXT_INSERT_PROOF"', start)
    submit = page.index("const submitStartedAt", proof)
    assert start < proof < submit
    assert "_pr117RequireRichInsertedTextProof(debuggee, text)" in page
    assert "CWA_RICH_COMPOSER_TEXT_NOT_INSERTED" in UI_COMPAT.read_text(
        encoding="utf-8"
    )
    assert "Input.insertText" in page
