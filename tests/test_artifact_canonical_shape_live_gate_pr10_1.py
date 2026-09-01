from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
GATE_PATH = TOOLS / "pr10_1_artifact_canonical_shape_live_gate.py"


def _load_gate():
    sys.path.insert(0, str(TOOLS))
    try:
        spec = importlib.util.spec_from_file_location(
            "pr10_1_artifact_canonical_shape_live_gate",
            GATE_PATH,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(TOOLS))
        except ValueError:
            pass


def _node(message_id: str, role: str, content, *, metadata=None, parent=None):
    return {
        "id": message_id,
        "parent": parent,
        "children": [],
        "message": {
            "id": message_id,
            "author": {"role": role},
            "content": content,
            "metadata": metadata or {},
        },
    }


def test_canonical_shape_ignores_user_and_assistant_prose_but_finds_structured_attachment():
    gate = _load_gate()
    filename = gate.PROBE_FILENAME
    user = _node(
        "u1",
        "user",
        {"content_type": "text", "parts": [f"please create {filename}"]},
    )
    assistant_text = _node(
        "a1",
        "assistant",
        {
            "content_type": "text",
            "parts": [f"[download](sandbox:/mnt/data/{filename})"],
        },
        parent="u1",
    )
    tool = _node(
        "t1",
        "tool",
        {"content_type": "execution_output", "parts": []},
        metadata={
            "attachments": [
                {
                    "id": "file-123",
                    "name": filename,
                    "mime_type": "text/plain",
                    "url": "https://private.invalid/signed?token=secret",
                }
            ]
        },
        parent="a1",
    )
    payload = {
        "current_node": "t1",
        "mapping": {"u1": user, "a1": assistant_text, "t1": tool},
    }

    shape = gate.characterize_canonical_payload(payload)

    assert shape["payload_present"] is True
    assert len(shape["findings"]) == 1
    finding = shape["findings"][0]
    assert finding["anchor_kind"] == "exact_filename"
    assert finding["field_key"] == "name"
    assert finding["source_role"] == "tool"
    assert finding["locator_key_present"] is True
    assert "id" in finding["identity_key_candidates"]
    serialized = repr(finding)
    assert "private.invalid" not in serialized
    assert "token=secret" not in serialized


def test_canonical_shape_excludes_thoughts_even_when_structured():
    gate = _load_gate()
    filename = gate.PROBE_FILENAME
    thought = _node(
        "a1",
        "assistant",
        {
            "content_type": "thoughts",
            "parts": [{"file": {"name": filename, "id": "file-private"}}],
        },
    )
    payload = {"current_node": "a1", "mapping": {"a1": thought}}

    shape = gate.characterize_canonical_payload(payload)

    assert shape["findings"] == []


def test_canonical_shape_gate_is_bounded_read_only_after_one_product_write():
    source = GATE_PATH.read_text(encoding="utf-8")

    assert 'PROBE_FILENAME = "cwa_pr10_1_probe.txt"' in source
    assert "PRODUCT_WRITE_BUDGET = 1" in source
    assert "ADDITIONAL_CANONICAL_READ_BUDGET = 1" in source
    assert source.count("runtime.send_text_observed(") == 1
    assert source.count('getattr(client, "_get_conversation_payload", None)') == 1
    assert '"raw_canonical_payload_exported": False' in source
    assert '"raw_canonical_payload_persisted": False' in source
    assert '"assistant_text_used_as_artifact_evidence": False' in source
    assert '"download_attempted": False' in source
    assert '"local_write_attempted": False' in source
    assert "role == \"user\"" in source
    assert 'content_type == "thoughts"' in source

    for forbidden in (
        "urlopen(",
        "requests.get(",
        "httpx.get(",
        "chrome.downloads",
        "write_bytes(",
        "write_text(",
        "open(destination",
    ):
        assert forbidden not in source
