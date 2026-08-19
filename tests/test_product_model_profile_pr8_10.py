from __future__ import annotations

from pathlib import Path

import pytest

from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)
from chatgpt_web_adapter.product_model_profile_pr8_10 import (
    PRODUCT_MODE_TO_SLIDER_INDEX,
    PROFILE_TO_PRODUCT_MODE,
    ProductModelProfileProvider,
    _validate_selection,
    normalize_model_profile,
    product_mode_for_profile,
)

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_semantic_profiles_map_only_to_proven_slider_states() -> None:
    assert PROFILE_TO_PRODUCT_MODE == {
        "FAST": "INSTANT",
        "BALANCED": "MEDIUM",
        "DEEP": "HIGH",
    }
    assert PRODUCT_MODE_TO_SLIDER_INDEX == {"INSTANT": 0, "MEDIUM": 1, "HIGH": 2}
    assert product_mode_for_profile("fast") == "INSTANT"
    assert product_mode_for_profile("balanced") == "MEDIUM"
    assert product_mode_for_profile("deep") == "HIGH"


def test_max_remains_explicitly_unmapped() -> None:
    with pytest.raises(ValueError, match="MAX model profile is not mapped"):
        normalize_model_profile("max")


def test_provider_injects_required_mode_only_for_leased_product_turn(monkeypatch) -> None:
    captured = []

    def fake_rpc(self, payload, *, timeout, on_event=None):
        captured.append(dict(payload))
        return {"ok": True, **payload}

    monkeypatch.setattr(BrowserAuthorityCharacterizationProvider, "_rpc", fake_rpc)
    provider = ProductModelProfileProvider()

    with provider.require_profile("balanced"):
        provider._rpc(
            {
                "type": "turn",
                "request_id": "r1",
                "text": "hello",
                "browserAuthorityLeaseId": "lease-1",
            },
            timeout=1.0,
        )
        provider._rpc({"type": "ping", "request_id": "r2"}, timeout=1.0)

    assert captured[0]["requiredModelMode"] == "MEDIUM"
    assert "requiredModelMode" not in captured[1]


def test_nested_profile_requirements_fail_closed() -> None:
    provider = ProductModelProfileProvider()
    with provider.require_profile("fast"):
        with pytest.raises(RuntimeError, match="nested model-profile requirements"):
            with provider.require_profile("deep"):
                pass


def test_selection_validation_requires_exact_prewrite_proof() -> None:
    good = {
        "browserAuthorityLeaseId": "lease-1",
        "requestedModelMode": "HIGH",
        "requestedSliderIndex": 2,
        "selectionComplete": True,
        "selectedModeAfterProven": True,
        "selectedModeAfter": "HIGH",
        "conversationWriteBeforeSelection": False,
    }
    _validate_selection("DEEP", "lease-1", good)

    bad = dict(good, conversationWriteBeforeSelection=True)
    with pytest.raises(RuntimeError, match="WRITE_BEFORE_SELECTION"):
        _validate_selection("DEEP", "lease-1", bad)


def test_extension_uses_semantic_keyboard_slider_selection_and_no_option_guessing() -> None:
    source = (EXTENSION / "service_worker_model_profile_selection_pr8_10.js").read_text(
        encoding="utf-8"
    )
    assert 'INSTANT: 0, MEDIUM: 1, HIGH: 2' in source
    assert '_pr88InstantEffortDispatchHome(debuggee)' in source
    assert '"ArrowRight"' in source
    assert 'selectedModeAfterProven' in source
    assert 'conversationWriteBeforeSelection' in source
    assert "Fetch.enable" not in source
    assert "Network.getResponseBody" not in source


def test_model_profile_overlay_loads_after_pr8_8_selector_before_pr8_9_streaming() -> None:
    source = (EXTENSION / "service_worker_observability.js").read_text(encoding="utf-8")
    pr88 = 'importScripts("service_worker_instant_effort_slider_support_pr8_8.js");'
    pr810 = 'importScripts("service_worker_model_profile_selection_pr8_10.js");'
    pr89 = 'importScripts("service_worker_safe_browser_response_stream_pr8_9.js");'
    assert pr88 in source and pr810 in source and pr89 in source
    assert source.index(pr88) < source.index(pr810) < source.index(pr89)
