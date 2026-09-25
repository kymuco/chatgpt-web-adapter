from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

SCHEMA29 = EXT / "service_worker_rich_input_schema29_repair_pr9_2.js"
TEXT_SHAPE = EXT / "service_worker_request_text_shape_compat.js"
INDENT = EXT / "service_worker_browser_indent_compat.js"
OWNER = EXT / "service_worker_request_inspection.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_request_inspection_has_one_public_owner() -> None:
    schema29 = _source(SCHEMA29)
    text_shape = _source(TEXT_SHAPE)
    indent = _source(INDENT)
    owner = _source(OWNER)

    assert "function _pr92Schema29BaseInspectRequestPostData(" in schema29
    assert "function _pr92Schema29InspectRequestPostData(" not in schema29

    assert "function _cwaRequestTextShapeInspect(" in text_shape
    assert "_pr92Schema29InspectRequestPostData =" not in text_shape
    assert "_cwaRequestTextShapePriorSchema29Inspect" not in text_shape

    assert "function _cwaBrowserIndentInspect(" in indent
    assert "_pr92Schema29InspectRequestPostData =" not in indent
    assert "_cwaBrowserIndentPriorSchema29Inspect" not in indent

    assert owner.count("function _pr92Schema29InspectRequestPostData(") == 1
    assert "_pr92Schema29InspectRequestPostData =" not in owner


def test_text_shape_delegates_only_to_schema29_base() -> None:
    text_shape = _source(TEXT_SHAPE)
    start = text_shape.index("function _cwaRequestTextShapeInspect")
    block = text_shape[start:]

    assert "_pr92Schema29BaseInspectRequestPostData(" in block
    assert "_cwaBrowserIndentInspect(" not in block


def test_browser_indent_preserves_two_pass_text_shape_delegation() -> None:
    indent = _source(INDENT)
    start = indent.index("function _cwaBrowserIndentInspect")
    block = indent[start:]

    assert block.count("_cwaRequestTextShapeInspect(") == 2
    first = block.index("_cwaRequestTextShapeInspect(")
    canonicalize = block.index("_cwaBrowserIndentCanonicalizedPostData(")
    second = block.index("_cwaRequestTextShapeInspect(", first + 1)
    assert first < canonicalize < second


def test_write_domain_installs_owner_between_indent_and_ui_compat() -> None:
    write = _source(WRITE)
    text_shape = 'importScripts("service_worker_request_text_shape_compat.js");'
    indent = 'importScripts("service_worker_browser_indent_compat.js");'
    owner = 'importScripts("service_worker_request_inspection.js");'
    ui = 'importScripts("service_worker_ui_compat_pr11_7.js");'

    assert write.index(text_shape) < write.index(indent) < write.index(owner)
    assert write.index(owner) < write.index(ui)


def test_public_owner_delegates_once_with_unchanged_arguments() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
function _cwaBrowserIndentInspect(postData, expectedText, count, conversationId) {{
  calls.push([postData, expectedText, count, conversationId]);
  return {{ matched: true }};
}}
{owner}
const result = _pr92Schema29InspectRequestPostData("body", "prompt", 0, null);
console.log(JSON.stringify({{
  result,
  calls
}}));
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": {"matched": True},
        "calls": [["body", "prompt", 0, None]],
    }
