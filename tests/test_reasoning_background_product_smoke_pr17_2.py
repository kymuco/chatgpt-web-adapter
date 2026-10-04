from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pr17_2_fresh_background_product_smoke.py"


def _source() -> str:
    return TOOL.read_text(encoding="utf-8")


def test_pr17_2_fresh_product_smoke_is_exactly_one_write() -> None:
    source = _source()

    assert '"product_write_budget": 1' in source
    assert '"automatic_write_retry": False' in source
    assert "--acknowledge-live-write" in source
    assert "this gate performs exactly one ChatGPT product write" in source


def test_pr17_2_fresh_product_smoke_requires_fresh_background_tab() -> None:
    source = _source()

    assert 'observation.get("runtime_tab_preexisting") is not False' in source
    assert 'observation.get("runtime_tab_created_for_turn") is not True' in source
    assert 'observation.get("tab_was_active_at_write_start") is not False' in source
    assert 'observation.get("tab_activated_during_turn") is not False' in source
    assert 'observation.get("foreground_activation_observed") is not False' in source
    assert 'observation.get("tab_active_after_write") is not False' in source


def test_pr17_2_fresh_product_smoke_requires_r12_and_canonical_completion() -> None:
    source = _source()

    assert 'EXPECTED_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R12"' in source
    assert "provider.model_profile_support()" in source
    assert "runtime.send_text_observed(" in source
    assert "provider.model_profile_selection_for_lease(lease_id)" in source
    assert '"background_submit_proven": True' in source
    assert '"canonical_completion_proven": True' in source
