"""Regression for current ChatGPT's no-id multiline composer with rich inputs.

Run the *production* schema-27 evidence expression using a tiny DOM model. The
tests deliberately avoid browser traffic, file staging, and any submit action.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
EVIDENCE = EXT / "service_worker_rich_input_schema27_repair_pr9_2.js"

NODE_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const [compatFile, evidenceFile, scenario] = process.argv.slice(1);

class Element {
  constructor(attrs = {}, opts = {}) {
    this.attrs = attrs;
    this.tagName = (opts.tag || "div").toUpperCase();
    this.id = attrs.id || "";
    this.visible = opts.visible !== false;
    this.disabled = opts.disabled === true;
    this.readOnly = false;
    this.form = opts.form || null;
    this.main = opts.main || null;
    this.groups = [];
    this.textContent = "";
  }
  getAttribute(name) { return this.attrs[name] ?? null; }
  hasAttribute(name) { return Object.hasOwn(this.attrs, name); }
  getBoundingClientRect() {
    return { width: this.visible ? 100 : 0, height: this.visible ? 30 : 0 };
  }
  closest(selector) {
    if (selector === "form") return this.form;
    if (selector === "main") return this.main;
    return null;
  }
  matches(selector) {
    return selector === "textarea[placeholder]" &&
      this.tagName === "TEXTAREA" && this.hasAttribute("placeholder");
  }
  contains(other) { return this === other; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    if (selector === '[role="group"][aria-label]') return this.groups;
    return [];
  }
}

const main = new Element();
const form = new Element();
const editors = [];
function editor(attrs, opts = {}) {
  const element = new Element(attrs, {
    form: opts.noForm ? null : form,
    main: opts.noMain ? null : main,
    visible: opts.visible
  });
  editors.push(element);
  return element;
}
const modernAttrs = {
  contenteditable: "true",
  role: "textbox",
  "aria-multiline": "true"
};

if (scenario === "legacy") {
  editor({ id: "prompt-textarea", contenteditable: "true" });
} else {
  editor(modernAttrs, { noForm: scenario === "no_form" });
  if (scenario === "duplicate") editor(modernAttrs);
  if (scenario === "unrelated_visible_editor") {
    editor({ contenteditable: "true" }, { noForm: true });
  }
}
if (scenario === "stale_attachment") {
  form.groups.push(new Element({
    role: "group",
    "aria-label": "stale.txt"
  }));
}
if (scenario === "expected_attachment") {
  form.groups.push(new Element({
    role: "group",
    "aria-label": "brief.md"
  }));
}

function selectAll(selector) {
  if (selector === "#prompt-textarea") {
    return editors.filter(e => e.id === "prompt-textarea");
  }
  if (selector === '[data-testid="prompt-textarea"]') {
    return editors.filter(e => e.getAttribute("data-testid") === "prompt-textarea");
  }
  if (selector === '[contenteditable="true"][data-lexical-editor="true"]') {
    return editors.filter(e =>
      e.getAttribute("contenteditable") === "true" &&
      e.getAttribute("data-lexical-editor") === "true"
    );
  }
  if (selector === "textarea[placeholder]") {
    return editors.filter(e => e.matches(selector));
  }
  if (selector === '[contenteditable="true"]') {
    return editors.filter(e => e.getAttribute("contenteditable") === "true");
  }
  if (selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]') {
    return editors.filter(e =>
      e.getAttribute("contenteditable") === "true" &&
      e.getAttribute("role") === "textbox" &&
      e.getAttribute("aria-multiline") === "true"
    );
  }
  throw new Error("Unexpected document selector: " + selector);
}
const document = {
  querySelectorAll: selectAll,
  querySelector: selector => selectAll(selector)[0] || null
};
const context = { console };
vm.createContext(context);
vm.runInContext(fs.readFileSync(compatFile, "utf8"), context);
vm.runInContext(fs.readFileSync(evidenceFile, "utf8"), context);
const expected = scenario === "expected_attachment" ? ["brief.md"] : [];
const expression = vm.runInContext(
  "_pr92Schema27AttachmentEvidenceExpression(" +
    JSON.stringify(expected) + ")", context
);
const result = vm.runInNewContext(expression, {
  document, Element,
  getComputedStyle: () => ({
    display: "block", visibility: "visible", opacity: "1"
  })
});
console.log(JSON.stringify({
  officialComposerMounted: result.officialComposerMounted,
  exactAttachmentSet: result.exactAttachmentSet,
  groupLabelCount: result.groupLabelCount,
  removalLabelCount: result.removalLabelCount,
  evidenceKind: result.evidenceKind
}));
"""


def _evaluate(scenario: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the production-expression DOM test")
    result = subprocess.run(
        [node, "-e", NODE_HARNESS, str(COMPAT), str(EVIDENCE), scenario],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "scenario",
    ["current", "legacy", "unrelated_visible_editor"],
)
def test_recognizes_official_composer_with_no_attachment_evidence(
    scenario: str,
) -> None:
    evidence = _evaluate(scenario)
    assert evidence["officialComposerMounted"] is True
    assert evidence["exactAttachmentSet"] is True
    assert evidence["groupLabelCount"] == 0
    assert evidence["removalLabelCount"] == 0


@pytest.mark.parametrize("scenario", ["duplicate", "no_form"])
def test_ambiguous_or_unanchored_editor_is_not_attachment_authority(
    scenario: str,
) -> None:
    evidence = _evaluate(scenario)
    assert evidence["officialComposerMounted"] is False
    assert evidence["exactAttachmentSet"] is False


def test_unexpected_attachment_still_fails_clean_composer_evidence() -> None:
    evidence = _evaluate("stale_attachment")
    assert evidence["officialComposerMounted"] is True
    assert evidence["exactAttachmentSet"] is False
    assert evidence["groupLabelCount"] == 1


def test_exact_expected_attachment_group_remains_supported() -> None:
    evidence = _evaluate("expected_attachment")
    assert evidence["officialComposerMounted"] is True
    assert evidence["exactAttachmentSet"] is True
    assert evidence["groupLabelCount"] == 1


def test_compat_resolver_is_shared_without_weakening_attachment_rules() -> None:
    source = EVIDENCE.read_text(encoding="utf-8")
    assert "const structuralResolverSource = _pr117ComposerResolverSource();" in source
    assert "eligibleModernEditors.length === 1" in source
    assert "eligibleModernEditors[0] === structuralPrompt" in source
    assert "element.closest('main') instanceof Element" in source
    assert "element.closest('form') instanceof Element" in source
    assert "exactAttachmentSet = crossEvidenceChannelExact" in source
    assert "unknownRoleGroupsFailClosed: true" in source
