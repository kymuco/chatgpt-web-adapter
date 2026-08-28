from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
DIAGNOSTIC = EXT / "service_worker_rich_input_schema23_diagnostic_pr9_2.js"
CLI = PKG / "product_rich_input_composer_diagnostic_pr9_2.py"


def test_schema23_diagnostic_overlay_loads_after_schema24_repair():
    text = LOADER.read_text(encoding="utf-8")
    schema24 = 'importScripts("service_worker_rich_input_schema24_repair_pr9_2.js");'
    diagnostic = 'importScripts("service_worker_rich_input_schema23_diagnostic_pr9_2.js");'
    assert schema24 in text
    assert diagnostic in text
    assert text.index(schema24) < text.index(diagnostic)


def test_composer_diagnostic_is_explicitly_zero_write_and_zero_staging():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "diagnosePr92ComposerEvidence" in text
    assert 'message?.text != null || message?.attachmentPaths != null' in text
    assert 'writePerformed: false' in text
    assert 'attachmentStagingPerformed: false' in text
    assert 'protectedSubmitAttempted: false' in text
    assert "DOM.setFileInputFiles" not in text
    assert "button.click()" not in text
    assert "Input.dispatch" not in text


def test_composer_diagnostic_reports_schema23_retained_groups_and_structure():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "visibleRoleGroupCount" in text
    assert "schema23RetainedRoleGroupCount" in text
    assert "schema23ExcludedAsComposerControl" in text
    assert "stableComposerControls" in text
    assert "containsPrompt" in text
    assert "ariaLabel" in text
    assert "testId" in text
    assert "descendants" in text


def test_composer_diagnostic_executes_exact_schema24_production_clean_dry_run():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "_pr92Schema24WaitForOfficialComposerMounted" in text
    assert "_pr92Schema24EvidenceIsClean" in text
    assert "_pr92ClosureReadPageOwnedAttachmentEvidence" in text
    assert "PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS" in text
    assert "productionCleanProof" in text
    assert "allPollsClean" in text
    assert "waitForComposerReady" not in text


def test_composer_diagnostic_awaits_successful_debugger_detach_before_return():
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    result = text.index("const result = {")
    detach = text.index("await _pr92Schema15DetachWithinDeadline", result)
    clear = text.index("attached = false", detach)
    returned = text.index("return result", clear)
    finally_block = text.index("} finally {", returned)
    assert result < detach < clear < returned < finally_block
    assert '"SCHEMA24_DIAGNOSTIC_DEBUGGER_DETACH"' in text
    assert "_pr92Schema23DiagnosticBestEffortDetach(debuggee)" in text[finally_block:]


def test_composer_diagnostic_cli_sends_no_text_or_attachment_paths():
    text = CLI.read_text(encoding="utf-8")
    start = text.index("response = provider._rpc")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"diagnosePr92ComposerEvidence": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert 'response.get("writePerformed") is not False' in text
    assert 'response.get("attachmentStagingPerformed") is not False' in text
    assert 'response.get("protectedSubmitAttempted") is not False' in text
    assert '"production_clean_proof": response.get("productionCleanProof")' in text
