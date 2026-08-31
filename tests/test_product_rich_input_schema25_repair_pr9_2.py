from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA25 = EXT / "service_worker_rich_input_schema25_repair_pr9_2.js"
GATE25 = PKG / "product_rich_input_live_gate_schema25_pr9_2.py"


def _mirror_schema25_removal_basename(label: str) -> str:
    value = label.strip()
    action = re.match(r"^(?:remove|delete|discard|удалить)(?:\s+|:\s*)", value, re.I)
    if not action:
        return ""
    payload = value[action.end() :].strip()
    indexed = re.match(
        r"^(?:file|image|attachment|document|файл|изображение|вложение|документ)\s+\d+\s*:\s*(.+)$",
        payload,
        re.I,
    )
    return (indexed.group(1) if indexed else payload).strip()


def test_schema_25_overlay_loads_after_schema24_and_diagnostic():
    text = LOADER.read_text(encoding="utf-8")
    schema24 = 'importScripts("service_worker_rich_input_schema24_repair_pr9_2.js");'
    diagnostic = 'importScripts("service_worker_rich_input_schema23_diagnostic_pr9_2.js");'
    schema25 = 'importScripts("service_worker_rich_input_schema25_repair_pr9_2.js");'
    assert schema24 in text
    assert diagnostic in text
    assert schema25 in text
    assert text.index(schema24) < text.index(diagnostic) < text.index(schema25)


def test_schema_25_normalizes_observed_localized_indexed_removal_label_exactly():
    assert (
        _mirror_schema25_removal_basename(
            "Удалить файл 1: pr9_2_attachment_evidence.png"
        )
        == "pr9_2_attachment_evidence.png"
    )
    assert _mirror_schema25_removal_basename("Remove file 7: report.txt") == "report.txt"
    assert _mirror_schema25_removal_basename("Delete image 2: frame.png") == "frame.png"


def test_schema_25_does_not_reintroduce_suffix_or_substring_aliases():
    assert _mirror_schema25_removal_basename("Remove old report.txt") == "old report.txt"
    assert _mirror_schema25_removal_basename("Remove file x: report.txt") == "file x: report.txt"
    assert _mirror_schema25_removal_basename("Remove file 1 report.txt") == "file 1 report.txt"
    assert _mirror_schema25_removal_basename("Remove file 1: old-report.txt") == "old-report.txt"
    assert _mirror_schema25_removal_basename("Open file 1: report.txt") == ""
    assert _mirror_schema25_removal_basename("Удалить что-то 1: report.txt") == "что-то 1: report.txt"


def test_schema_25_production_expression_uses_one_shared_anchored_parser():
    text = SCHEMA25.read_text(encoding="utf-8")
    assert "function _pr92Schema25RemovalControlBasename" in text
    assert "_pr92Schema25RemovalControlBasename.toString()" in text
    assert "const removalControlBasename = ${removalParser};" in text
    assert "\\s+\\d+\\s*:\\s*(.+)$" in text
    assert "exactRemovalBasename = (label, name) => removalControlBasename(label) === name" in text
    expression_start = text.index("function _pr92Schema25AttachmentEvidenceExpression")
    expression_end = text.index("_pr92ClosureAttachmentEvidenceExpression =", expression_start)
    expression = text[expression_start:expression_end]
    assert ".includes(name)" not in expression
    assert ".endsWith(name)" not in expression


def test_schema_25_keeps_cross_channel_and_unknown_group_fail_closed_authority():
    text = SCHEMA25.read_text(encoding="utf-8")
    assert "groupsCompatible" in text
    assert "removalsCompatible" in text
    assert "atLeastOneExpectedChannelExact" in text
    assert "crossEvidenceChannelExact" in text
    assert "exactAttachmentSet = crossEvidenceChannelExact" in text
    assert "unknownRoleGroupsFailClosed: true" in text
    assert "filenameGroupIndependentOfRemovalControl: true" in text
    assert "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema25AttachmentEvidenceExpression" in text


def test_schema_25_diagnostic_reports_live_normalization_without_write_authority():
    text = SCHEMA25.read_text(encoding="utf-8")
    assert "_pr92Schema25DiagnosticRemovalNormalization" in text
    assert "schema25RemovalNormalizationProof" in text
    assert "singleAttachmentCrossChannelExact" in text
    assert "richInputSchemaVersion: PR92_SCHEMA25_REPAIR_SCHEMA" in text
    diagnostic_block = text[text.index("if (message?.diagnosePr92ComposerEvidence") :]
    assert "button.click" not in diagnostic_block
    assert "DOM.setFileInputFiles" not in diagnostic_block


def test_schema_25_support_contract_is_narrow_and_fail_closed():
    text = SCHEMA25.read_text(encoding="utf-8")
    assert "indexedRemovalUiPrefixNormalizationSupported: true" in text
    assert "indexedRemovalUiPrefixRequiresKnownNounOrdinalAndColon: true" in text
    assert "indexedRemovalUiPrefixBasenameComparedExactly: true" in text
    assert "unknownRemovalUiMetadataStillFailsClosed: true" in text
    assert "removalNormalizationSharedByProductionAndDiagnostic: true" in text


def test_schema_25_gate_preserves_schema24_and_requires_new_fields():
    text = GATE25.read_text(encoding="utf-8")
    assert "SCHEMA = 25" in text
    assert "class ProductRichInputSchema25LiveProvider" in text
    assert 'legacy["schema"] = _v24.SCHEMA' in text
    assert "_v24._validate_support(legacy)" in text
    assert "indexed_removal_ui_prefix_normalization_supported" in text
    assert "indexed_removal_ui_prefix_requires_known_noun_ordinal_and_colon" in text
    assert "indexed_removal_ui_prefix_basename_compared_exactly" in text
    assert "unknown_removal_ui_metadata_still_fails_closed" in text
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text


def test_schema_25_support_probe_is_nineteenth_no_write_characterization_rpc():
    text = GATE25.read_text(encoding="utf-8")
    assert "Nineteenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
