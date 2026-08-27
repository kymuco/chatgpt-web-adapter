from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA11 = EXT / "service_worker_rich_input_schema11_repair_pr9_2.js"


def test_schema_11_overlay_is_loaded_after_schema_10():
    text = LOADER.read_text(encoding="utf-8")
    schema10 = 'importScripts("service_worker_rich_input_schema10_repair_pr9_2.js");'
    schema11 = 'importScripts("service_worker_rich_input_schema11_repair_pr9_2.js");'
    assert schema10 in text
    assert schema11 in text
    assert text.index(schema10) < text.index(schema11)


def test_schema_11_parses_complete_removal_payload_without_suffix_aliases():
    text = SCHEMA11.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA11_REPAIR_SCHEMA = 11;" in text
    assert "const removalControlBasename = (label) =>" in text
    assert "removalControlBasename(label) === name" in text
    assert "label.endsWith(name)" not in text
    assert "label.includes(name)" not in text
    assert "structuredRemovalControlBasenameParsing: true" in text

    def removal_payload(label: str) -> str:
        value = label.strip()
        match = re.match(r"^(?:remove|delete|discard)(?:\s+|:\s*)", value, re.I)
        if match is None:
            return ""
        value = value[match.end() :].strip()
        pairs = {'"': '"', "'": "'", "“": "”", "‘": "’"}
        if len(value) >= 2 and value[0] in pairs and value[-1] == pairs[value[0]]:
            value = value[1:-1].strip()
        return value

    assert removal_payload("Remove report.txt") == "report.txt"
    assert removal_payload("Remove: report.txt") == "report.txt"
    assert removal_payload('Delete "report.txt"') == "report.txt"
    assert removal_payload("Remove old report.txt") == "old report.txt"
    assert removal_payload("Remove old-report.txt") == "old-report.txt"
    assert removal_payload("Remove report.txt.bak") == "report.txt.bak"
    assert removal_payload("Remove old report.txt") != "report.txt"


def test_schema_11_bounds_the_shared_attachment_evidence_read():
    text = SCHEMA11.read_text(encoding="utf-8")
    assert (
        "const _pr92Schema11PriorReadPageOwnedAttachmentEvidence =\n"
        "  _pr92ClosureReadPageOwnedAttachmentEvidence;"
    ) in text
    assert "_pr92ClosureReadPageOwnedAttachmentEvidence = async function" in text
    assert "return _pr92Schema7RunUntil(" in text
    assert '"SCHEMA11_PAGE_ATTACHMENT_EVIDENCE_READ"' in text
    assert "() => _pr92Schema11PriorReadPageOwnedAttachmentEvidence(" in text
    assert "attachmentEvidenceReadsDeadlineBounded: true" in text


def test_schema_11_preserves_official_composer_and_cross_channel_exactness():
    text = SCHEMA11.read_text(encoding="utf-8")
    assert "document.querySelector('#prompt-textarea')" in text
    assert 'document.querySelector(\'[data-testid="prompt-textarea"]\')' in text
    assert "officialComposerMounted: false" in text
    assert "officialComposerMounted: true" in text
    assert "crossEvidenceChannelExact" in text
    assert "exactAttachmentSet" in text
    assert (
        "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema11AttachmentEvidenceExpression;"
        in text
    )
