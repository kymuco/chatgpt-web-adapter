from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA10 = EXT / "service_worker_rich_input_schema10_repair_pr9_2.js"


def test_schema_10_overlay_is_loaded_after_schema_9():
    text = LOADER.read_text(encoding="utf-8")
    schema9 = 'importScripts("service_worker_rich_input_schema9_repair_pr9_2.js");'
    schema10 = 'importScripts("service_worker_rich_input_schema10_repair_pr9_2.js");'
    assert schema9 in text
    assert schema10 in text
    assert text.index(schema9) < text.index(schema10)


def test_schema_10_requires_the_official_composer_for_attachment_evidence():
    text = SCHEMA10.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA10_REPAIR_SCHEMA = 10;" in text
    assert "document.querySelector('#prompt-textarea')" in text
    assert 'document.querySelector(\'[data-testid="prompt-textarea"]\')' in text
    assert "prompt instanceof Element ? prompt.closest('form') : null" in text
    assert "officialComposerMounted: false" in text
    assert "officialComposerMounted: true" in text
    assert "document.querySelector('form') || document.body" not in text
    assert "document.querySelector('[contenteditable=\"true\"]')" not in text


def test_schema_10_uses_whole_basename_association_not_substring_aliases():
    text = SCHEMA10.read_text(encoding="utf-8")
    assert "const exactGroupBasename = (label, name) => label === name;" in text
    assert "if (!label.endsWith(name)) return false;" in text
    assert "label.includes(name)" not in text
    assert "exactBasenameAssociationRequired: true" in text

    def removal_match(label: str, name: str) -> bool:
        if label == name:
            return True
        if not label.endswith(name):
            return False
        prefix = label[: len(label) - len(name)]
        if not prefix:
            return True
        return prefix[-1].isspace() or prefix[-1] in "\"'(:["

    assert removal_match("Remove report.txt", "report.txt") is True
    assert removal_match('Delete file: "report.txt', "report.txt") is True
    assert removal_match("old-report.txt", "report.txt") is False
    assert removal_match("Remove old-report.txt", "report.txt") is False
    assert removal_match("report.txt.bak", "report.txt") is False


def test_schema_10_bounds_prestage_debugger_setup_and_detaches_late_attach():
    text = SCHEMA10.read_text(encoding="utf-8")
    prestage = text[
        text.index("async function _pr92Schema10RequireOfficialCleanComposerBeforeStaging") :
        text.index("_pr92StageOfficialPageAttachments = async function _pr92Schema10StageFromOfficialCleanComposer")
    ]
    assert '"SCHEMA10_PRESTAGE_CLEAN_DEBUGGER_ATTACH"' in prestage
    assert '"SCHEMA10_PRESTAGE_CLEAN_RUNTIME_ENABLE"' in prestage
    assert "await _pr92Schema7RunUntil(" in prestage
    assert "attachPending.then(" in prestage
    assert "_pr92Schema10BestEffortDetach(debuggee)" in prestage
    assert "await chrome.debugger.attach" not in prestage
    assert 'await chrome.debugger.sendCommand(debuggee, "Runtime.enable")' not in prestage
    assert "preStageDebuggerSetupDeadlineBounded: true" in text
    assert "latePreStageDebuggerAttachAutoDetached: true" in text


def test_schema_10_bypasses_only_the_schema_8_unbounded_prestage_wrapper():
    text = SCHEMA10.read_text(encoding="utf-8")
    assert "await _pr92Schema10RequireOfficialCleanComposerBeforeStaging" in text
    assert "return _pr92Schema8PriorStageOfficialPageAttachments(" in text
    assert (
        "_pr92ClosureAttachmentEvidenceExpression = _pr92Schema10AttachmentEvidenceExpression;"
        in text
    )
