from __future__ import annotations

from chatgpt_web_adapter.browser_native_client import _status_finalizes_message
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_write_runtime import BrowserOwnedProductWriteRuntime
from chatgpt_web_adapter.status import _status_from_payload


def _message(
    *,
    role: str = "assistant",
    recipient: str = "all",
    message_status: str | None = None,
    end_turn: bool | None = None,
    metadata: dict | None = None,
) -> dict:
    message = {
        "id": "assistant-final",
        "author": {"role": role},
        "recipient": recipient,
        "content": {"content_type": "text", "parts": ["SDK_RUNTIME_OBS_CREATE_OK"]},
        "metadata": metadata or {},
    }
    if message_status is not None:
        message["status"] = message_status
    if end_turn is not None:
        message["end_turn"] = end_turn
    return message


def _payload(message: dict, *, async_status: str | None = None) -> dict:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "assistant-final",
        "mapping": {
            "assistant-final": {
                "id": "assistant-final",
                "parent": "user-1",
                "children": [],
                "message": message,
            }
        },
    }
    if async_status is not None:
        payload["async_status"] = async_status
    return payload


def test_observed_finished_successfully_end_turn_payload_is_completed() -> None:
    status = _status_from_payload(
        _payload(_message(message_status="finished_successfully", end_turn=True))
    )

    assert status.status == "completed"
    assert status.message_id == "assistant-final"
    assert status.finish_reason is None
    assert status.async_status is None
    assert status.metadata_preview["message_status"] == "finished_successfully"
    assert status.metadata_preview["end_turn"] is True


def test_finished_successfully_alone_is_explicit_message_completion() -> None:
    status = _status_from_payload(
        _payload(_message(message_status="finished_successfully"))
    )
    assert status.status == "completed"


def test_end_turn_true_alone_is_explicit_message_completion() -> None:
    status = _status_from_payload(_payload(_message(end_turn=True)))
    assert status.status == "completed"


def test_active_async_status_overrides_message_level_completion() -> None:
    status = _status_from_payload(
        _payload(
            _message(message_status="finished_successfully", end_turn=True),
            async_status="running",
        )
    )
    assert status.status == "running"


def test_active_message_status_overrides_end_turn_defensively() -> None:
    status = _status_from_payload(
        _payload(_message(message_status="running", end_turn=True))
    )
    assert status.status == "running"


def test_tool_recipient_precedence_is_preserved() -> None:
    status = _status_from_payload(
        _payload(
            _message(
                recipient="python",
                message_status="finished_successfully",
                end_turn=True,
            )
        )
    )
    assert status.status == "tool_calling"


def test_pending_approval_precedence_is_preserved() -> None:
    status = _status_from_payload(
        _payload(
            _message(
                recipient="python",
                message_status="finished_successfully",
                end_turn=True,
                metadata={"pending_approval": True},
            )
        )
    )
    assert status.status == "awaiting_tool_approval"


def test_assistant_without_explicit_finality_remains_running() -> None:
    status = _status_from_payload(_payload(_message()))
    assert status.status == "running"


class _Provider:
    def status(self) -> BrowserNativeBridgeStatus:
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=17,
        )

    def send_text(self, *args, **kwargs):
        raise AssertionError("health-only test must not send a turn")


class _Client:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def get_status(self, conversation):
        return _status_from_payload(self.payload)


def test_browser_owned_preflight_accepts_observed_completed_payload() -> None:
    runtime = BrowserOwnedProductWriteRuntime(
        _Client(
            _payload(
                _message(message_status="finished_successfully", end_turn=True)
            )
        ),
        provider=_Provider(),
    )

    health = runtime.health("conversation-1")
    assert health.ready is True
    assert health.canonical_status == "completed"
    assert health.runtime_tab_preexisting is True


def test_pr824a1_message_id_finality_accepts_recovered_status() -> None:
    status = _status_from_payload(
        _payload(_message(message_status="finished_successfully", end_turn=True))
    )
    assert _status_finalizes_message(status, "assistant-final") is True
    assert _status_finalizes_message(status, "different-assistant") is False
