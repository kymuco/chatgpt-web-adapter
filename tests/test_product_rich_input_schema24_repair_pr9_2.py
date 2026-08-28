from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA24 = EXT / "service_worker_rich_input_schema24_repair_pr9_2.js"
GATE24 = PKG / "product_rich_input_live_gate_schema24_pr9_2.py"


def test_schema_24_overlay_is_loaded_after_schema_23_and_before_diagnostic():
    text = LOADER.read_text(encoding="utf-8")
    schema23 = 'importScripts("service_worker_rich_input_schema23_repair_pr9_2.js");'
    schema24 = 'importScripts("service_worker_rich_input_schema24_repair_pr9_2.js");'
    diagnostic = 'importScripts("service_worker_rich_input_schema23_diagnostic_pr9_2.js");'
    assert schema23 in text
    assert schema24 in text
    assert diagnostic in text
    assert text.index(schema23) < text.index(schema24) < text.index(diagnostic)


def test_schema_24_waits_for_official_composer_before_empty_set_clean_polls():
    text = SCHEMA24.read_text(encoding="utf-8")
    runtime_enable = text.index("SCHEMA24_PRESTAGE_CLEAN_RUNTIME_ENABLE")
    readiness = text.index("waitForComposerReady", runtime_enable)
    evidence = text.index("_pr92ClosureReadPageOwnedAttachmentEvidence", readiness)
    assert runtime_enable < readiness < evidence
    assert "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_READY" in text
    assert "context.deadlineAt" in text
    assert "_pr92Schema7RunUntil" in text


def test_schema_24_preserves_exact_fail_closed_clean_evidence_after_mount():
    text = SCHEMA24.read_text(encoding="utf-8")
    assert "PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS" in text
    assert "evidence?.officialComposerMounted === true" in text
    assert "evidence?.exactBasenameAssociation === true" in text
    assert "evidence?.exactAttachmentSet === true" in text
    assert "groupCount === 0 && removalCount === 0" in text
    assert 'throw new Error("PR9_2_OFFICIAL_COMPOSER_NOT_CLEAN_BEFORE_STAGING")' in text
    assert "_pr92Schema15DetachWithinDeadline" in text


def test_schema_24_support_contract_records_mount_race_repair():
    text = SCHEMA24.read_text(encoding="utf-8")
    assert "richInputSchemaVersion: PR92_SCHEMA24_REPAIR_SCHEMA" in text
    assert "preStageOfficialComposerReadinessAwaited: true" in text
    assert "preStageOfficialComposerReadinessDeadlineBounded: true" in text
    assert "tabCompleteAloneCanProveComposerMounted: false" in text
    assert "missingComposerBeforeReadinessClassifiedDirty: false" in text
    assert "mountedAttachmentEvidenceStillFailsClosed: true" in text


def test_schema_24_gate_preserves_schema_23_and_requires_new_fields():
    text = GATE24.read_text(encoding="utf-8")
    assert "SCHEMA = 24" in text
    assert "class ProductRichInputSchema24LiveProvider" in text
    assert 'legacy["schema"] = _v23.SCHEMA' in text
    assert "_v23._validate_support(legacy)" in text
    assert "pre_stage_official_composer_readiness_awaited" in text
    assert "pre_stage_official_composer_readiness_deadline_bounded" in text
    assert "tab_complete_alone_can_prove_composer_mounted" in text
    assert "missing_composer_before_readiness_classified_dirty" in text
    assert "mounted_attachment_evidence_still_fails_closed" in text
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text


def test_schema_24_support_probe_is_eighteenth_no_write_characterization_rpc():
    text = GATE24.read_text(encoding="utf-8")
    assert "Eighteenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
