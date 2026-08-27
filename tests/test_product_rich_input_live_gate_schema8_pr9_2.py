from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_rich_input_live_gate_schema8_pr9_2 import (
    ProductRichInputSchema8LiveProvider,
    _validate_support,
)


def _raw_response(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": 8,
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
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "writePerformed": False,
    }


def test_schema_8_support_probe_performs_only_zero_write_characterizations(monkeypatch):
    provider = ProductRichInputSchema8LiveProvider()
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

    assert len(calls) == 2
    assert support["schema"] == 8
    assert support["pre_stage_composer_attachment_clean"] is True
    assert support["exact_composer_attachment_set_required"] is True
    assert support["destructive_cleanup_authority_revalidated_at_close"] is True
    assert support["destructive_cleanup_ownership_change_fails_closed"] is True


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("pre_stage_composer_attachment_clean", "PRE_STAGE_COMPOSER_ATTACHMENT_CLEAN_NOT_PROVEN"),
        ("exact_composer_attachment_set_required", "EXACT_COMPOSER_ATTACHMENT_SET_NOT_PROVEN"),
        (
            "destructive_cleanup_authority_revalidated_at_close",
            "DESTRUCTIVE_CLEANUP_REVALIDATION_NOT_PROVEN",
        ),
        (
            "destructive_cleanup_ownership_change_fails_closed",
            "DESTRUCTIVE_CLEANUP_OWNERSHIP_CHANGE_FAIL_CLOSED_NOT_PROVEN",
        ),
    ],
)
def test_schema_8_validator_requires_every_new_closure_claim(monkeypatch, field, error):
    provider = ProductRichInputSchema8LiveProvider()
    monkeypatch.setattr(
        provider,
        "_rpc",
        lambda payload, *, timeout, on_event=None: _raw_response(payload["request_id"]),
    )
    support = provider.rich_input_support(timeout=1.0)
    support[field] = False
    with pytest.raises(RuntimeError, match=error):
        _validate_support(support)


def test_schema_8_validator_rejects_schema_7_even_if_all_other_claims_match(monkeypatch):
    provider = ProductRichInputSchema8LiveProvider()
    monkeypatch.setattr(
        provider,
        "_rpc",
        lambda payload, *, timeout, on_event=None: _raw_response(payload["request_id"]),
    )
    support = provider.rich_input_support(timeout=1.0)
    support["schema"] = 7
    with pytest.raises(RuntimeError, match="SCHEMA8_RICH_INPUT_SUPPORT_NOT_PROVEN"):
        _validate_support(support)
