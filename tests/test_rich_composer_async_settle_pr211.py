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

# Use a multiline, non-ASCII Codexia-shaped work request to expose the
# Lexical paragraph and asynchronous render paths. No literal WorkStore prompt
# is available to this regression test.
PROMPT = "Codexia Gen2\n\nПрочитай три файла:\n- one.md\n- two.md\n- three.md"

_JS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const prompt = JSON.parse(process.argv[2]);
const scenario = process.argv[3];

let reads = 0;
let fakeTime = 0;
let focused = null;
const calls = [];
const warnings = [];
const textNode = (text) => ({nodeType: 3, nodeValue: text, textContent: text});
class Element {
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
    return this.childNodes.map(node => node.textContent || "").join("");
  }
  get innerText() {
    return this.childNodes.map(node => node.innerText ?? node.textContent ?? "").join(
      this.tagName === "DIV" ? "\n\n" : ""
    );
  }
  getAttribute(key) { return this.attrs[key] ?? null; }
  hasAttribute(key) { return Object.hasOwn(this.attrs, key); }
  getBoundingClientRect() { return {width: 450, height: 45}; }
  closest(selector) { return selector === "main" || selector === "form" ? {} : null; }
  matches() { return false; }
  focus() { focused = this; }
}
const editor = new Element("div", [], {
  contenteditable: "true",
  role: "textbox",
  "aria-multiline": "true",
});
focused = editor;
function fill(value) {
  editor.childNodes = value.split("\n").map(line => new Element(
    "p", line ? [new Element("span", [textNode(line)])] : [new Element("br")]
  ));
}
function shouldBeExact(read) {
  if (scenario === "delayed") return read >= 4;
  if (scenario === "transient") return read === 1 || read >= 4;
  if (scenario === "persistentMismatch") return false;
  return true;
}
const document = {
  get activeElement() {
    return scenario === "focusMoved" ? null : focused;
  },
  querySelectorAll(selector) {
    if (selector === '[contenteditable="true"]' ||
        selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]') {
      return [editor];
    }
    return [];
  },
};
const context = {
  document,
  Element,
  getComputedStyle: () => ({
    display: "block", visibility: "visible", opacity: "1"
  }),
  performance: {now: () => fakeTime},
  sleep: async duration => {
    fakeTime += duration;
  },
  console: {warn: (...args) => warnings.push(args)},
  async sendCommand(_debuggee, command, args) {
    calls.push(command);
    if (command !== "Runtime.evaluate") throw new Error("unexpected command");
    reads += 1;
    fill(shouldBeExact(reads) ? prompt : prompt.replace("two.md", "TWO.md"));
    return {result: {value: vm.runInContext(args.expression, context)}};
  },
};
vm.createContext(context);
vm.runInContext(source, context);
(async () => {
  try {
    const result = await context._pr117RequireRichInsertedTextProof(
      {tabId: 73}, prompt
    );
    console.log(JSON.stringify({
      result,
      reads,
      fakeTime,
      calls,
      warnings: warnings.length
    }));
  } catch (error) {
    console.log(JSON.stringify({
      error: error.message,
      reads,
      fakeTime,
      calls,
      warnings: warnings.length,
      warningMetadata: warnings[0]?.[1] || null
    }));
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
@pytest.mark.parametrize(
    ("scenario", "expected_reads"),
    [
        ("immediate", 2),
        ("delayed", 5),
        ("transient", 5),
        ("focusMoved", 2),
    ],
)
def test_multiline_rich_proof_waits_for_two_stable_exact_observations(
    scenario: str, expected_reads: int
) -> None:
    proc = subprocess.run(
        [NODE, "-e", _JS, str(UI), json.dumps(PROMPT, ensure_ascii=False), scenario],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["result"] is True
    assert result["reads"] == expected_reads
    assert result["calls"] == ["Runtime.evaluate"] * expected_reads
    assert result["warnings"] == 0


@pytest.mark.skipif(NODE is None, reason="Node.js unavailable")
def test_persistent_rich_mismatch_fails_before_any_write_with_bounded_evidence() -> None:
    proc = subprocess.run(
        [
            NODE,
            "-e",
            _JS,
            str(UI),
            json.dumps(PROMPT, ensure_ascii=False),
            "persistentMismatch",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["error"] == "CWA_RICH_COMPOSER_TEXT_NOT_INSERTED"
    assert result["fakeTime"] == 15000
    assert result["calls"] == ["Runtime.evaluate"] * result["reads"]
    assert result["warnings"] == 1
    assert result["warningMetadata"]["composerFound"] is True
    assert result["warningMetadata"]["structuredExact"] is False
    assert result["warningMetadata"]["attemptedStableReads"] == 0


def test_proof_never_reinserts_or_invokes_submit() -> None:
    source = UI.read_text(encoding="utf-8")
    start = source.index("async function _pr117RequireRichInsertedTextProof")
    end = source.index("function _pr117StructuralSubmitButtonResolverSource", start)
    helper = source[start:end]
    assert "Input.insertText" not in helper
    assert "submitOfficialPageTurn" not in helper
    assert "Runtime.evaluate" in helper
    assert "consecutiveExact >= 2" in helper
