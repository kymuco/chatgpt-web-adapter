from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA27 = EXT / "service_worker_rich_input_schema27_repair_pr9_2.js"
DIAGNOSTIC = EXT / "service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js"
CLI = PKG / "product_rich_input_staging_diagnostic_schema27_pr9_2.py"


def test_schema_27_staging_diagnostic_loads_after_schema27_repair():
    text = LOADER.read_text(encoding="utf-8")
    schema27 = 'importScripts("service_worker_rich_input_schema27_repair_pr9_2.js");'
    diagnostic = 'importScripts("service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js");'
    assert schema27 in text
    assert diagnostic in text
    assert text.index(schema27) < text.index(diagnostic)


def test_schema_27_staging_diagnostic_is_explicitly_no_conversation_write():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "diagnosePr92StagedAttachmentEvidenceSchema27" in text
    assert "PR9_2_SCHEMA27_STAGING_DIAGNOSTIC_TEXT_FORBIDDEN" in text
    assert "conversationWritePerformed: false" in text
    assert "textInsertionPerformed: false" in text
    assert "protectedSubmitAttempted: false" in text
    assert "writePerformed: false" in text
    assert "fileUploadPerformed: true" in text
    assert "automaticWriteRetry: false" in text
    assert "fallbackTransport: null" in text


def test_schema_27_staging_diagnostic_uses_production_staging_and_latest_evidence():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "_pr92StageOfficialPageAttachments" in text
    assert "_pr92Schema26ReadStagedDiagnosticEvidence" in text
    assert "_pr92Schema27DiagnosticRemovalNormalization" in text
    assert "historical" in text
    assert "deliberately ignored" in text
    assert "pageOwned?.exactAttachmentSet !== true" in text
    assert "pageOwned?.crossEvidenceChannelExact !== true" in text
    assert "pageOwned?.indexedRemovalAmbiguityBidirectionalFailClosed !== true" in text
    assert "schema27Normalization?.singleAttachmentCrossChannelExact !== true" in text


def test_schema_27_staging_diagnostic_does_not_reach_conversation_submit_path():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    start = text.index("executeNativeTurn = async function _executeNativeTurnWithPr92Schema27StagingDiagnostic")
    diagnostic = text[start:]
    assert "submitOfficialPageTurn" not in diagnostic
    assert "button.click" not in diagnostic
    assert "insertComposerText" not in diagnostic
    flag = diagnostic.index("if (message?.diagnosePr92StagedAttachmentEvidenceSchema27 !== true)")
    prior = diagnostic.index("_pr92Schema27StagingDiagnosticPriorExecuteNativeTurn(message)", flag)
    staging = diagnostic.index("_pr92StageOfficialPageAttachments", prior)
    assert flag < prior < staging


def test_schema_27_staging_diagnostic_requires_cleanup_before_success():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    staged = text.index("const stagedCount = await _pr92StageOfficialPageAttachments")
    evidence = text.index("const evidence = await _pr92Schema26ReadStagedDiagnosticEvidence", staged)
    normalization = text.index("const schema27Normalization", evidence)
    cleanup = text.index("await _pr92RequireCleanAttachmentState(context)", normalization)
    fence_read = text.index("const remainingFence = await _pr92ReadDirtyAttachmentFence()", cleanup)
    result = text.index("return {", fence_read)
    assert staged < evidence < normalization < cleanup < fence_read < result
    assert "cleanupProven: true" in text[result:]
    assert "durableFenceCleared: true" in text[result:]
    assert "if (staged)" in text


def test_schema_27_staging_diagnostic_cli_uploads_one_fixture_but_sends_no_text():
    text = CLI.read_text(encoding="utf-8")
    request_start = text.index("response = provider._rpc")
    request_end = text.index("timeout=timeout", request_start)
    request = text[request_start:request_end]
    assert '"diagnosePr92StagedAttachmentEvidenceSchema27": True' in request
    assert '"attachmentPaths": [str(image_path)]' in request
    assert '"text"' not in request
    assert "uploads one fixture but performs no conversation write" in text


def test_schema_27_staging_diagnostic_cli_requires_latest_ambiguity_proof_and_cleanup():
    text = CLI.read_text(encoding="utf-8")
    assert 'response.get("conversationWritePerformed") is not False' in text
    assert 'response.get("textInsertionPerformed") is not False' in text
    assert 'response.get("protectedSubmitAttempted") is not False' in text
    assert 'evidence.get("exactAttachmentSet") is not True' in text
    assert 'evidence.get("crossEvidenceChannelExact") is not True' in text
    assert 'evidence.get("indexedRemovalAmbiguityBidirectionalFailClosed") is not True' in text
    assert 'normalization.get("singleAttachmentCrossChannelExact") is not True' in text
    assert 'response.get("cleanupProven") is not True' in text
    assert 'response.get("durableFenceCleared") is not True' in text
