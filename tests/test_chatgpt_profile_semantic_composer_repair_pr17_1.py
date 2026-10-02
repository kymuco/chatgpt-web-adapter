from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

TARGETS = (
    EXT / "service_worker_instant_mode_pr8_8.js",
    EXT / "service_worker_instant_selection_repair_pr8_8.js",
    EXT / "service_worker_instant_effort_selection.js",
)

SEMANTIC_COMPOSER = (
    '[contenteditable="true"][role="textbox"][aria-multiline="true"]'
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_1_profile_paths_accept_current_semantic_composer_shape() -> None:
    for path in TARGETS:
        source = _source(path)

        assert "#prompt-textarea" in source
        assert '[contenteditable="true"][data-lexical-editor="true"]' in source
        assert "textarea[placeholder]" in source

        assert SEMANTIC_COMPOSER in source
        assert "candidate.closest('main')" in source
        assert "candidate.closest('form')" in source
        assert "semanticCandidates.length === 1" in source or (
            "semanticCandidates.length===1" in source
        )


def test_pr17_1_profile_semantic_fallback_stays_fail_closed() -> None:
    for path in TARGETS:
        source = _source(path)

        assert '[role="textbox"]' not in source
        assert "querySelectorAll('[contenteditable="true"]')" not in source
        assert "semanticCandidates.length" in source


def test_pr17_1_profile_repair_preserves_composer_missing_failure() -> None:
    for path in TARGETS:
        source = _source(path)

        assert "composer_missing" in source
