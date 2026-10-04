from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pr17_2_background_product_model_profile_e2e.py"


def _source() -> str:
    return TOOL.read_text(encoding="utf-8")


def test_pr17_2_e2e_uses_public_production_runtime() -> None:
    source = _source()

    assert "assemble_product_runtime" in source
    assert "ProductModelProfileProvider" in source
    assert 'SEQUENCE: tuple[str, ...] = ("FAST", "DEEP", "BALANCED")' in source
    assert "runtime.send_text_observed(" in source
    assert "provider.model_profile_selection_for_lease(" in source


def test_pr17_2_e2e_requires_real_background_observation() -> None:
    source = _source()

    assert 'observation.get("tab_was_active_at_write_start") is not False' in source
    assert 'observation.get("tab_activated_during_turn") is not False' in source
    assert 'observation.get("foreground_activation_observed") is not False' in source
    assert 'observation.get("tab_active_after_write") is not False' in source


def test_pr17_2_e2e_requires_shipping_background_selection_record() -> None:
    source = _source()

    assert 'selection.get("conversationWriteBeforeSelection") is not False' in source
    assert 'selection.get("transientForegroundActivated") is not False' in source
    assert 'selection.get("transientForegroundProven") is not False' in source
    assert 'selection.get("foregroundRestoreAttempted") is not False' in source
    assert 'selection.get("backgroundSelectionAttempted") is not True' in source
    assert 'selection.get("backgroundSelectionProven") is not True' in source
    assert '"REASONING_EFFORT_SLIDER_HOME_PLUS_RIGHT"' in source


def test_pr17_2_e2e_forces_mutation_after_first_turn() -> None:
    source = _source()

    assert "require_mutation=index > 0" in source
    assert '"background_mutations_required": ["DEEP", "BALANCED"]' in source
    assert '"background_mutations_proven": True' in source
    assert '"strict_prewrite_selection_proven": True' in source


def test_pr17_2_e2e_has_bounded_live_write_contract() -> None:
    source = _source()

    assert '"product_write_budget": len(SEQUENCE)' in source
    assert '"automatic_write_retry": False' in source
    assert "--acknowledge-live-writes" in source
    assert "this gate performs exactly three ChatGPT product writes" in source


def test_pr17_2_e2e_chains_one_new_conversation() -> None:
    source = _source()

    assert "conversation: str | None = None" in source
    assert (
        "response_conversation = execution.response.conversation.conversation_id"
        in source
    )
    assert "conversation = response_conversation" in source
    assert "response_conversation != conversation" in source
    assert '"canonical_completion_proven": True' in source
