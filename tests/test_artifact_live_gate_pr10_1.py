from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "tools" / "pr10_1_artifact_live_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("pr10_1_artifact_live_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_live_gate_safe_event_excludes_capability_locators():
    gate = _load_gate()
    event = {
        "type": "product_artifact_observed",
        "artifact_id": "file-123",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 10,
        "download_available": True,
        "source_origin": "product_message_metadata",
        "download_url": "https://secret.test/signed?token=private",
        "href": "https://secret.test/private",
        "text": "private",
    }

    safe = gate._safe_event(event)

    assert safe == {
        "type": "product_artifact_observed",
        "artifact_id": "file-123",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 10,
        "download_available": True,
        "source_origin": "product_message_metadata",
    }


def test_artifact_live_gate_support_contract_is_no_write_and_no_authority():
    gate = _load_gate()

    assert gate._EXPECTED_ARTIFACT_SUPPORT == {
        "supported": True,
        "schema": 1,
        "explicit_artifact_identity_required": True,
        "artifact_locator_exported": False,
        "grants_download_authority": False,
        "grants_overwrite_authority": False,
        "write_performed": False,
    }


def test_artifact_live_gate_source_has_one_product_write_and_no_download_path():
    source = GATE_PATH.read_text(encoding="utf-8")

    assert source.count("runtime.send_text_observed(") == 1
    assert "PRODUCT_WRITE_BUDGET = 1" in source
    assert '"download_attempted": False' in source
    assert '"local_write_attempted": False' in source
    assert "--acknowledge-live-write" in source
    assert "--preflight-only" in source

    for forbidden in (
        "urlopen(",
        "requests.get(",
        "httpx.get(",
        "chrome.downloads",
        "Page.setDownloadBehavior",
        "Browser.setDownloadBehavior",
        "write_bytes(",
        "write_text(",
        "open(destination",
    ):
        assert forbidden not in source


def test_artifact_live_prompt_is_bounded_to_conversation_file_creation():
    gate = _load_gate()
    prompt = gate.DEFAULT_PROMPT.lower()

    assert "cwa_pr10_1_probe.txt" in prompt
    assert "tiny plain-text" in prompt
    assert "do not use connectors" in prompt
    assert "do not access private data" in prompt
    assert "outside this chatgpt conversation" in prompt
