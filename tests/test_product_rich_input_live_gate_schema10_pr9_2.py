from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_rich_input_live_gate_schema10_pr9_2 import (
    PRODUCT_WRITE_BUDGET,
    ProductRichInputSchema10LiveProvider,
    _validate_support,
)


def _raw_response(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": 10,
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
        "officialComposerRequiredForAttachmentEvidence": True,
        "exactBasenameAssociationRequired": True,
        "preStageDebuggerSetupDeadlineBounded": True,
        "latePreStageDebuggerAttachAutoDetached": True,
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "writePerformed": False,
    }


def _support(monkeypatch):
    provider = ProductRichInputSchema10LiveProvider()
    calls = []

    def fake_rpc(payload, *, timeout, on_event=None):
        calls.append(dict(payload))
        assert payload["characterizeRichInputSupport"] is True
        assert "text" not in payload
        assert "attachmentPaths" not in payload
        return _raw_response(payload["request_id"])

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support = provider.rich_input_support(timeout=1.0)
    return support, calls


def test_schema_10_support_probe_is_four_zero_write_characterizations(monkeypatch):
    support, calls = _support(monkeypatch)
    _validate_support(support)

    assert len(calls) == 4
    assert PRODUCT_WRITE_BUDGET == 3
    assert support["schema"] == 10
    assert support["official_composer_required_for_attachment_evidence"] is True
    assert support["exact_basename_association_required"] is True
    assert support["prestage_debugger_setup_deadline_bounded"] is True
    assert support["late_prestage_debugger_attach_auto_detached"] is True


@pytest.mark.parametrize(
    ("key", "message"),
    [
        (
            "official_composer_required_for_attachment_evidence",
            "OFFICIAL_COMPOSER_ATTACHMENT_EVIDENCE_NOT_PROVEN",
        ),
        ("exact_basename_association_required", "EXACT_BASENAME_ASSOCIATION_NOT_PROVEN"),
        (
            "prestage_debugger_setup_deadline_bounded",
            "PRESTAGE_DEBUGGER_SETUP_DEADLINE_NOT_PROVEN",
        ),
        (
            "late_prestage_debugger_attach_auto_detached",
            "LATE_PRESTAGE_DEBUGGER_ATTACH_DETACH_NOT_PROVEN",
        ),
    ],
)
def test_schema_10_validator_requires_every_new_claim(monkeypatch, key, message):
    support, _ = _support(monkeypatch)
    support[key] = False
    with pytest.raises(RuntimeError, match=message):
        _validate_support(support)


def test_schema_10_validator_rejects_schema_9(monkeypatch):
    support, _ = _support(monkeypatch)
    support["schema"] = 9
    with pytest.raises(RuntimeError, match="SCHEMA10_RICH_INPUT_SUPPORT_NOT_PROVEN"):
        _validate_support(support)


def test_schema_10_validator_preserves_schema_9_claims(monkeypatch):
    support, _ = _support(monkeypatch)
    support["cross_evidence_channel_exactness"] = False
    with pytest.raises(RuntimeError, match="CROSS_EVIDENCE_CHANNEL_EXACTNESS_NOT_PROVEN"):
        _validate_support(support)
