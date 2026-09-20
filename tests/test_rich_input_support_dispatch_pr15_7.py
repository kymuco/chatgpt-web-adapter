from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def test_support_only_rich_input_layers_no_longer_own_native_turn() -> None:
    support_only = [
        "service_worker_rich_input_deadline_repair_pr9_2.js",
        "service_worker_rich_input_schema7_core_pr9_2.js",
        "service_worker_rich_input_schema8_repair_pr9_2.js",
        "service_worker_rich_input_schema9_repair_pr9_2.js",
        "service_worker_rich_input_schema10_repair_pr9_2.js",
        "service_worker_rich_input_schema11_repair_pr9_2.js",
        "service_worker_rich_input_schema12_repair_pr9_2.js",
        "service_worker_rich_input_schema13_repair_pr9_2.js",
        "service_worker_rich_input_schema15_repair_pr9_2.js",
        "service_worker_rich_input_schema16_repair_pr9_2.js",
        "service_worker_rich_input_schema17_repair_pr9_2.js",
        "service_worker_rich_input_schema19_repair_pr9_2.js",
        "service_worker_rich_input_schema20_repair_pr9_2.js",
        "service_worker_rich_input_schema21_repair_pr9_2.js",
        "service_worker_rich_input_schema22_repair_pr9_2.js",
        "service_worker_rich_input_schema23_repair_pr9_2.js",
        "service_worker_rich_input_schema24_repair_pr9_2.js",
        "service_worker_rich_input_schema25_repair_pr9_2.js",
        "service_worker_rich_input_schema26_repair_pr9_2.js",
        "service_worker_rich_input_schema27_repair_pr9_2.js",
    ]
    for name in support_only:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name
        assert "AugmentSupportResult" in source, name


def test_mixed_rich_input_layers_keep_only_runtime_native_turn_ownership() -> None:
    mixed = [
        "service_worker_rich_input_pr9_2.js",
        "service_worker_rich_input_closure_repair_pr9_2.js",
        "service_worker_rich_input_schema14_repair_pr9_2.js",
        "service_worker_rich_input_schema18_repair_pr9_2.js",
        "service_worker_rich_input_schema28_repair_pr9_2.js",
        "service_worker_rich_input_schema29_repair_pr9_2.js",
    ]
    for name in mixed:
        source = _source(name)
        assert "executeNativeTurn =" in source, name
        assert "characterizeRichInputSupport" not in source, name


def test_rich_input_control_owner_matches_support_probe() -> None:
    owner = _source("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js")
    assert '"rich-input-diagnostics"' in owner
    assert "registerNativeTurnDiagnosticHandler(" in owner
    assert "message?.characterizeRichInputSupport === true" in owner
    assert "return _cwaRichInputSupportResult(message);" in owner


def test_rich_input_support_composition_preserves_historical_schema_order() -> None:
    owner = _source("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js")
    calls = [
        "_pr92RichInputBaseSupportResult(message)",
        "_pr92DeadlineRepairAugmentSupportResult(result)",
        "_pr92ClosureAugmentSupportResult(result)",
        *[
            f"_pr92Schema{schema}AugmentSupportResult(result)"
            for schema in range(7, 30)
        ],
    ]
    positions = [owner.index(call) for call in calls]
    assert positions == sorted(positions)


def test_rich_input_support_probe_remains_no_write() -> None:
    base = _source("service_worker_rich_input_pr9_2.js")
    helper = base[base.index("function _pr92RichInputBaseSupportResult") :]
    assert "message?.text != null || message?.attachmentPaths != null" in helper
    assert "PR9_2_RICH_INPUT_SUPPORT_PROBE_MUST_BE_NO_WRITE" in helper
    assert "writePerformed: false" in helper


def test_combined_diagnostic_support_precedence_remains_explicit() -> None:
    owner = _source("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js")
    handler = owner[owner.index("async function _cwaHandleRichInputDiagnostic") :]
    schema28 = handler.index(
        "message?.diagnosePr92CommittedIdentityStateSchema28 === true"
    )
    schema27 = handler.index(
        "message?.diagnosePr92StagedAttachmentEvidenceSchema27 === true"
    )
    schema26 = handler.index("message?.diagnosePr92StagedAttachmentEvidence === true")
    composer = handler.index("message?.diagnosePr92ComposerEvidence === true")
    support = handler.index("message?.characterizeRichInputSupport === true")
    assert schema28 < schema27 < schema26 < composer < support
