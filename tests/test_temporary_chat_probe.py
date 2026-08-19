from __future__ import annotations

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_probe import probe_temporary_chat_mode


class _FakeProvider:
    connect_timeout = 0.5

    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def _rpc(self, payload, *, timeout):
        self.request = dict(payload)
        self.timeout = timeout
        response = dict(self.response)
        response.setdefault("protocol", 1)
        response.setdefault("type", "turn_result")
        response.setdefault("request_id", payload["request_id"])
        return response


def _success_response(**overrides):
    payload = {
        "ok": True,
        "probeContext": "isolated_new_chat",
        "controlFound": True,
        "candidateCount": 1,
        "selectedBefore": False,
        "selectedAfter": True,
        "modeSelectionProven": True,
        "selectionAction": "cdp_control_click",
        "reason": "TEMPORARY_CHAT_SELECTION_PROVEN",
        "matchSignals": ["aria_label"],
        "selectionProofSignals": ["ax:pressed:true"],
        "axBefore": {
            "candidateCount": 1,
            "actionableCandidateCount": 1,
            "roles": ["button"],
            "stateSignals": ["pressed:false"],
            "selectionState": False,
            "selectionProofSignals": [],
        },
        "axAfter": {
            "candidateCount": 1,
            "actionableCandidateCount": 1,
            "roles": ["button"],
            "stateSignals": ["pressed:true"],
            "selectionState": True,
            "selectionProofSignals": ["ax:pressed:true"],
        },
        "conversationWriteObserved": False,
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "probeTabClosed": True,
        "elapsedMs": 321,
    }
    payload.update(overrides)
    return payload


def test_probe_uses_internal_no_write_turn_contract_and_parses_safe_evidence() -> None:
    provider = _FakeProvider(_success_response())

    result = probe_temporary_chat_mode(provider=provider, timeout=12)

    assert provider.request["type"] == "turn"
    assert provider.request["probeTemporaryMode"] is True
    assert provider.request["conversationId"] is None
    assert provider.request["text"] is None
    assert provider.request["canonicalCompleted"] is False
    assert provider.request["canonicalCompletedAtMs"] is None
    assert provider.request["timeoutMs"] == 12_000
    assert provider.timeout == pytest.approx(12.5)

    assert result.probe_context == "isolated_new_chat"
    assert result.control_found is True
    assert result.candidate_count == 1
    assert result.selected_before is False
    assert result.selected_after is True
    assert result.mode_selection_proven is True
    assert result.match_signals == ("aria_label",)
    assert result.selection_proof_signals == ("ax:pressed:true",)
    assert result.ax_before.actionable_candidate_count == 1
    assert result.ax_before.roles == ("button",)
    assert result.ax_before.selection_state is False
    assert result.ax_after.state_signals == ("pressed:true",)
    assert result.ax_after.selection_state is True
    assert result.ax_after.selection_proof_signals == ("ax:pressed:true",)
    assert result.conversation_write_observed is False
    assert result.probe_tab_closed is True


def test_probe_allows_safe_negative_characterization_without_claiming_support() -> None:
    provider = _FakeProvider(
        _success_response(
            selectedAfter=None,
            modeSelectionProven=False,
            reason="TEMPORARY_CHAT_SELECTION_NOT_PROVEN",
            selectionProofSignals=[],
            axAfter={
                "candidateCount": 1,
                "actionableCandidateCount": 1,
                "roles": ["button"],
                "stateSignals": ["expanded:true", "haspopup:menu"],
                "selectionState": None,
                "selectionProofSignals": [],
            },
        )
    )

    result = probe_temporary_chat_mode(provider=provider, timeout=5)

    assert result.mode_selection_proven is False
    assert result.selected_after is None
    assert result.reason == "TEMPORARY_CHAT_SELECTION_NOT_PROVEN"
    assert result.ax_after.selection_state is None
    assert result.ax_after.state_signals == ("expanded:true", "haspopup:menu")


def test_probe_sanitizes_missing_or_malformed_ax_snapshot() -> None:
    provider = _FakeProvider(
        _success_response(
            axBefore=None,
            axAfter={
                "candidateCount": -1,
                "actionableCandidateCount": True,
                "roles": ["button", 123, ""],
                "stateSignals": "not-a-list",
                "selectionState": "true",
                "selectionProofSignals": [None, "ax:selected:true"],
            },
        )
    )

    result = probe_temporary_chat_mode(provider=provider, timeout=5)

    assert result.ax_before.candidate_count == 0
    assert result.ax_before.roles == ()
    assert result.ax_after.candidate_count == 0
    assert result.ax_after.actionable_candidate_count == 0
    assert result.ax_after.roles == ("button",)
    assert result.ax_after.state_signals == ()
    assert result.ax_after.selection_state is None
    assert result.ax_after.selection_proof_signals == ("ax:selected:true",)


def test_probe_rejects_any_observed_conversation_write() -> None:
    provider = _FakeProvider(
        _success_response(conversationWriteObserved=True)
    )

    with pytest.raises(RequestError, match="UNEXPECTED_CONVERSATION_WRITE"):
        probe_temporary_chat_mode(provider=provider, timeout=5)


def test_probe_fails_closed_on_bridge_error() -> None:
    provider = _FakeProvider({"ok": False, "error": "TEMPORARY_CHAT_CONTROL_NOT_FOUND"})

    with pytest.raises(RequestError, match="TEMPORARY_CHAT_CONTROL_NOT_FOUND"):
        probe_temporary_chat_mode(provider=provider, timeout=5)


def test_probe_requires_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        probe_temporary_chat_mode(provider=_FakeProvider(_success_response()), timeout=0)
