from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPAT = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_ui_compat_pr11_7.js"
)


def test_empty_composer_drift_uses_bounded_locale_neutral_structural_evidence() -> None:
    source = COMPAT.read_text(encoding="utf-8")

    assert "currentEmptyComposerEvidence" in source
    assert "element.getAttribute('contenteditable') !== 'true'" in source
    assert "element.getAttribute('role') !== 'textbox'" in source
    assert "element.getAttribute('aria-multiline') !== 'true'" in source
    assert "!element.closest('main') || !element.closest('form')" in source
    assert (
        '\'[contenteditable="true"][role="textbox"][aria-multiline="true"]\''
    ) in source
    assert "visible(candidate)" in source
    assert "writable(candidate)" in source
    assert "candidate.closest('main')" in source
    assert "candidate.closest('form')" in source
    assert "peers.length === 1 && peers[0] === element" in source
    assert "currentEmptyComposerEvidence(element)" in source

    # Live evidence included a localized aria-label, but compatibility must not
    # depend on account language or visible copy.
    assert "Сообщение ChatGPT" not in source
    assert "Message ChatGPT" not in source


def test_empty_composer_repair_does_not_remove_existing_fail_closed_submit_evidence() -> (
    None
):
    source = COMPAT.read_text(encoding="utf-8")

    assert "structuralGenericEvidence" in source
    assert "scopedSubmitControls.length > 0" in source
    assert "genericOnly && !structuralGenericEvidence(element)" in source
    assert "if (semantic.length > 1) return null;" in source
    assert "if (candidates.length !== 1) return null;" in source
