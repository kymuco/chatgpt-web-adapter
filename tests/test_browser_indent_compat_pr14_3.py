from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SCHEMA29 = EXT / "service_worker_rich_input_schema29_repair_pr9_2.js"
TEXT_SHAPE = EXT / "service_worker_request_text_shape_compat.js"
INDENT = EXT / "service_worker_browser_indent_compat.js"
RUNTIME_WRITE = EXT / "service_worker_runtime_write.js"


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def _inspector_source() -> str:
    schema29 = SCHEMA29.read_text(encoding="utf-8")
    start = schema29.index("function _pr92Schema29NonEmptyString")
    end = schema29.index("function _pr92Schema29ApplyRequestInspection", start)
    return "\n".join(
        (
            schema29[start:end],
            TEXT_SHAPE.read_text(encoding="utf-8"),
            INDENT.read_text(encoding="utf-8"),
        )
    )


def test_nbsp_line_indentation_matches_exact_ordinary_text() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = 'before\\n{{\\n  "a": 1,\\n    "b": 2\\n}}\\nafter';
const observed = 'before\\n{{\\n\u00a0\u00a0"a": 1,\\n\u00a0\u00a0\u00a0\u00a0"b": 2\\n}}\\nafter';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-indent",
    author: {{role: "user"}},
    content: {{parts: [observed]}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is True
    assert result["logicalMessageId"] == "msg-indent"
    assert result["diagnostics"]["exactTextUserMessageCount"] == 1
    assert result["diagnostics"]["attachmentCountsMatch"] is True


def test_nnbsp_line_indentation_matches_exact_ordinary_text() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = '{{\\n  "a": 1\\n}}';
const observed = '{{\\n\u202f\u202f"a": 1\\n}}';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-nnbsp",
    author: {{role: "user"}},
    content: {{parts: [observed]}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is True


def test_nbsp_inside_value_remains_mismatch() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = '{{"value":"alpha beta"}}';
const observed = '{{"value":"alpha\u00a0beta"}}';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-value",
    author: {{role: "user"}},
    content: {{parts: [observed]}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is False
    assert result["diagnostics"]["exactTextUserMessageCount"] == 0


def test_nbsp_between_prose_words_remains_mismatch() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = 'alpha  beta';
const observed = 'alpha \u00a0beta';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-prose",
    author: {{role: "user"}},
    content: {{parts: [observed]}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is False


def test_indent_compat_does_not_apply_to_attachment_turns() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = '{{\\n  "a": 1\\n}}';
const observed = '{{\\n\u00a0\u00a0"a": 1\\n}}';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-rich",
    author: {{role: "user"}},
    content: {{parts: [
      observed,
      {{asset_pointer: "sediment://file-1"}}
    ]}},
    metadata: {{attachments: [{{id: "file-1"}}]}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 1, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is False


def test_safe_indent_fingerprint_contains_no_raw_evidence() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
let persisted = {{}};
globalThis.chrome = {{
  storage: {{
    local: {{
      set(value) {{ persisted = {{...persisted, ...value}}; return Promise.resolve(); }}
    }}
  }}
}};
{source}
const expected = 'private-prefix\\n  "private-value"';
const observed = 'private-prefix\\n\u00a0\u00a0"private-value"';
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "private-message-id",
    author: {{role: "user"}},
    content: {{parts: [observed]}},
    metadata: {{}}
  }}]
}});
const matched = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
const fingerprint = persisted[CWA_BROWSER_INDENT_DIAGNOSTIC_KEY];
console.log(JSON.stringify({{
  matched: matched.matched,
  fingerprint,
  serialized: JSON.stringify(fingerprint)
}}));
"""
    )

    assert result["matched"] is True
    fingerprint = result["fingerprint"]
    assert fingerprint["priorMatched"] is False
    assert fingerprint["eligibleOrdinaryRequest"] is True
    assert fingerprint["observedTextCandidateCount"] == 1
    assert fingerprint["browserIndentEquivalent"] is True
    assert fingerprint["normalizedIndentSpaceCount"] == 2
    assert fingerprint["normalizedMatch"] is True
    assert fingerprint["expectedTextLength"] == fingerprint["observedTextLength"]
    assert "private-prefix" not in result["serialized"]
    assert "private-value" not in result["serialized"]
    assert "private-message-id" not in result["serialized"]


def test_write_domain_keeps_ordinary_identity_authority_last() -> None:
    source = RUNTIME_WRITE.read_text(encoding="utf-8")
    text_shape = source.index(
        'importScripts("service_worker_request_text_shape_compat.js")'
    )
    indent = source.index('importScripts("service_worker_browser_indent_compat.js")')
    ui = source.index('importScripts("service_worker_ui_compat_pr11_7.js")')
    ordinary = source.index(
        'importScripts("service_worker_ordinary_text_identity_authority.js")'
    )
    assert text_shape < indent < ui < ordinary
