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


def test_pr87_live_evidence_reclassifies_run_e_and_requires_manual_ground_truth() -> None:
    text = LIVE_DOC.read_text(encoding="utf-8")

    assert "ORDINARY DURABLE CONTROL" in text
    assert "ordinary-control evidence only" in text
    assert "Manual Temporary ground-truth probe" in text
    assert "temporary_chat_manual_ground_truth_probe" in text
    assert "manual-temporary-confirmed" in text
    assert "does NOT click Temporary" in text
    assert "BEFORE ANY CANONICAL READ" in text
    assert "true Temporary canonical read while page open" in text
    assert "true Temporary canonical read after page close" in text
    assert "UI_MODE_MARKER != PRODUCT_TEMPORARY_PROOF" in text
    assert "HISTORY_ENUMERATION != DIRECT_ID_READABILITY" in text
    assert "temporary_chat = UNKNOWN" in text
    assert "stable_history_presence" in text

    # The ordinary Run E readback must not be used as Temporary evidence.
    assert '"Temporary uses an ordinary backend conversation identity"' in text
    assert "Those questions are **OPEN again**" in text


def test_pr87_characterization_commit_does_not_claim_transport_availability() -> None:
    transport = TRANSPORT.read_text(encoding="utf-8")

    assert "TEMPORARY_CHAT: CapabilityState.UNKNOWN" in transport
    assert 'TEMPORARY_CHAT: "PR8.7' not in transport
