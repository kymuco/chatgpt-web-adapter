from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_provenance import (
    CompletionSource,
    ProductCompletionProvenance,
    ProductExecutionProvenance,
    ProductIdentityProvenance,
)
from chatgpt_web_adapter.product_rich_input_live_gate_pr9_2 import (
    PRODUCT_WRITE_BUDGET,
    ProductRichInputLiveProvider,
    _CONTINUATION_PROMPT,
    _CONTINUATION_REPLY,
    _FILE_PROMPT,
    _FILE_REPLY,
    _IMAGE_PROMPT,
    _IMAGE_REPLY,
    _validate_execution,
    _validate_support,
    _write_fixtures,
)


def _support_response(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": 1,
        "stagingPrimitive": "DOM.setFileInputFiles",
        "maxAttachmentCount": 32,
        "nativeMessagingCarriesAttachmentBytes": False,
        "officialPageOwnsUpload": True,
        "officialPageOwnsProtectedWrite": True,
        "recoveryBeforeAttachmentStaging": True,
        "staleAttachmentFailureFence": True,
        "staleAttachmentFencePersistentAcrossWorkerRestart": True,
        "singleTotalTurnDeadline": True,
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "writePerformed": False,
    }


def _validated_support() -> dict:
    return {
        "supported": True,
        "schema": 1,
        "staging_primitive": "DOM.setFileInputFiles",
        "max_attachment_count": 32,
        "native_messaging_carries_attachment_bytes": False,
        "official_page_owns_upload": True,
        "official_page_owns_protected_write": True,
        "recovery_before_attachment_staging": True,
        "stale_attachment_failure_fence": True,
        "stale_attachment_fence_persistent_across_worker_restart": True,
        "single_total_turn_deadline": True,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "write_performed": False,
    }


def _execution(expected: str):
    response = SimpleNamespace(
        text=expected,
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id="assistant-1",
        ),
    )
    provenance = ProductExecutionProvenance(
        product_semantics="ordinary-chatgpt",
        transport="browser-owned",
        write_plane="BROWSER_NATIVE_PAGE_OWNED_WRITE",
        readback_plane="BROWSERLESS_CANONICAL_HTTP",
        session_plane="BROWSERLESS_SESSION_HTTP",
        completion=ProductCompletionProvenance(
            completed=True,
            source=CompletionSource.CANONICAL_READBACK,
            canonical_completion_proven=True,
            finish_reason="stop",
            finish_reason_observed=True,
        ),
        identity=ProductIdentityProvenance(
            conversation_id="conversation-1",
            message_id="assistant-1",
            observed_model="test-model",
        ),
        transport_metadata={},
    )
    return SimpleNamespace(
        response=response,
        observation=SimpleNamespace(write_event_observed=True),
        provenance=provenance,
    )


def test_support_probe_is_no_write_and_requires_pr9_2_overlay(monkeypatch):
    provider = ProductRichInputLiveProvider()
    calls = []

    def fake_rpc(payload, *, timeout, on_event=None):
        calls.append(dict(payload))
        assert payload["type"] == "turn"
        assert payload["characterizeRichInputSupport"] is True
        assert "text" not in payload
        assert "attachmentPaths" not in payload
        return _support_response(payload["request_id"])

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support = provider.rich_input_support(timeout=1.0)
    _validate_support(support)

    assert len(calls) == 1
    assert support["recovery_before_attachment_staging"] is True
    assert support["stale_attachment_failure_fence"] is True
    assert support["stale_attachment_fence_persistent_across_worker_restart"] is True
    assert support["single_total_turn_deadline"] is True
    assert support["write_performed"] is False
    assert support["automatic_write_retry"] is False
    assert support["fallback_transport"] is None


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("recovery_before_attachment_staging", "RECOVERY_BEFORE_STAGING_NOT_PROVEN"),
        ("stale_attachment_failure_fence", "STALE_ATTACHMENT_FAILURE_FENCE_NOT_PROVEN"),
        (
            "stale_attachment_fence_persistent_across_worker_restart",
            "PERSISTENT_STALE_ATTACHMENT_FENCE_NOT_PROVEN",
        ),
        ("single_total_turn_deadline", "SINGLE_TOTAL_TURN_DEADLINE_NOT_PROVEN"),
    ],
)
def test_support_validation_requires_recovery_and_persistent_cleanup_claims(field, error):
    support = _validated_support()
    support[field] = False
    with pytest.raises(RuntimeError, match=error):
        _validate_support(support)


def test_support_validation_fails_if_probe_claims_a_write():
    support = _validated_support()
    support["write_performed"] = True
    with pytest.raises(RuntimeError, match="SUPPORT_PROBE_MUST_BE_NO_WRITE"):
        _validate_support(support)


def test_execution_validation_requires_exact_attachment_events_and_canonical_finality():
    expected = "SDK_PR9_2_TEST_OK"
    events = [
        {
            "type": "browser_native_write_completed",
            "attachment_count": 1,
            "browser_authority_lease_id": "lease-1",
        },
        {
            "type": "browser_native_readback_completed",
            "attachment_count": 1,
        },
    ]
    result = _validate_execution(
        label="TEST",
        execution=_execution(expected),
        events=events,
        expected_text=expected,
        expected_attachment_count=1,
        attachment_evidence_kind="test_fixture_marker",
        expected_conversation_id="conversation-1",
    )
    assert result["canonical_completion_proven"] is True
    assert result["completion_source"] == "CANONICAL_READBACK"
    assert result["attachment_count"] == 1
    assert result["attachment_dependent_evidence"] is True
    assert result["attachment_evidence_kind"] == "test_fixture_marker"

    events[0]["attachment_count"] = 0
    with pytest.raises(RuntimeError, match="WRITE_ATTACHMENT_COUNT_MISMATCH"):
        _validate_execution(
            label="TEST",
            execution=_execution(expected),
            events=events,
            expected_text=expected,
            expected_attachment_count=1,
            attachment_evidence_kind="test_fixture_marker",
        )


def test_execution_validation_rejects_wrong_attachment_dependent_response():
    events = [
        {"type": "browser_native_write_completed", "attachment_count": 1},
        {"type": "browser_native_readback_completed", "attachment_count": 1},
    ]
    with pytest.raises(RuntimeError, match="ATTACHMENT_DEPENDENT_RESPONSE_MISMATCH"):
        _validate_execution(
            label="TEST",
            execution=_execution("WRONG"),
            events=events,
            expected_text="EXPECTED_FROM_ATTACHMENT",
            expected_attachment_count=1,
            attachment_evidence_kind="test_fixture_marker",
        )


def test_live_gate_prompts_do_not_disclose_expected_attachment_evidence():
    assert _IMAGE_REPLY not in _IMAGE_PROMPT
    assert _FILE_REPLY not in _FILE_PROMPT
    assert _CONTINUATION_REPLY not in _CONTINUATION_PROMPT
    assert "attached PNG image" in _IMAGE_PROMPT
    assert "attached text file" in _FILE_PROMPT
    assert "newly attached text file" in _CONTINUATION_PROMPT


def test_live_gate_has_exact_three_write_budget_and_attachment_dependent_fixtures(tmp_path):
    assert PRODUCT_WRITE_BUDGET == 3
    image, text_file, continuation_file = _write_fixtures(Path(tmp_path))

    image_bytes = image.read_bytes()
    assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image_bytes) > 50

    file_text = text_file.read_text(encoding="utf-8")
    continuation_text = continuation_file.read_text(encoding="utf-8")
    assert f"EVIDENCE: {_FILE_REPLY}" in file_text
    assert f"EVIDENCE: {_CONTINUATION_REPLY}" in continuation_text
    assert _FILE_REPLY != _CONTINUATION_REPLY
