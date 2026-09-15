from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SCHEMA29 = EXT / "service_worker_rich_input_schema29_repair_pr9_2.js"
COMPAT = EXT / "service_worker_request_text_shape_compat.js"


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
    compat = COMPAT.read_text(encoding="utf-8")
    return schema29[start:end] + "\n" + compat


def test_long_object_text_part_matches_exactly() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const prompt = "x".repeat(100000) + "::tail";
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-long-object",
    author: {{role: "user"}},
    content: {{
      content_type: "multimodal_text",
      parts: [{{content_type: "text", text: prompt}}]
    }},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, prompt, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is True
    assert result["logicalMessageId"] == "msg-long-object"
    assert result["diagnostics"]["exactTextUserMessageCount"] == 1
    assert result["diagnostics"]["attachmentCountsMatch"] is True


def test_content_text_fallback_matches_exactly() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const prompt = "content.text fallback";
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-content-text",
    author: {{role: "user"}},
    content: {{content_type: "text", parts: [], text: prompt}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, prompt, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is True
    assert result["logicalMessageId"] == "msg-content-text"


def test_asset_pointer_with_incidental_text_is_not_reclassified_as_text() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const prompt = "must not come from attachment object";
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-pointer",
    author: {{role: "user"}},
    content: {{
      content_type: "multimodal_text",
      parts: [{{asset_pointer: "sediment://file-1", text: prompt}}]
    }},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, prompt, 1, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is False
    assert result["diagnostics"]["exactTextUserMessageCount"] == 0


def test_object_text_compatibility_keeps_exact_equality() -> None:
    source = _inspector_source()
    result = _run_node(
        f"""
{source}
const expected = "exact prompt";
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-near-match",
    author: {{role: "user"}},
    content: {{parts: [{{text: expected + "!"}}]}},
    metadata: {{}}
  }}]
}});
const result = _pr92Schema29InspectRequestPostData(body, expected, 0, null);
console.log(JSON.stringify(result));
"""
    )

    assert result["matched"] is False
    assert result["diagnostics"]["exactTextUserMessageCount"] == 0
