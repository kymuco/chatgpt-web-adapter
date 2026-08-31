from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA26 = EXT / "service_worker_rich_input_schema26_repair_pr9_2.js"
GATE26 = PKG / "product_rich_input_live_gate_schema26_pr9_2.py"


def _payload(label: str) -> str:
    value = label.strip()
    action = re.match(r"^(?:remove|delete|discard|удалить)(?:\s+|:\s*)", value, re.I)
    return value[action.end() :].strip() if action else ""


def _indexed_candidate(payload: str) -> str:
    indexed = re.match(
        r"^(?:file|image|attachment|document|файл|изображение|вложение|документ)\s+\d+\s*:\s*(.+)$",
        payload.strip(),
        re.I,
    )
    return indexed.group(1).strip() if indexed else ""


def _matches(label: str, expected: str, group_labels: list[str]) -> bool:
    payload = _payload(label)
    if payload == expected:
        return True
    candidate = _indexed_candidate(payload)
    return candidate == expected and candidate in group_labels


def test_schema_26_overlay_loads_after_schema25():
    text = LOADER.read_text(encoding="utf-8")
    schema25 = 'importScripts("service_worker_rich_input_schema25_repair_pr9_2.js");'
    schema26 = 'importScripts("service_worker_rich_input_schema26_repair_pr9_2.js");'
    assert schema25 in text
    assert schema26 in text
    assert text.index(schema25) < text.index(schema26)


def test_schema_26_preserves_literal_filename_that_looks_like_ui_metadata():
    assert _matches("Remove file 1: report.txt", "file 1: report.txt", [])
    assert _matches("Удалить файл 3: отчет.txt", "файл 3: отчет.txt", [])


def test_schema_26_accepts_current_indexed_ui_only_with_independent_group_corroboration():
    label = "Удалить файл 1: pr9_2_attachment_evidence.png"
    expected = "pr9_2_attachment_evidence.png"
    assert _matches(label, expected, [expected])
    assert _matches("Remove file 7: report.txt", "report.txt", ["report.txt"])


def test_schema_26_ambiguous_indexed_removal_only_evidence_fails_closed():
    assert not _matches("Remove file 1: report.txt", "report.txt", [])
    assert not _matches("Удалить файл 1: report.txt", "report.txt", [])


def test_schema_26_indexed_candidate_must_match_independent_group_exactly():
    assert not _matches("Remove file 1: report.txt", "report.txt", ["old-report.txt"])
    assert not _matches("Remove file 1: report.txt", "old-report.txt", ["old-report.txt"])
    assert not _matches("Remove file x: report.txt", "report.txt", ["report.txt"])
    assert not _matches("Remove file 1 report.txt", "report.txt", ["report.txt"])
    assert not _matches("Remove unknown 1: report.txt", "report.txt", ["report.txt"])


def test_schema_26_production_matcher_is_literal_first_then_group_corroborated():
    text = SCHEMA26.read_text(encoding="utf-8")
    assert "function _pr92Schema26RemovalPostActionPayload" in text
    assert "function _pr92Schema26IndexedRemovalCandidate" in text
    matcher = text[text.index("const exactRemovalBasename") : text.index("const matchesExpectedExactly")]
    assert "if (payload === name) return true" in matcher
    assert "candidate === name && groupLabels.includes(candidate)" in matcher
    assert ".endsWith(" not in matcher
    assert "label.includes(name)" not in matcher


def test_schema_26_keeps_existing_exact_set_cross_channel_authority():
    text = SCHEMA26.read_text(encoding="utf-8")
    assert "groupsCompatible" in text
    assert "removalsCompatible" in text
    assert "atLeastOneExpectedChannelExact" in text
    assert "crossEvidenceChannelExact" in text
    assert "exactAttachmentSet = crossEvidenceChannelExact" in text
    assert "unknownRoleGroupsFailClosed: true" in text
    assert "filenameGroupIndependentOfRemovalControl: true" in text
    assert "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema26AttachmentEvidenceExpression" in text


def test_schema_26_diagnostic_exposes_literal_and_corroborated_interpretations():
    text = SCHEMA26.read_text(encoding="utf-8")
    assert "schema26RemovalNormalizationProof" in text
    assert "literalBasename" in text
    assert "indexedCandidate" in text
    assert "corroboratedIndexedBasename" in text
    assert "singleAttachmentCrossChannelExact" in text
    diagnostic_block = text[text.index("if (message?.diagnosePr92ComposerEvidence") :]
    assert "button.click" not in diagnostic_block
    assert "DOM.setFileInputFiles" not in diagnostic_block


def test_schema_26_support_contract_records_ambiguity_boundary():
    text = SCHEMA26.read_text(encoding="utf-8")
    assert "indexedRemovalUiPrefixRequiresIndependentFilenameGroup: true" in text
    assert "removalOnlyIndexedUiPrefixNormalizationAllowed: false" in text
    assert "literalPostActionRemovalBasenamePreserved: true" in text
    assert "ambiguousIndexedRemovalLabelFailsClosedWithoutFilenameGroup: true" in text
    assert "indexedRemovalCandidateStillComparedExactly: true" in text


def test_schema_26_gate_preserves_schema25_and_requires_new_fields():
    text = GATE26.read_text(encoding="utf-8")
    assert "SCHEMA = 26" in text
    assert "class ProductRichInputSchema26LiveProvider" in text
    assert 'legacy["schema"] = _v25.SCHEMA' in text
    assert "_v25._validate_support(legacy)" in text
    assert "indexed_removal_ui_prefix_requires_independent_filename_group" in text
    assert "removal_only_indexed_ui_prefix_normalization_allowed" in text
    assert "literal_post_action_removal_basename_preserved" in text
    assert "ambiguous_indexed_removal_label_fails_closed_without_filename_group" in text
    assert "indexed_removal_candidate_still_compared_exactly" in text
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text


def test_schema_26_support_probe_is_twentieth_no_write_characterization_rpc():
    text = GATE26.read_text(encoding="utf-8")
    assert "Twentieth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
