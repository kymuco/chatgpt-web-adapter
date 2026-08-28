from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA27 = EXT / "service_worker_rich_input_schema27_repair_pr9_2.js"
GATE27 = PKG / "product_rich_input_live_gate_schema27_pr9_2.py"


def _payload(label: str) -> str:
    value = label.strip()
    action = re.match(r"^(?:remove|delete|discard|удалить)(?:\s+|:\s*)", value, re.I)
    return value[action.end() :].strip() if action else ""


def _indexed_candidate(payload: str) -> str:
    match = re.match(
        r"^(?:file|image|attachment|document|файл|изображение|вложение|документ)\s+\d+\s*:\s*(.+)$",
        payload.strip(),
        re.I,
    )
    return match.group(1).strip() if match else ""


def _matches(label: str, expected: str, group_labels: list[str]) -> bool:
    payload = _payload(label)
    candidate = _indexed_candidate(payload)
    if not candidate:
        return payload == expected
    return (
        (payload == expected and payload in group_labels)
        or (candidate == expected and candidate in group_labels)
    )


def test_schema_27_overlay_loads_after_schema26_staging_diagnostic():
    text = LOADER.read_text(encoding="utf-8")
    schema26 = 'importScripts("service_worker_rich_input_schema26_repair_pr9_2.js");'
    staging26 = 'importScripts("service_worker_rich_input_schema26_staging_diagnostic_pr9_2.js");'
    schema27 = 'importScripts("service_worker_rich_input_schema27_repair_pr9_2.js");'
    assert schema26 in text
    assert staging26 in text
    assert schema27 in text
    assert text.index(schema26) < text.index(staging26) < text.index(schema27)


def test_schema_27_indexed_removal_only_fails_closed_for_stripped_interpretation():
    label = "Remove file 1: report.txt"
    assert not _matches(label, "report.txt", [])
    assert not _matches("Удалить файл 1: отчет.txt", "отчет.txt", [])


def test_schema_27_indexed_removal_only_fails_closed_for_literal_interpretation():
    label = "Remove file 1: report.txt"
    assert not _matches(label, "file 1: report.txt", [])
    assert not _matches("Удалить файл 3: отчет.txt", "файл 3: отчет.txt", [])


def test_schema_27_independent_group_selects_stripped_interpretation_exactly():
    label = "Удалить файл 1: pr9_2_attachment_evidence.png"
    expected = "pr9_2_attachment_evidence.png"
    assert _matches(label, expected, [expected])
    assert not _matches(label, "файл 1: pr9_2_attachment_evidence.png", [expected])


def test_schema_27_independent_group_can_select_literal_indexed_filename_exactly():
    label = "Remove file 1: report.txt"
    expected = "file 1: report.txt"
    assert _matches(label, expected, [expected])
    assert not _matches(label, "report.txt", [expected])


def test_schema_27_mismatched_or_malformed_groups_do_not_disambiguate():
    assert not _matches("Remove file 1: report.txt", "report.txt", ["old-report.txt"])
    assert not _matches("Remove file 1: report.txt", "file 1: report.txt", ["report.txt"])
    assert not _matches("Remove file x: report.txt", "report.txt", ["report.txt"])
    assert not _matches("Remove file 1 report.txt", "report.txt", ["report.txt"])
    assert not _matches("Remove unknown 1: report.txt", "report.txt", ["report.txt"])


def test_schema_27_unindexed_removal_preserves_literal_exact_semantics():
    assert _matches("Remove report.txt", "report.txt", [])
    assert _matches("Удалить отчет 2026.txt", "отчет 2026.txt", [])
    assert not _matches("Remove old report.txt", "report.txt", [])
    assert not _matches("Remove report.txt.bak", "report.txt", [])


def test_schema_27_production_matcher_requires_group_for_both_indexed_interpretations():
    text = SCHEMA27.read_text(encoding="utf-8")
    start = text.index("const exactRemovalBasename")
    end = text.index("const matchesExpectedExactly", start)
    matcher = text[start:end]
    assert "if (!candidate) return payload === name" in matcher
    assert "payload === name && groupLabels.includes(payload)" in matcher
    assert "candidate === name && groupLabels.includes(candidate)" in matcher
    assert "if (payload === name) return true" not in matcher
    assert ".endsWith(" not in matcher
    assert "label.includes(name)" not in matcher


def test_schema_27_preserves_exact_set_cross_channel_authority():
    text = SCHEMA27.read_text(encoding="utf-8")
    assert "groupsCompatible" in text
    assert "removalsCompatible" in text
    assert "atLeastOneExpectedChannelExact" in text
    assert "exactAttachmentSet = crossEvidenceChannelExact" in text
    assert "unknownRoleGroupsFailClosed: true" in text
    assert "filenameGroupIndependentOfRemovalControl: true" in text
    assert "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema27AttachmentEvidenceExpression" in text


def test_schema_27_diagnostic_reports_both_corroborated_interpretations():
    text = SCHEMA27.read_text(encoding="utf-8")
    assert "schema27RemovalNormalizationProof" in text
    assert "postActionPayload" in text
    assert "indexedCandidate" in text
    assert "indexedAmbiguous" in text
    assert "unambiguousLiteralBasename" in text
    assert "corroboratedLiteralBasename" in text
    assert "corroboratedIndexedBasename" in text
    assert "singleAttachmentCrossChannelExact" in text


def test_schema_27_support_explicitly_supersedes_schema25_and_schema26_parser_claims():
    text = GATE27.read_text(encoding="utf-8")
    assert "SCHEMA = 27" in text
    assert "class ProductRichInputSchema27LiveProvider" in text
    assert 'legacy["schema"] = _v24.SCHEMA' in text
    assert "_v24._validate_support(legacy)" in text
    assert "_v25._validate_support" not in text
    assert "_v26._validate_support" not in text
    assert "Schemas 25 and 26 are superseded parser experiments" in text
    assert "indexed_removal_ambiguity_bidirectional_fail_closed" in text
    assert "indexed_removal_literal_interpretation_requires_independent_filename_group" in text
    assert "indexed_removal_stripped_interpretation_requires_independent_filename_group" in text
    assert "indexed_removal_removal_only_authority_allowed" in text
    assert "unindexed_removal_literal_semantics_preserved" in text


def test_schema_27_support_probe_is_twenty_first_no_write_characterization_rpc():
    text = GATE27.read_text(encoding="utf-8")
    assert "Twenty-first characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    block = text[start:end]
    assert '"characterizeRichInputSupport": True' in block
    assert '"text"' not in block
    assert '"attachmentPaths"' not in block
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
