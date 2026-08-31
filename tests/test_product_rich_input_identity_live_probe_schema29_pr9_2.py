from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "product_rich_input_identity_live_probe_schema29_pr9_2.py"
)


def _source() -> str:
    return PROBE.read_text(encoding="utf-8")


def test_schema29_identity_probe_has_hard_one_write_budget_and_explicit_opt_in():
    text = _source()
    assert "SCHEMA = 29" in text
    assert "PRODUCT_WRITE_BUDGET = 1" in text
    assert 'parser.add_argument("--acknowledge-live-write", action="store_true")' in text
    assert "this probe performs exactly one product write" in text
    assert "--acknowledge-live-writes" not in text


def test_schema29_identity_probe_contains_exactly_one_product_send_call():
    tree = ast.parse(_source())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_text_observed"
    ]
    assert len(calls) == 1


def test_schema29_identity_probe_is_image_new_chat_only():
    text = _source()
    assert "_v7._IMAGE_PROMPT" in text
    assert "media=[image_path]" in text
    assert 'conversation_mode="normal"' in text
    assert "_v7._IMAGE_REPLY" in text
    assert 'expected_attachment_count=1' in text
    assert 'attachment_evidence_kind="image_color_band_order"' in text
    assert "_v7._FILE_PROMPT" not in text
    assert "_v7._CONTINUATION_PROMPT" not in text


def test_schema29_identity_probe_requires_support_and_nonempty_resolved_identity():
    text = _source()
    assert "ProductRichInputSchema29LiveProvider" in text
    assert "_validate_support(support)" in text
    assert 'turn.get("conversation_id")' in text
    assert "PR9_2_SCHEMA29_IDENTITY_PROBE_CONVERSATION_ID_NOT_PROVEN" in text
    assert '"new_chat_conversation_identity_authority"' in text
    assert '"request_bound_protocol_conversation_id_consensus": True' in text
    assert '"stream_handoff_required_for_causal_conversation_identity": False' in text
    assert '"route_conversation_identity_authoritative": False' in text
    assert '"automatic_write_retry": False' in text
    assert '"fallback_transport": None' in text


def test_schema29_identity_probe_reports_request_body_causal_authority():
    text = _source()
    assert '"probe": "SCHEMA29_VALIDATED_CLICK_REQUEST_BODY_AND_RESPONSE_IDENTITY"' in text
    assert 'label="SCHEMA29_REQUEST_BODY_IMAGE_NEW_CHAT"' in text
    assert '"validated_click_request_body_correlation": True' in text
    assert '"exact_user_text_request_binding": True' in text
    assert '"request_message_id_binding": True' in text
    assert '"request_attachment_count_binding": True' in text
    assert '"raw_post_arm_multiplicity_non_authoritative": True' in text
    assert '"has_user_gesture_non_authoritative": True' in text


def test_schema29_identity_probe_reuses_attachment_dependent_canonical_validator():
    text = _source()
    assert "_v7._validate_execution(" in text
    assert '"attachment_dependent_response_proven": True' in text
    assert '"canonical_finality_proven": True' in text
    assert '"conversation_identity_resolved": True' in text
