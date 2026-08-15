from __future__ import annotations

import pytest

import chatgpt_web_adapter.temporary_chat_turn_probe as probe_module
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_turn_probe import probe_temporary_chat_turn


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


class _FakeStatus:
    status = "completed"
    finish_reason = None


class _FakeMessage:
    def __init__(self, role, model=None):
        self.role = role
        self.model = model


class _FakeAttached:
    current_node = "node-1"
    detected_model = "model-x"
    title = "smoke"


class _FakeRuntime:
    def get_status(self, conversation):
        assert conversation == "conversation-1"
        return _FakeStatus()

    def get_messages(self, conversation):
        assert conversation == "conversation-1"
        return [
            _FakeMessage("user"),
            _FakeMessage("assistant", "model-x"),
        ]

    def attach_conversation(self, conversation):
        assert conversation == "conversation-1"
        return _FakeAttached()


def _success_response(**overrides):
    payload = {
        "ok": True,
        "probeContext": "isolated_new_chat_temporary_turn",
        "activationAction": "click_unique_control_without_selected_state_proof",
        "selectionProvenBeforeWrite": False,
        "selectedBefore": None,
        "selectedAfterActivation": None,
        "selectedAfterTurn": None,
        "preWriteProofSignals": [],
        "postTurnProofSignals": [],
        "uiModeMarkerObservedBeforeWrite": False,
        "uiModeMarkerObservedAfterTurn": True,
        "preWriteUiModeSignals": [],
        "postTurnUiModeSignals": ["semantic:document-title-temporary"],
        "conversationWriteCount": 1,
        "conversationId": "conversation-1",
        "turnExchangeId": "turn-1",
        "responseStatus": 200,
        "responseMimeType": "text/event-stream",
        "finalUrlKind": "conversation",
        "urlConversationIdPresent": True,
        "submitStrategy": "send_button_click",
        "submitAckMs": 123,
        "completionReadyWaitMs": 456,
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "probeTabClosed": True,
        "elapsedMs": 1200,
    }
    payload.update(overrides)
    return payload


def test_turn_probe_requires_explicit_durable_risk_acknowledgement() -> None:
    with pytest.raises(ValueError, match="acknowledge_durable_risk"):
        probe_temporary_chat_turn(
            provider=_FakeProvider(_success_response()),
            acknowledge_durable_risk=False,
        )


def test_turn_probe_serializes_explicit_diagnostic_write_and_observes_canonical_after_close(
    monkeypatch,
) -> None:
    provider = _FakeProvider(_success_response())
    monkeypatch.setattr(
        probe_module,
        "assemble_product_runtime",
        lambda **kwargs: _FakeRuntime(),
    )

    result = probe_temporary_chat_turn(
        "Reply exactly: smoke",
        provider=provider,
        acknowledge_durable_risk=True,
        timeout=12,
    )

    assert provider.request["type"] == "turn"
    assert provider.request["conversationId"] is None
    assert provider.request["probeTemporaryMode"] is False
    assert provider.request["characterizeTemporaryTurn"] is True
    assert provider.request["acknowledgeDurableRisk"] is True
    assert provider.request["text"] == "Reply exactly: smoke"
    assert provider.request["timeoutMs"] == 12_000
    assert provider.timeout == pytest.approx(12.5)

    assert result.probe_context == "isolated_new_chat_temporary_turn"
    assert result.activation_action == "click_unique_control_without_selected_state_proof"
    assert result.selection_proven_before_write is False
    assert result.selected_after_turn is None
    assert result.post_turn_proof_signals == ()
    assert result.ui_mode_marker_observed_before_write is False
    assert result.ui_mode_marker_observed_after_turn is True
    assert result.post_turn_ui_mode_signals == ("semantic:document-title-temporary",)
    assert result.conversation_write_count == 1
    assert result.conversation_id == "conversation-1"
    assert result.response_status == 200
    assert result.probe_tab_closed is True

    canonical = result.canonical_after_tab_close
    assert canonical.attempted is True
    assert canonical.status_ok is True
    assert canonical.status == "completed"
    assert canonical.messages_ok is True
    assert canonical.message_count == 2
    assert canonical.user_message_count == 1
    assert canonical.assistant_message_count == 1
    assert canonical.observed_models == ("model-x",)
    assert canonical.attach_ok is True
    assert canonical.attach_current_node_present is True
    assert canonical.attach_detected_model == "model-x"
    assert canonical.attach_title_present is True
    assert canonical.error_types == ()


def test_turn_probe_does_not_fabricate_canonical_identity_when_transport_returns_none() -> None:
    provider = _FakeProvider(
        _success_response(
            conversationId=None,
            turnExchangeId=None,
            finalUrlKind="new_chat_root",
            urlConversationIdPresent=False,
        )
    )

    result = probe_temporary_chat_turn(
        provider=provider,
        acknowledge_durable_risk=True,
        timeout=5,
    )

    assert result.conversation_id is None
    assert result.canonical_after_tab_close.attempted is False
    assert result.canonical_after_tab_close.status_ok is None
    assert result.canonical_after_tab_close.messages_ok is None
    assert result.canonical_after_tab_close.attach_ok is None


def test_turn_probe_preserves_canonical_failure_classes_without_raw_payload(monkeypatch) -> None:
    class _FailingRuntime:
        def get_status(self, conversation):
            raise RequestError("status payload detail", request_stage="status")

        def get_messages(self, conversation):
            raise RuntimeError("message payload detail")

        def attach_conversation(self, conversation):
            raise ValueError("attach payload detail")

    monkeypatch.setattr(
        probe_module,
        "assemble_product_runtime",
        lambda **kwargs: _FailingRuntime(),
    )

    result = probe_temporary_chat_turn(
        provider=_FakeProvider(_success_response()),
        acknowledge_durable_risk=True,
        timeout=5,
    )

    canonical = result.canonical_after_tab_close
    assert canonical.status_ok is False
    assert canonical.messages_ok is False
    assert canonical.attach_ok is False
    assert canonical.error_types == (
        "status:RequestError",
        "messages:RuntimeError",
        "attach:ValueError",
    )


def test_turn_probe_fails_closed_on_bridge_error() -> None:
    provider = _FakeProvider(
        {"ok": False, "error": "TEMPORARY_CHAT_TURN_PROBE_CONTROL_NOT_FOUND"}
    )

    with pytest.raises(RequestError, match="CONTROL_NOT_FOUND"):
        probe_temporary_chat_turn(
            provider=provider,
            acknowledge_durable_risk=True,
            timeout=5,
        )
