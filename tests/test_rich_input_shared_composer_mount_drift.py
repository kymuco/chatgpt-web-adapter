from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
RICH = EXT / "service_worker_rich_input_schema27_repair_pr9_2.js"


def _run_case(case: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")

    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const compatCode = fs.readFileSync(process.argv[1], "utf8");
const richCode = fs.readFileSync(process.argv[2], "utf8");
const variant = process.argv[3];

class FakeElement {
  constructor(props = {}) { this.props = props; }
  get id() { return this.props.id || ""; }
  get disabled() { return false; }
  get readOnly() { return false; }
  getBoundingClientRect() { return { width: 100, height: 24 }; }
  hasAttribute(name) { return name === "contenteditable" && !!this.props.editable; }
  getAttribute(name) { return this.props.attrs?.[name] ?? null; }
  matches(selector) { return selector === "textarea[placeholder]" && !!this.props.textarea; }
  closest(selector) {
    if (selector === "form") return this.props.hasForm === false ? null : form;
    if (selector === "main") return main;
    if (selector === '[data-testid*="composer"]') return this.props.composerScope ? form : null;
    return null;
  }
  contains(_element) { return false; }
  querySelector(_selector) { return null; }
  querySelectorAll(selector) {
    if (selector === '[role="group"][aria-label]' && variant === "unexpected_chip") {
      return [group];
    }
    return [];
  }
}

const main = new FakeElement();
const form = new FakeElement();
const group = new FakeElement({attrs: {"aria-label": "unexpected.txt"}});
const attrs = variant === "legacy"
  ? {"contenteditable": "true", role: "textbox", "aria-multiline": "true"}
  : variant === "unrelated_editor"
    ? {"contenteditable": "true"}
    : {
        "contenteditable": "true",
        "data-lexical-editor": "true",
        role: "textbox",
        "aria-multiline": "true"
      };
const editor = new FakeElement({
  id: variant === "legacy" ? "prompt-textarea" : "",
  attrs,
  editable: true,
  hasForm: variant !== "orphan_editor"
});

const document = {
  querySelectorAll(selector) {
    if (selector === "#prompt-textarea") {
      return editor.id === "prompt-textarea" ? [editor] : [];
    }
    if (selector === '[contenteditable="true"][data-lexical-editor="true"]') {
      return attrs["data-lexical-editor"] === "true" ? [editor] : [];
    }
    if (selector === '[contenteditable="true"]') return [editor];
    if (selector === "textarea[placeholder]") return [];
    if (selector === '[contenteditable="true"][role="textbox"][aria-multiline="true"]') {
      return attrs.role === "textbox" && attrs["aria-multiline"] === "true" ? [editor] : [];
    }
    return [];
  }
};

const scope = {
  console,
  document,
  Element: FakeElement,
  getComputedStyle: () => ({
    display: "block", visibility: "visible", opacity: "1"
  })
};
vm.createContext(scope);
vm.runInContext(compatCode + "\n" + richCode, scope);
const expr = vm.runInContext(
  "_pr92Schema27AttachmentEvidenceExpression([])", scope
);
const evidence = vm.runInContext(expr, scope);
console.log(JSON.stringify({
  mounted: evidence.officialComposerMounted,
  clean: evidence.exactAttachmentSet,
  groupCount: evidence.groupLabelCount,
  kind: evidence.evidenceKind
}));
"""
    result = subprocess.run(
        [node, "-e", script, str(COMPAT), str(RICH), case],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("variant", ["legacy", "modern_lexical"])
def test_current_and_historical_official_composer_are_mounted_and_clean(
    variant: str,
) -> None:
    evidence = _run_case(variant)
    assert evidence["mounted"] is True
    assert evidence["clean"] is True
    assert evidence["groupCount"] == 0


@pytest.mark.parametrize("variant", ["orphan_editor", "unrelated_editor"])
def test_editor_without_authoritative_composer_is_not_mount_proof(variant: str) -> None:
    evidence = _run_case(variant)
    assert evidence["mounted"] is False
    assert evidence["clean"] is False


def test_unexpected_attachment_chip_still_fails_closed() -> None:
    evidence = _run_case("unexpected_chip")
    assert evidence["mounted"] is True
    assert evidence["clean"] is False
    assert evidence["groupCount"] == 1


def test_rich_input_uses_existing_shared_composer_resolver() -> None:
    rich = RICH.read_text(encoding="utf-8")
    compat = COMPAT.read_text(encoding="utf-8")
    assert "_pr117ComposerResolverSource()" in rich
    assert "const prompt = resolveComposer();" in rich
    assert "prompt.closest('form')" in rich
    assert "const exactAttachmentSet = crossEvidenceChannelExact;" in rich
    assert "function _pr117ComposerResolverSource()" in compat
    assert "|| document.body" not in rich
