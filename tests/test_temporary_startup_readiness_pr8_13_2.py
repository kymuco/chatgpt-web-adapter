from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
READINESS = EXTENSION / "service_worker_temporary_startup_readiness.js"
PRODUCTION = EXTENSION / "service_worker_temporary_product.js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr8132_helpers_load_before_temporary_product_owner() -> None:
    text = _text(OBSERVABILITY)
    readiness = 'importScripts("service_worker_temporary_startup_readiness.js");'
    temporary_product = 'importScripts("service_worker_temporary_product.js");'

    assert readiness in text
    assert temporary_product in text
    assert text.index(readiness) < text.index(temporary_product)
    assert "service_worker_temporary_startup_readiness_pr8_13_2.js" not in text


def test_fresh_readiness_is_bounded_and_non_authoritative() -> None:
    text = _text(READINESS)

    assert "PR8132_FRESH_READINESS_TIMEOUT_MS = 5_000" in text
    assert "PR8132_FRESH_READINESS_STABLE_MS = 750" in text
    assert "PR8132_FRESH_READINESS_REQUIRED_SAMPLES = 3" in text
    assert 'searchParams.get("temporary-chat") === "true"' in text
    assert "queryComposerReadiness(debuggee)" in text
    assert "_cwaTemporaryControlSnapshot" in text
    assert "_pr87TemporaryControlSnapshot" not in text
    assert "temporary_control_explicitly_false" in text
    assert "PR8_13_2_TEMPORARY_FRESH_READINESS_TIMEOUT" in text

    # The readiness layer is explicitly a delay/hint only. It must not create
    # or replace the PR8.13 request-body authority proof.
    assert "deliberately non-authoritative" in text
    assert "history_and_training_disabled === true" in text
    assert "remains the only prewrite" in text
    assert "Fetch.continueRequest" not in text
    assert "Fetch.failRequest" not in text


def test_original_pr813_fetch_fence_remains_authoritative_and_fail_closed() -> None:
    text = _text(PRODUCTION)

    assert "payload.history_and_training_disabled !== true" in text
    assert 'reason: "HISTORY_AND_TRAINING_DISABLED_NOT_TRUE"' in text
    assert '"Fetch.failRequest"' in text
    assert 'errorReason: "Aborted"' in text
    assert '"Fetch.continueRequest"' in text
    assert "PR8_13_TEMPORARY_PREWRITE_PROOF_FAILED" in text


def test_pr8132_abort_diagnostics_distinguish_observation_phase() -> None:
    text = _text(READINESS)

    assert "PR8_13_2_TEMPORARY_PREWRITE_ABORT" in text
    assert "PR8_13_2_TEMPORARY_ABORT_AFTER_PREWRITE_PROOF" in text
    assert "PR8_13_2_TEMPORARY_ABORT_WITHOUT_RETAINED_PROOF" in text
    assert "PR8_13_2_TEMPORARY_ABORT_BEFORE_FETCH_OBSERVATION" in text
    assert "pausedConversationWriteCount" in text
    assert "modeViolation" in text
    assert "prewriteProofKind" in text


def test_pr8132_does_not_add_automatic_write_retry_or_durable_fallback() -> None:
    text = _text(READINESS)

    assert "retry" not in text.lower()
    assert "durable" not in text.lower()
    assert (
        "async function _pr8132ExecuteNativeTurnWithStartupDiagnostics(message, next)"
        in text
    )
    assert "return next(message);" in text


def test_pr8132_readiness_applies_only_to_fresh_temporary_turns() -> None:
    text = _text(READINESS)

    assert "context.expectedConversationId === null" in text
    assert "freshReadinessApplied: true" in text
    assert "freshReadinessApplied: false" in text
    assert "temporaryFreshReadinessApplied" in text
    assert "temporaryFreshReadinessKind" in text


def test_startup_readiness_no_longer_reassigns_temporary_product_hooks() -> None:
    readiness = _text(READINESS)
    product = _text(PRODUCTION)

    for forbidden in (
        "_pr813ResolveProof =",
        "_pr813RejectProof =",
        "submitOfficialPageTurn =",
        "_pr8132PriorResolveProof",
        "_pr8132PriorRejectProof",
        "_pr8132PriorSubmitOfficialPageTurn",
    ):
        assert forbidden not in readiness

    assert "function _pr8132ResolveProofWithDiagnostics(" in readiness
    assert "function _pr8132RejectProofWithDiagnostics(" in readiness
    assert "async function _pr8132SubmitOfficialPageTurnWithReadiness(" in readiness

    assert "function _pr813ResolveProof(context, evidence)" in product
    assert "function _pr813RejectProof(context, error)" in product
    assert "async function _pr813SubmitOfficialPageTurn(" in product
    assert "submitOfficialPageTurn =" not in product
    assert "_pr813PriorSubmitOfficialPageTurn" not in product
    assert "_pr8132ResolveProofWithDiagnostics(" in product
    assert "_pr8132RejectProofWithDiagnostics(" in product
    assert "_pr8132SubmitOfficialPageTurnWithReadiness(" in product
