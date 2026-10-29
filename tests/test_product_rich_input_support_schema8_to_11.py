from __future__ import annotations

import importlib

import pytest


# Schema 8–11 support checks share a cumulative wire response, not four copies
# of the same historical fixture. None of these tests performs a product write.
SCHEMAS = (8, 9, 10, 11)

NEW_CLAIMS = {
    8: (
        (
            "pre_stage_composer_attachment_clean",
            "PRE_STAGE_COMPOSER_ATTACHMENT_CLEAN_NOT_PROVEN",
        ),
        (
            "exact_composer_attachment_set_required",
            "EXACT_COMPOSER_ATTACHMENT_SET_NOT_PROVEN",
        ),
        (
            "destructive_cleanup_authority_revalidated_at_close",
            "DESTRUCTIVE_CLEANUP_REVALIDATION_NOT_PROVEN",
        ),
        (
            "destructive_cleanup_ownership_change_fails_closed",
            "DESTRUCTIVE_CLEANUP_OWNERSHIP_CHANGE_FAIL_CLOSED_NOT_PROVEN",
        ),
    ),
    9: (
        (
            "cross_evidence_channel_exactness",
            "CROSS_EVIDENCE_CHANNEL_EXACTNESS_NOT_PROVEN",
        ),
    ),
    10: (
        (
            "official_composer_required_for_attachment_evidence",
            "OFFICIAL_COMPOSER_ATTACHMENT_EVIDENCE_NOT_PROVEN",
        ),
        (
            "exact_basename_association_required",
            "EXACT_BASENAME_ASSOCIATION_NOT_PROVEN",
        ),
        (
            "prestage_debugger_setup_deadline_bounded",
            "PRESTAGE_DEBUGGER_SETUP_DEADLINE_NOT_PROVEN",
        ),
        (
            "late_prestage_debugger_attach_auto_detached",
            "LATE_PRESTAGE_DEBUGGER_ATTACH_DETACH_NOT_PROVEN",
        ),
    ),
    11: (
        (
            "structured_removal_control_basename_parsing",
            "STRUCTURED_REMOVAL_BASENAME_NOT_PROVEN",
        ),
        (
            "attachment_evidence_reads_deadline_bounded",
            "ATTACHMENT_EVIDENCE_READ_DEADLINE_NOT_PROVEN",
        ),
    ),
}


def _raw_response(request_id: str, schema: int) -> dict:
    return {
        "request_id": request_id,
        "ok": True,
        "richInputSupported": True,
        "richInputSchemaVersion": schema,
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



def _module(schema: int):
    return importlib.import_module(
        f"chatgpt_web_adapter.product_rich_input_live_gate_schema{schema}_pr9_2"
    )


def _support(monkeypatch, schema: int):
    module = _module(schema)
    provider = getattr(module, f"ProductRichInputSchema{schema}LiveProvider")()
    calls = []

    def fake_rpc(payload, *, timeout, on_event=None):
        calls.append(dict(payload))
        assert payload["characterizeRichInputSupport"] is True
        assert "text" not in payload
        assert "attachmentPaths" not in payload
        return _raw_response(payload["request_id"], schema)

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    return module, provider.rich_input_support(timeout=1.0), calls


@pytest.mark.parametrize("schema", SCHEMAS)
def test_legacy_support_preflight_is_read_only_and_preserves_new_claims(
    monkeypatch, schema
):
    module, support, calls = _support(monkeypatch, schema)
    module._validate_support(support)

    assert len(calls) == schema - 6
    assert module.PRODUCT_WRITE_BUDGET == 3
    assert support["schema"] == schema
    for key, _error in NEW_CLAIMS[schema]:
        assert support[key] is True


@pytest.mark.parametrize(
    ("schema", "field", "error"),
    [
        (schema, field, error)
        for schema, claims in NEW_CLAIMS.items()
        for field, error in claims
    ],
)
def test_legacy_support_rejects_each_missing_safety_claim(
    monkeypatch, schema, field, error
):
    module, support, _calls = _support(monkeypatch, schema)
    support[field] = False
    with pytest.raises(RuntimeError, match=error):
        module._validate_support(support)


@pytest.mark.parametrize("schema", SCHEMAS)
def test_legacy_support_rejects_previous_schema(monkeypatch, schema):
    module, support, _calls = _support(monkeypatch, schema)
    support["schema"] = schema - 1
    with pytest.raises(
        RuntimeError,
        match=f"SCHEMA{schema}_RICH_INPUT_SUPPORT_NOT_PROVEN",
    ):
        module._validate_support(support)


@pytest.mark.parametrize(
    ("schema", "field", "error"),
    [
        (
            9,
            "exact_composer_attachment_set_required",
            "EXACT_COMPOSER_ATTACHMENT_SET_NOT_PROVEN",
        ),
        (
            10,
            "cross_evidence_channel_exactness",
            "CROSS_EVIDENCE_CHANNEL_EXACTNESS_NOT_PROVEN",
        ),
        (
            11,
            "official_composer_required_for_attachment_evidence",
            "OFFICIAL_COMPOSER_ATTACHMENT_EVIDENCE_NOT_PROVEN",
        ),
    ],
)
def test_legacy_support_preserves_prior_schema_fail_closed_claims(
    monkeypatch, schema, field, error
):
    module, support, _calls = _support(monkeypatch, schema)
    support[field] = False
    with pytest.raises(RuntimeError, match=error):
        module._validate_support(support)
