from pathlib import Path

import pytest

from chatgpt_web_adapter.browser_authority_instant_working_path_validation_pr8_8 import (
    UNIFIED_GPT56_ROUTE_STATUS,
    validate_instant_route,
)

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)


def _live_unified_fixture() -> dict:
    return {
        "requested_model_mode": "INSTANT",
        "require_no_reasoning_route": True,
        "selected_mode_before_write_proven": True,
        "selected_mode_before_write": "INSTANT",
        "conversation_request_observed": True,
        "network_route_status": UNIFIED_GPT56_ROUTE_STATUS,
        "reasoning_route_observed": False,
        "request_evidence": {
            "model_identifiers": ["gpt-5-6"],
            "model_modes": [],
            "reasoning_states": [],
            "model_hint_keys": ["model"],
            "reasoning_hint_keys": [],
        },
        "response_evidence": {
            "model_identifiers": [
                "gpt-5-6",
                "gpt-5-6-auto-thinking",
                "gpt-5-6-thinking",
            ],
            "model_modes": ["REASONING_OTHER"],
            "reasoning_states": [],
            "model_hint_keys": ["model_slug"],
            "reasoning_hint_keys": [],
        },
    }


def test_model_slug_thinking_alias_is_not_explicit_reasoning_route():
    validate_instant_route(_live_unified_fixture())


def test_explicit_reasoning_state_still_fails_closed():
    record = _live_unified_fixture()
    record["reasoning_route_observed"] = True
    record["network_route_status"] = "REASONING_ROUTE_OBSERVED"
    record["response_evidence"]["reasoning_states"] = ["ON"]
    record["response_evidence"]["reasoning_hint_keys"] = ["reasoning_effort"]
    with pytest.raises(RuntimeError, match="ROUTE_CONTRACT_FAILED"):
        validate_instant_route(record)


def test_unified_status_requires_gpt56_identity_and_no_explicit_reasoning_metadata():
    missing_family = _live_unified_fixture()
    missing_family["request_evidence"]["model_identifiers"] = ["other-model"]
    missing_family["response_evidence"]["model_identifiers"] = ["other-model-thinking"]
    with pytest.raises(RuntimeError, match="UNIFIED_GPT56_ROUTE_CONTRACT_FAILED"):
        validate_instant_route(missing_family)

    explicit_reasoning = _live_unified_fixture()
    explicit_reasoning["response_evidence"]["reasoning_hint_keys"] = ["thinking_mode"]
    with pytest.raises(RuntimeError, match="UNIFIED_GPT56_ROUTE_CONTRACT_FAILED"):
        validate_instant_route(explicit_reasoning)


def test_extension_derivation_separates_model_identity_from_reasoning_state():
    worker = (
        ROOT / "service_worker_instant_unified_route_semantics_pr8_8.js"
    ).read_text(encoding="utf-8")
    for token in (
        "UNIFIED_GPT_5_6_ROUTE_WITHOUT_EXPLICIT_REASONING",
        "merged.reasoningHintKeys.size > 0",
        'reasoning.has("ON")',
        "modelSlugReasoningAliasObserved",
        "A model slug is model identity evidence, not reasoning-state evidence.",
    ):
        assert token in worker

    for forbidden in (
        "Input.insertText",
        "Input.dispatchMouseEvent",
        "chrome.tabs.remove",
        "target.click()",
        "Network.setRequestInterception",
    ):
        assert forbidden not in worker


def test_observability_loads_unified_semantics_immediately_after_instant_mode():
    worker = (ROOT / "service_worker_observability.js").read_text(encoding="utf-8")
    instant = 'importScripts("service_worker_instant_mode_pr8_8.js");'
    unified = (
        'importScripts("service_worker_instant_unified_route_semantics_pr8_8.js");'
    )
    assert instant in worker
    assert unified in worker
    assert worker.index(instant) < worker.index(unified)
