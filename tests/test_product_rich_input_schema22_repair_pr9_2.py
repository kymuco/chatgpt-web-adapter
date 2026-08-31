from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA22 = EXT / "service_worker_rich_input_schema22_repair_pr9_2.js"
GATE22 = PKG / "product_rich_input_live_gate_schema22_pr9_2.py"


def test_schema_22_overlay_is_loaded_after_schema_21():
    text = LOADER.read_text(encoding="utf-8")
    schema21 = 'importScripts("service_worker_rich_input_schema21_repair_pr9_2.js");'
    schema22 = 'importScripts("service_worker_rich_input_schema22_repair_pr9_2.js");'
    assert schema21 in text
    assert schema22 in text
    assert text.index(schema21) < text.index(schema22)


def test_schema_22_role_group_evidence_requires_attachment_removal_control():
    text = SCHEMA22.read_text(encoding="utf-8")
    assert "rawGroupElements" in text
    assert ".filter(hasVisibleStructuredRemovalControl)" in text
    assert "hasVisibleStructuredRemovalControl" in text
    assert "removalControlSelector" in text
    assert "rawGroupLabelCount" in text
    assert "ignoredComposerGroupLabelCount" in text


def test_schema_22_keeps_structured_removal_channel_independent():
    text = SCHEMA22.read_text(encoding="utf-8")
    assert "const removalLabels = Array.from(composer.querySelectorAll(removalControlSelector))" in text
    assert ".filter(isStructuredRemovalLabel);" in text
    assert "removalControlBasename(label) === name" in text
    assert "groupsCompatible" in text
    assert "removalsCompatible" in text
    assert "crossEvidenceChannelExact" in text


def test_schema_22_clean_composer_ignores_unrelated_role_groups_without_weakening_removal_evidence():
    text = SCHEMA22.read_text(encoding="utf-8")
    group_start = text.index("const rawGroupElements")
    group_end = text.index("const removalLabels", group_start)
    group_block = text[group_start:group_end]
    assert "querySelectorAll('[role=\"group\"][aria-label]')" in group_block
    assert ".filter(hasVisibleStructuredRemovalControl)" in group_block

    removal_start = text.index("const removalLabels")
    removal_end = text.index("const exactGroupBasename", removal_start)
    removal_block = text[removal_start:removal_end]
    assert "composer.querySelectorAll(removalControlSelector)" in removal_block
    assert "group" not in removal_block.lower()


def test_schema_22_support_contract_advertises_live_ui_classification_repair():
    text = SCHEMA22.read_text(encoding="utf-8")
    assert "richInputSchemaVersion: PR92_SCHEMA22_REPAIR_SCHEMA" in text
    assert "attachmentEvidenceRoleGroupsRequireRemovalControl: true" in text
    assert "composerControlRoleGroupsExcludedFromAttachmentEvidence: true" in text
    assert "preStageCleanUsesAttachmentOwnedEvidenceOnly: true" in text


def test_schema_22_gate_preserves_schema_21_and_requires_new_fields():
    text = GATE22.read_text(encoding="utf-8")
    assert "SCHEMA = 22" in text
    assert "class ProductRichInputSchema22LiveProvider" in text
    assert 'legacy["schema"] = _v21.SCHEMA' in text
    assert "_v21._validate_support(legacy)" in text
    assert "attachment_evidence_role_groups_require_removal_control" in text
    assert "composer_control_role_groups_excluded_from_attachment_evidence" in text
    assert "pre_stage_clean_uses_attachment_owned_evidence_only" in text
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text


def test_schema_22_support_probe_is_sixteenth_no_write_characterization_rpc():
    text = GATE22.read_text(encoding="utf-8")
    assert "Sixteenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
