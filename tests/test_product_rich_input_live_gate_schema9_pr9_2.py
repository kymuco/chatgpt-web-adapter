from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_rich_input_live_gate_schema9_pr9_2 import (
    PRODUCT_WRITE_BUDGET,
    ProductRichInputSchema9LiveProvider,
    _validate_support,
)


def _raw_response(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": 9,
        "stagingPrimitive": "DOM.setFileInputFiles",
        "maxAttachmentCount": 32,
        "nativeMessagingCarriesAttachmentBytes": False,
        "officialPageOwnsUpload": True,
        "officialPageOwnsProtectedWrite": True,
        "recoveryBeforeAttachmentStaging": True,
        "staleAttachmentFailureFence": True,
        "staleAttachmentFencePersistentAcrossWorkerRestart": True,
        "singleTotalTurnDeadline": True,
        "preSubmitDeadlineGuard": True,
        "deadlineBoundedPostWriteCleanup": True,
        "postWriteFenceRetainedUntilNextPrewrite": True,
        "enterKeyReleaseAffectsSubmittedOutcome": False,
        "mouseToEnterFallbackAfterReleaseAttempt": False,
        "mouseReleaseOutcomeAmbiguityFailsClosed": True,
        "staleAttachmentCleanupProof": "RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED",
        "attachmentCountEvidence": "PAGE_OWNED_COMPOSER_ATTACHMENT_STATE",
        "attachmentEvidenceStablePollCount": 2,
        "preSubmitAttachmentRevalidation": True,
        "postSendReadinessAttachmentRevalidation": True,
        "protectedSubmitPrimitive": "PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK",
        "richInputRawCdpInputSubmitDisabled": True,
        "richInputEnterFallbackEnabled": False,
        "lateProtectedSubmitExecutionPreventedByPageDeadline": True,
        "atomicAttachmentValidationAndSubmit": True,
        "postClickDebuggerAckRequired": False,
        "protectedSubmitOutcomeProof": "NETWORK_REQUEST_OBSERVATION",
        "submitObservationReserveMs": 10_500,
        "staleAttachmentCleanupRequiresSessionRuntimeIdentity": True,
        "staleAttachmentIdentityMismatchClosesTab": False,
        "staleAttachmentIdentityMismatchFailsClosed": True,
        "staleAttachmentUnprovenIdentityFailsClosed": True,
        "preStageComposerAttachmentClean": True,
        "exactComposerAttachmentSetRequired": True,
        "destructiveCleanupAuthorityRevalidatedAtClose": True,
        "destructiveCleanupOwnershipChangeFailsClosed": True,
        "crossEvidenceChannelExactness": True,
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "writePerformed": False,
    }


def test_schema_9_support_probe_is_three_zero_write_characterizations(monkeypatch):
    provider = ProductRichInputSchema9LiveProvider()
    calls = []

    def fake_rpc(payload, *, timeout, on_event=None):
        calls.append(dict(payload))
        assert payload["characterizeRichInputSupport"] is True
        assert "text" not in payload
        assert "attachmentPaths" not in payload
        return _raw_response(payload["request_id"])

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support = provider.rich_input_support(timeout=1.0)
    _validate_support(support)

    assert len(calls) == 3
    assert PRODUCT_WRITE_BUDGET == 3
    assert support["schema"] == 9
    assert support["cross_evidence_channel_exactness"] is True


def test_schema_9_validator_requires_cross_channel_exactness(monkeypatch):
    provider = ProductRichInputSchema9LiveProvider()
    monkeypatch.setattr(
        provider,
        "_rpc",
        lambda payload, *, timeout, on_event=None: _raw_response(payload["request_id"]),
    )
    support = provider.rich_input_support(timeout=1.0)
    support["cross_evidence_channel_exactness"] = False

    with pytest.raises(RuntimeError, match="CROSS_EVIDENCE_CHANNEL_EXACTNESS_NOT_PROVEN"):
        _validate_support(support)


def test_schema_9_validator_rejects_schema_8(monkeypatch):
    provider = ProductRichInputSchema9LiveProvider()
    monkeypatch.setattr(
        provider,
        "_rpc",
        lambda payload, *, timeout, on_event=None: _raw_response(payload["request_id"]),
    )
    support = provider.rich_input_support(timeout=1.0)
    support["schema"] = 8

    with pytest.raises(RuntimeError, match="SCHEMA9_RICH_INPUT_SUPPORT_NOT_PROVEN"):
        _validate_support(support)


def test_schema_9_validator_preserves_schema_8_claims(monkeypatch):
    provider = ProductRichInputSchema9LiveProvider()
    monkeypatch.setattr(
        provider,
        "_rpc",
        lambda payload, *, timeout, on_event=None: _raw_response(payload["request_id"]),
    )
    support = provider.rich_input_support(timeout=1.0)
    support["exact_composer_attachment_set_required"] = False

    with pytest.raises(RuntimeError, match="EXACT_COMPOSER_ATTACHMENT_SET_NOT_PROVEN"):
        _validate_support(support)
