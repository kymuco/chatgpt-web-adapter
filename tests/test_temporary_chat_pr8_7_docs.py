from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "temporary_chat_pr8_7.md"
LIVE_DOC = ROOT / "docs" / "temporary_chat_pr8_7_live_characterization.md"
TRANSPORT = ROOT / "src" / "chatgpt_web_adapter" / "browser_owned_product_transport.py"


def test_pr87_docs_keep_temporary_chat_evidence_first_and_fail_closed() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "temporary_chat = UNKNOWN" in text
    assert "production Temporary Chat is not enabled" in text
    assert "python -m chatgpt_web_adapter.temporary_chat_probe" in text
    assert "no conversation POST" in text
    assert "DEDICATED PROBE TAB" in text
    assert "TEMP -> NORMAL" in text
    assert "NORMAL -> TEMP" in text
    assert "FUNDAMENTAL_BOUNDARY_DISCOVERED" in text


def test_pr87_live_evidence_separates_ui_marker_from_persistence_semantics() -> None:
    text = LIVE_DOC.read_text(encoding="utf-8")

    assert "T4  no ordinary-history persistence        FAIL / CONTRADICTED" in text
    assert "UI_MODE_MARKER != PRODUCT_TEMPORARY_PROOF" in text
    assert "semantic:document-title-temporary" in text
    assert "temporary_chat = UNKNOWN" in text
    assert "temporary_chat_history_probe" in text
    assert "history_link_present" in text
    assert "ordinary backend conversation identity" in text
    assert "browserless canonical status/messages/attach" in text


def test_pr87_characterization_commit_does_not_claim_transport_availability() -> None:
    transport = TRANSPORT.read_text(encoding="utf-8")

    assert "TEMPORARY_CHAT: CapabilityState.UNKNOWN" in transport
    assert 'TEMPORARY_CHAT: "PR8.7' not in transport
