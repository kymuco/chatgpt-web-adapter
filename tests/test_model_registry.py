from __future__ import annotations

import pytest

from chatgpt_web_adapter.model_detection import detect_model_from_conversation_payload
from chatgpt_web_adapter.model_registry import (
    DEFAULT_MODEL,
    DEFAULT_THINKING_MODEL,
    MODEL_CAPABILITIES,
    get_model_capability,
    normalize_reasoning_effort,
    resolve_model,
)


def test_default_models_match_current_policy() -> None:
    assert DEFAULT_MODEL == "gpt-5-3-mini"
    assert DEFAULT_THINKING_MODEL == "gpt-5-6-thinking"


def test_gpt56_capability_records_live_ui_contract() -> None:
    capability = MODEL_CAPABILITIES["gpt-5-6-thinking"]

    assert capability.family == "gpt-5.6"
    assert capability.ui_name == "GPT-5.6 Sol"
    assert capability.reasoning_modes == {
        "medium": "standard",
        "high": "extended",
    }
    assert capability.evidence == "live-attach-2026-08-07"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("off", None),
        ("none", None),
        ("-", None),
        ("instant", None),
        ("medium", "standard"),
        ("standard", "standard"),
        ("high", "extended"),
        ("extended", "extended"),
        (" HIGH ", "extended"),
    ],
)
def test_reasoning_aliases_are_normalized(value: str | None, expected: str | None) -> None:
    assert normalize_reasoning_effort(value) == expected


def test_unobserved_extra_high_is_not_guessed() -> None:
    with pytest.raises(ValueError, match="reasoning_effort must be one of"):
        normalize_reasoning_effort("extra-high")


@pytest.mark.parametrize("mode", ["medium", "high", "standard", "extended"])
def test_reasoning_modes_use_live_gpt56_thinking_default(mode: str) -> None:
    assert resolve_model(None, mode) == "gpt-5-6-thinking"


def test_no_reasoning_uses_instant_default() -> None:
    assert resolve_model(None, None) == "gpt-5-3-mini"
    assert resolve_model(None, "instant") == "gpt-5-3-mini"


@pytest.mark.parametrize("alias", ["thinking", "gpt-5.6", "GPT-5.6"])
def test_gpt56_convenience_aliases_resolve_to_observed_slug(alias: str) -> None:
    assert resolve_model(alias, None) == "gpt-5-6-thinking"


def test_legacy_explicit_thinking_slug_remains_pass_through() -> None:
    assert resolve_model("gpt-5-5-thinking", "high") == "gpt-5-5-thinking"


def test_unknown_future_explicit_slug_remains_pass_through() -> None:
    assert resolve_model("gpt-9-unknown-web", "high") == "gpt-9-unknown-web"


def test_empty_explicit_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="model must not be empty"):
        resolve_model("   ", None)


def test_capability_lookup_accepts_aliases_without_whitelisting_unknown_models() -> None:
    assert get_model_capability("thinking") is MODEL_CAPABILITIES["gpt-5-6-thinking"]
    assert get_model_capability("gpt-9-unknown-web") is None


def test_model_detector_is_independent_of_registry_membership() -> None:
    payload = {
        "current_node": "assistant-current",
        "mapping": {
            "assistant-current": {
                "message": {
                    "id": "assistant-current",
                    "author": {"role": "assistant"},
                    "metadata": {"model_slug": "gpt-9-unknown-web"},
                }
            }
        },
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-9-unknown-web"
