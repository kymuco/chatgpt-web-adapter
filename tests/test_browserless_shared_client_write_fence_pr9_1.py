from __future__ import annotations

from threading import Event, Thread
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import BrowserlessRequestTransport
from chatgpt_web_adapter.sentinel_bundle import prepared_send_active
from chatgpt_web_adapter.types import ChatConversation, ChatMessage, ChatResponse


class _RaceFenceClient:
    def __init__(self) -> None:
        self.timeout = 60.0
        self.base_headers = {"user-agent": "race-fence-test"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.preflight_started = Event()
        self.release_preflight = Event()
        self.ordinary_send_entered = Event()
        self.canonical_readback_finished = Event()
        self.browserless_send_calls = 0
        self.ordinary_send_calls = 0
        self.ordinary_entered_after_canonical_readback = False
        self.ordinary_parent_message_id: str | None = None

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **dict(extra or {})}

    def _get_ready_requirements(self):
        raise AssertionError("browserless prepared binding must supply requirements")

    def _json_request(self, method, url, payload, headers):
        if url.endswith("/chat-requirements/prepare"):
            self.preflight_started.set()
            assert self.release_preflight.wait(2.0)
            return 200, {
                "persona": "chatgpt-test",
                "prepare_token": "prepare-token",
                "proofofwork": {"required": False},
                "so": {"required": False},
                "turnstile": {"required": False},
            }
        if url.endswith("/chat-requirements/finalize"):
            return 200, {
                "persona": "chatgpt-test",
                "token": "requirements-token",
                "expire_after": 60,
                "expire_at": 9999999999,
            }
        raise AssertionError(f"unexpected URL: {url}")

    @staticmethod
    def _parent_id(conversation) -> str | None:
        if isinstance(conversation, ChatConversation):
            return conversation.parent_message_id or conversation.message_id
        if isinstance(conversation, dict):
            return conversation.get("parent_message_id") or conversation.get("message_id")
        return None

    def send(self, prompt, *, conversation=None, on_token=None, on_event=None, **kwargs):
        if not prepared_send_active():
            self.ordinary_send_calls += 1
            self.ordinary_parent_message_id = self._parent_id(conversation)
            self.ordinary_entered_after_canonical_readback = (
                self.canonical_readback_finished.is_set()
            )
            self.ordinary_send_entered.set()
            return ChatResponse(
                text="ordinary answer",
                conversation=ChatConversation(
                    conversation_id="conversation-1",
                    message_id="ordinary-assistant",
                    parent_message_id="ordinary-assistant",
                ),
            )

        self.browserless_send_calls += 1
        requirements, proof = self._get_ready_requirements()
        assert proof is None
        assert requirements["token"] == "requirements-token"
        self._build_headers(
            {
                "x-openai-target-path": "/backend-api/f/conversation/prepare",
                "x-openai-target-route": "/backend-api/f/conversation/prepare",
            }
        )
        self._build_headers(
            {
                "x-openai-target-path": "/backend-api/f/conversation",
                "x-openai-target-route": "/backend-api/f/conversation",
                "openai-sentinel-chat-requirements-token": requirements["token"],
                "x-conduit-token": "current-conduit",
            }
        )
        return ChatResponse(
            text="browserless stream",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="browserless-assistant",
                parent_message_id="browserless-assistant",
            ),
        )

    def attach_conversation(self, conversation):
        parent = (
            "browserless-assistant"
            if self.canonical_readback_finished.is_set()
            else "attached-parent"
        )
        return SimpleNamespace(
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id=parent,
                parent_message_id=parent,
            )
        )

    def get_status(self, conversation):
        return SimpleNamespace(
            status="completed",
            finish_reason="stop",
            message_id="browserless-assistant",
        )

    def get_messages(self, conversation, **kwargs):
        self.canonical_readback_finished.set()
        return [
            ChatMessage(role="user", text="browserless prompt", message_id="user-message"),
            ChatMessage(
                role="assistant",
                text="browserless canonical answer",
                message_id="browserless-assistant",
                finish_reason="stop",
            ),
        ]


def _run_browserless_turn(
    client: _RaceFenceClient,
    transport: BrowserlessRequestTransport,
    errors: list[BaseException],
) -> None:
    try:
        response = transport.send_text(
            "browserless prompt",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="stale-caller-parent",
                parent_message_id="stale-caller-parent",
            ),
            timeout=2.0,
            poll_interval=0.01,
        )
        assert response.text == "browserless canonical answer"
    except BaseException as error:  # pragma: no cover - surfaced by callers
        errors.append(error)


def test_same_client_ordinary_send_rebinds_parent_after_browserless_queue() -> None:
    client = _RaceFenceClient()
    transport = BrowserlessRequestTransport(client)
    browserless_errors: list[BaseException] = []
    ordinary_errors: list[BaseException] = []

    def run_ordinary() -> None:
        try:
            client.send(
                "ordinary prompt",
                conversation=ChatConversation(
                    conversation_id="conversation-1",
                    message_id="attached-parent",
                    parent_message_id="attached-parent",
                ),
            )
        except BaseException as error:  # pragma: no cover - surfaced below
            ordinary_errors.append(error)

    browserless_thread = Thread(
        target=_run_browserless_turn,
        args=(client, transport, browserless_errors),
    )
    browserless_thread.start()
    assert client.preflight_started.wait(1.0)

    ordinary_thread = Thread(target=run_ordinary)
    ordinary_thread.start()

    # The ordinary public client.send() is queued while browserless owns
    # attach -> Sentinel -> mutation -> canonical readback.
    assert client.ordinary_send_entered.wait(0.10) is False

    client.release_preflight.set()
    browserless_thread.join(2.0)
    ordinary_thread.join(2.0)

    assert browserless_thread.is_alive() is False
    assert ordinary_thread.is_alive() is False
    assert browserless_errors == []
    assert ordinary_errors == []
    assert client.browserless_send_calls == 1
    assert client.ordinary_send_calls == 1
    assert client.ordinary_entered_after_canonical_readback is True
    # Crucially, delaying the ordinary call does not preserve its queued parent.
    # It canonically reattaches after lock acquisition and continues from the
    # browserless assistant that became current while it was waiting.
    assert client.ordinary_parent_message_id == "browserless-assistant"


def test_replacing_instance_send_keeps_the_same_fence_and_post_queue_refresh() -> None:
    client = _RaceFenceClient()
    transport = BrowserlessRequestTransport(client)
    browserless_errors: list[BaseException] = []
    ordinary_errors: list[BaseException] = []
    replacement_entered = Event()
    replacement_parent: list[str | None] = []

    def replacement_send(prompt, *, conversation=None, **kwargs):
        replacement_parent.append(client._parent_id(conversation))
        replacement_entered.set()
        return ChatResponse(
            text="replacement ordinary answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="replacement-assistant",
                parent_message_id="replacement-assistant",
            ),
        )

    # This is the exact compatible-client replacement pattern from the review.
    # Guarded __setattr__ must automatically reapply the same per-client fence.
    client.send = replacement_send

    def run_replacement() -> None:
        try:
            client.send(
                "replacement ordinary prompt",
                conversation=ChatConversation(
                    conversation_id="conversation-1",
                    message_id="attached-parent",
                    parent_message_id="attached-parent",
                ),
            )
        except BaseException as error:  # pragma: no cover - surfaced below
            ordinary_errors.append(error)

    browserless_thread = Thread(
        target=_run_browserless_turn,
        args=(client, transport, browserless_errors),
    )
    browserless_thread.start()
    assert client.preflight_started.wait(1.0)

    ordinary_thread = Thread(target=run_replacement)
    ordinary_thread.start()
    assert replacement_entered.wait(0.10) is False

    client.release_preflight.set()
    browserless_thread.join(2.0)
    ordinary_thread.join(2.0)

    assert browserless_thread.is_alive() is False
    assert ordinary_thread.is_alive() is False
    assert browserless_errors == []
    assert ordinary_errors == []
    assert replacement_parent == ["browserless-assistant"]


def test_fenced_mutation_entrypoint_cannot_be_deleted_normally() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    with pytest.raises(TypeError, match="cannot delete fenced mutation entrypoint send"):
        del client.send
