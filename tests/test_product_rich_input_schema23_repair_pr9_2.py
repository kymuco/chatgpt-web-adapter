from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA23 = EXT / "service_worker_rich_input_schema23_repair_pr9_2.js"
GATE23 = PKG / "product_rich_input_live_gate_schema23_pr9_2.py"


def test_schema_23_overlay_is_loaded_after_schema_22():
    text = LOADER.read_text(encoding="utf-8")
    schema22 = 'importScripts("service_worker_rich_input_schema22_repair_pr9_2.js");'
    schema23 = 'importScripts("service_worker_rich_input_schema23_repair_pr9_2.js");'
    assert schema22 in text
    assert schema23 in text
    assert text.index(schema22) < text.index(schema23)


def test_schema_23_filename_role_group_channel_no_longer_depends_on_remove_control():
    text = SCHEMA23.read_text(encoding="utf-8")
    group_start = text.index("const rawGroupElements")
    group_end = text.index("const removalLabels", group_start)
    group_block = text[group_start:group_end]
    assert "attachmentGroupElements" in group_block
    assert ".filter((element) => !isOfficialComposerControlGroup(element))" in group_block
    assert "hasVisibleStructuredRemovalControl" not in group_block
    assert ".filter(hasVisibleStructuredRemovalControl)" not in text
    assert "filenameGroupIndependentOfRemovalControl: true" in text


def test_schema_23_excludes_only_structurally_proven_composer_control_groups():
    text = SCHEMA23.read_text(encoding="utf-8")
    start = text.index("const officialComposerControlSelectors")
    end = text.index("const rawGroupElements", start)
    block = text[start:end]
    assert 'button[data-testid="composer-plus-btn"]' in block
    assert 'button[data-testid="composer-button-add-files"]' in block
    assert 'button[data-testid="send-button"]' in block
    assert 'button[data-testid="composer-submit-button"]' in block
    assert "group.contains(prompt)" in block
    assert "group.querySelector(selector) instanceof Element" in block
    # Do not turn arbitrary localized aria-label text into an exclusion allowlist.
    assert "getAttribute('aria-label')" not in block


def test_schema_23_unclassified_filename_group_remains_fail_closed_evidence():
    text = SCHEMA23.read_text(encoding="utf-8")
    assert "unclassifiedRoleGroupsFailClosedAsAttachmentEvidence: true" in text
    assert "unknownRoleGroupsFailClosed: true" in text
    assert "const groupLabels = attachmentGroupElements" in text
    assert "matchesExpectedExactly(groupLabels, exactGroupBasename)" in text
    assert "expected.length === 0" in text
    assert "groups.exact && removals.exact" in text


def test_schema_23_keeps_removal_channel_independent_from_filename_groups():
    text = SCHEMA23.read_text(encoding="utf-8")
    removal_start = text.index("const removalLabels")
    removal_end = text.index("const exactGroupBasename", removal_start)
    removal_block = text[removal_start:removal_end]
    assert "composer.querySelectorAll(removalControlSelector)" in removal_block
    assert ".filter(isStructuredRemovalLabel);" in removal_block
    assert "attachmentGroupElements" not in removal_block
    assert "groupLabels" not in removal_block


def test_schema_23_support_contract_supersedes_schema_22_removal_dependency():
    text = SCHEMA23.read_text(encoding="utf-8")
    assert "richInputSchemaVersion: PR92_SCHEMA23_REPAIR_SCHEMA" in text
    assert "attachmentEvidenceRoleGroupsRequireRemovalControl: false" in text
    assert "attachmentFilenameGroupsIndependentOfRemovalControls: true" in text
    assert "composerControlGroupExclusionUsesStructure: true" in text
    assert "unclassifiedRoleGroupsFailClosedAsAttachmentEvidence: true" in text


def test_schema_23_gate_validates_schema_21_chain_then_new_contract():
    text = GATE23.read_text(encoding="utf-8")
    assert "SCHEMA = 23" in text
    assert "class ProductRichInputSchema23LiveProvider" in text
    assert 'legacy["schema"] = _v21.SCHEMA' in text
    assert "_v21._validate_support(legacy)" in text
    assert "_v22._validate_support" not in text
    assert "attachment_filename_groups_independent_of_removal_controls" in text
    assert "composer_control_group_exclusion_uses_structure" in text
    assert "unclassified_role_groups_fail_closed_as_attachment_evidence" in text
    assert "PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET" in text


def test_schema_23_support_probe_is_seventeenth_no_write_characterization_rpc():
    text = GATE23.read_text(encoding="utf-8")
    assert "Seventeenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
