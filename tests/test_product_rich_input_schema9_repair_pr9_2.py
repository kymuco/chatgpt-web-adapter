from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA9 = EXT / "service_worker_rich_input_schema9_repair_pr9_2.js"


def test_schema_9_overlay_is_loaded_after_schema_7_and_schema_8():
    text = LOADER.read_text(encoding="utf-8")
    core = 'importScripts("service_worker_rich_input_schema7_core_pr9_2.js");'
    schema8 = 'importScripts("service_worker_rich_input_schema8_repair_pr9_2.js");'
    schema9 = 'importScripts("service_worker_rich_input_schema9_repair_pr9_2.js");'

    for item in (core, schema8, schema9):
        assert item in text
    assert text.index(core) < text.index(schema8) < text.index(schema9)


def test_schema_9_requires_cross_channel_attachment_exactness():
    text = SCHEMA9.read_text(encoding="utf-8")

    assert "const PR92_SCHEMA9_REPAIR_SCHEMA = 9;" in text
    assert "_pr92Schema9AttachmentEvidenceExpression" in text
    assert "const groupsCompatible = groupLabels.length === 0 || groups.exact;" in text
    assert "const removalsCompatible = removalLabels.length === 0 || removals.exact;" in text
    assert "const atLeastOneExpectedChannelExact = groups.exact || removals.exact;" in text
    assert "groupsCompatible && removalsCompatible && atLeastOneExpectedChannelExact" in text
    assert "crossEvidenceChannelExactness: true" in text
    assert (
        "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema9AttachmentEvidenceExpression;"
        in text
    )


def test_schema_9_rejects_the_schema_8_cross_channel_counterexample():
    # Schema 8 could accept one exact channel while a second same-sized evidence
    # channel described a different/extra attachment. Schema 9 requires every
    # non-empty channel to be independently exact.
    expected_count = 1
    group_count = 1
    removal_count = 1
    groups_exact = True
    removals_exact = False

    old_schema_8 = (
        group_count <= expected_count
        and removal_count <= expected_count
        and (groups_exact or removals_exact)
    )
    assert old_schema_8 is True

    groups_compatible = group_count == 0 or groups_exact
    removals_compatible = removal_count == 0 or removals_exact
    schema_9 = (
        groups_compatible
        and removals_compatible
        and (groups_exact or removals_exact)
    )
    assert schema_9 is False


def test_schema_9_keeps_empty_secondary_evidence_channel_compatible():
    expected_count = 1
    group_count = 1
    removal_count = 0
    groups_exact = True
    removals_exact = False

    groups_compatible = group_count == 0 or groups_exact
    removals_compatible = removal_count == 0 or removals_exact
    schema_9 = (
        groups_compatible
        and removals_compatible
        and (groups_exact or removals_exact)
    )
    assert schema_9 is True
