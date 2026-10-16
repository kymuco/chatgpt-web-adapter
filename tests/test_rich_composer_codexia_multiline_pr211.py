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
UI = EXT / "service_worker_ui_compat_pr11_7.js"
NODE = shutil.which("node")

# Codexia-shaped bootstrap prompt, including blank lines, Russian, indentation
# and the three input file names. The historical Work's literal prompt is not
# available in this repository, so this is a structural regression fixture.
CODEXIA_PROMPT = (
    "[Codexia Gen2 — Delegated ChatGPT bootstrap]\n"
    "Reconstruct the state of the Gen2 work from the attached files.\n\n"
    "Files:\n"
    "- gen2_product_baseline.md\n"
    "- dw_chatgpt_bootstrap_v0.md\n"
    "- dw1_standalone_gen2_work_surface.md\n\n"
    "Ограничения:\n"
    "  - Do not execute commands.\n"
    "  - Do not create another Work.\n"
    "  - Return blockers and the next engineering step."
)

_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const ui = fs.readFileSync(process.argv[1], "utf8");
const prompt = JSON.parse(process.argv[2]);

class TextNode {
  constructor(value) {
    this.nodeType = 3;
    this.nodeValue = value;
    this.textContent = value;
  }
}
class FakeElement {
  constructor(tagName, children = [], attrs = {}) {
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.childNodes = children;
    this.attrs = attrs;
    this.id = "";
    this.disabled = false;
    this.readOnly = false;
  }
  get textContent() {
    return this.childNodes.map((n) => n.textContent || "").join("");
  }
  get innerText() {
    if (this.tagName === "DIV") {
      return this.childNodes.map((n) => n.innerText ?? n.textContent ?? "").join("\n\n");
    }
    return this.childNodes.map((n) => n.innerText ?? n.textContent ?? "").join("");
  }
  getBoundingClientRect() { return { width: 600, height: 100 }; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  hasAttribute(name) { return Object.hasOwn(this.attrs, name); }
  matches() { return false; }
  closest(selector) {
    if (selector === "main") return {};
    if (selector === "form") return {};
    return null;
  }
  focus() { active = this; }
}

const editor = new FakeElement("div", [], {
  contenteditable: "true",
  role: "textbox",
  "aria-multiline": "true"
});
let active = editor;
const document = {
  get activeElement() { return active; },
  querySelectorAll(selector) {
    if (selector === '[contenteditable="true"]' ||
        selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]') {
      return [editor];
    }
    return [];
  }
};
const context = {
  Element: FakeElement,
  document,
  getComputedStyle: () => ({
    display: "block", visibility: "visible", opacity: "1"
  })
};
vm.createContext(context);
vm.runInContext(ui, context);

function paragraphs(text) {
  return text.split("\n").map((line) =>
    new FakeElement("p", line
      ? [new FakeElement("span", [new TextNode(line)])]
      : [new FakeElement("br")])
  );
}
function check(actual, expected = prompt) {
  editor.childNodes = paragraphs(actual);
  const expr = vm.runInContext(
    "_pr117RichComposerTextObservationExpression(" +
    JSON.stringify(expected) + ")",
    context
  );
  const observation = vm.runInContext(expr, context);
  const boolExpr = vm.runInContext(
    "_pr117RichComposerTextProofExpression(" +
    JSON.stringify(expected) + ")",
    context
  );
  return { ...observation, booleanProof: vm.runInContext(boolExpr, context) };
}

const exact = check(prompt);
active = new FakeElement("button");
const focusDrift = check(prompt);
active = editor;
const crlf = check(prompt, prompt.replace(/\n/g, "\r\n"));
const omittedLine = check(prompt.replace("  - Do not create another Work.\n", ""));
const mutatedText = check(prompt.replace("blockers", "BLOCKERS"));
const extraBlankLine = check(prompt.replace("Files:\n", "Files:\n\n"));
editor.childNodes = [new FakeElement("section", paragraphs(prompt))];
const invalidShape = (() => {
  const expr = vm.runInContext(
    "_pr117RichComposerTextObservationExpression(" +
    JSON.stringify(prompt) + ")",
    context
  );
  return vm.runInContext(expr, context);
})();
console.log(JSON.stringify({
  exact, focusDrift, crlf, omittedLine, mutatedText,
  extraBlankLine, invalidShape
}));
"""


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
def test_multiline_codexia_composer_proof_is_exact_and_focus_independent() -> None:
    completed = subprocess.run(
        [NODE, "-e", _JS, str(UI), json.dumps(CODEXIA_PROMPT, ensure_ascii=False)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    for case in ("exact", "focusDrift", "crlf"):
        assert result[case]["passed"] is True, (case, result[case])
        assert result[case]["booleanProof"] is True, (case, result[case])
        assert result[case]["structuredExact"] is True
        assert result[case]["directExact"] is False
        assert result[case]["renderedExact"] is False

    assert result["exact"]["focusMatches"] is True
    assert result["focusDrift"]["focusMatches"] is False

    for case in ("omittedLine", "mutatedText", "extraBlankLine", "invalidShape"):
        assert result[case]["passed"] is False, (case, result[case])
