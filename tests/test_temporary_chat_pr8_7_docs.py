from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "temporary_chat_pr8_7.md"
LIVE_DOC = ROOT / "docs" / "temporary_chat_pr8_7_live_characterization.md"
REVIEW_DOC = ROOT / "docs" / "temporary_chat_pr8_7_capability_graduation_review.md"
TRANSPORT = ROOT / "src" / "chatgpt_web_adapter" / "browser_owned_product_transport.py"


def test_pr87_docs_keep_temporary_chat_evidence_first_and_fail_closed() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "production Temporary Chat is **not enabled by this document**" in text
    assert 'production conversation_mode="temporary" = NOT ENABLED' in text
    assert "temporary_product_conversation_id" in text
    assert "temporary_live_write_authority" in text
    assert "No hidden fallback is allowed." in text
    assert "TEMP -> NORMAL" in text
    assert "NORMAL -> TEMP" in text
    assert "Browser Authority Lease" in text
    assert "Temporary Lifecycle" in text


def test_pr87_live_evidence_preserves_corrected_temporary_ground_truth() -> None:
    text = LIVE_DOC.read_text(encoding="utf-8")

    assert "Earlier automated activation result is an ordinary durable control" in text
    assert "https://chatgpt.com/?temporary-chat=true" in text
    assert "T2 true Temporary page-owned visible text turn = PASS" in text
    assert "T7b post-close product-route recovery = STABLE_RECOVERED / PASS" in text
    assert "post-close controlled continuation = REJECTED / HTTP 404" in text
    assert "normal multi-turn conversation semantics = PROVEN" in text
    assert "temporary_chat = UNKNOWN" in text
    assert "production conversation_mode=\"temporary\" = NOT ENABLED" in text


def test_pr87_t13_review_and_transport_use_final_unimplemented_classification() -> None:
    review = REVIEW_DOC.read_text(encoding="utf-8")
    transport = TRANSPORT.read_text(encoding="utf-8")

    assert "temporary_chat = UNIMPLEMENTED" in review
    assert 'production conversation_mode="temporary" = DISABLED' in review
    assert "UNKNOWN -> UNIMPLEMENTED" in review
    assert "AVAILABLE graduation          = DENIED" in review

    assert "TEMPORARY_CHAT: CapabilityState.UNIMPLEMENTED" in transport
    assert "PR8.7 T13 review" in transport
    assert 'TEMPORARY_CHAT: "PR8.7' not in transport
