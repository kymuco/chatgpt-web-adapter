from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pr17_2_fresh_background_large_prompt_smoke.py"


def _source() -> str:
    return TOOL.read_text(encoding="utf-8")


def test_pr17_2_large_prompt_smoke_is_one_write_and_substantial() -> None:
    source = _source()

    assert 'PROFILE = "DEEP"' in source
    assert "MIN_PROMPT_CHARS = 24_000" in source
    assert '"product_write_budget": 1' in source
    assert '"automatic_write_retry": False' in source
    assert "--acknowledge-live-write" in source


def test_pr17_2_large_prompt_smoke_requires_fresh_background_commit() -> None:
    source = _source()

    assert 'observation.get("runtime_tab_preexisting") is not False' in source
    assert 'observation.get("runtime_tab_created_for_turn") is not True' in source
    assert 'observation.get("write_event_observed") is not True' in source
    assert 'observation.get("tab_activated_during_turn") is not False' in source
    assert 'observation.get("foreground_activation_observed") is not False' in source
    assert 'observation.get("tab_active_after_write") is not False' in source


def test_pr17_2_large_prompt_smoke_pins_r12_and_canonical_completion() -> None:
    source = _source()

    assert 'EXPECTED_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R12"' in source
    assert "runtime.send_text_observed(" in source
    assert "provider.model_profile_selection_for_lease(lease_id)" in source
    assert '"large_prompt_insert_and_commit_proven": True' in source
    assert '"canonical_completion_proven": True' in source
