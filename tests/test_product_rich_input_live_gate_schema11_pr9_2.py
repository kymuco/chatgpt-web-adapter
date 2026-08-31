from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_rich_input_live_gate_schema11_pr9_2 import (
    PRODUCT_WRITE_BUDGET,
    ProductRichInputSchema11LiveProvider,
    _validate_support,
)


def _raw_response(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": 11,
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
        "structuredRemovalControlBasenameParsing": True,
        "attachmentEvidenceReadsDeadlineBounded": True,
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "writePerformed": False,
    }


def _support(monkeypatch):
    provider = ProductRichInputSchema11LiveProvider()
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


def test_schema_11_support_probe_is_five_zero_write_characterizations(monkeypatch):
    support, calls = _support(monkeypatch)
    _validate_support(support)

    assert len(calls) == 5
    assert PRODUCT_WRITE_BUDGET == 3
    assert support["schema"] == 11
    assert support["structured_removal_control_basename_parsing"] is True
    assert support["attachment_evidence_reads_deadline_bounded"] is True


@pytest.mark.parametrize(
    ("key", "message"),
    [
        (
            "structured_removal_control_basename_parsing",
            "STRUCTURED_REMOVAL_BASENAME_NOT_PROVEN",
        ),
        (
            "attachment_evidence_reads_deadline_bounded",
            "ATTACHMENT_EVIDENCE_READ_DEADLINE_NOT_PROVEN",
        ),
    ],
)
def test_schema_11_validator_requires_every_new_claim(monkeypatch, key, message):
    support, _ = _support(monkeypatch)
    support[key] = False
    with pytest.raises(RuntimeError, match=message):
        _validate_support(support)


def test_schema_11_validator_rejects_schema_10(monkeypatch):
    support, _ = _support(monkeypatch)
    support["schema"] = 10
    with pytest.raises(RuntimeError, match="SCHEMA11_RICH_INPUT_SUPPORT_NOT_PROVEN"):
        _validate_support(support)


def test_schema_11_validator_preserves_schema_10_claims(monkeypatch):
    support, _ = _support(monkeypatch)
    support["official_composer_required_for_attachment_evidence"] = False
    with pytest.raises(RuntimeError, match="OFFICIAL_COMPOSER_ATTACHMENT_EVIDENCE_NOT_PROVEN"):
        _validate_support(support)
