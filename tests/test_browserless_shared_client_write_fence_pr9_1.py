from __future__ import annotations

from threading import Barrier, Event, Thread
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import BrowserlessRequestTransport
from chatgpt_web_adapter.exceptions import RequestError
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
        self.raw_payload_calls = 0
        self.raw_payload_parent: str | None = None
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
        if on_token is not None:
            on_token("browserless-token")
        return ChatResponse(
            text="browserless stream",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="browserless-assistant",
                parent_message_id="browserless-assistant",
            ),
        )

    def send_payload(self, payload, **kwargs):
        self.raw_payload_calls += 1
        self.raw_payload_parent = (
            payload.get("parent_message_id") if isinstance(payload, dict) else None
        )
        return {"ok": True}

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


def test_browserless_on_token_same_client_mutation_fails_closed_before_second_write() -> None:
    client = _RaceFenceClient()
    transport = BrowserlessRequestTransport(client)
    client.release_preflight.set()
    nested_errors: list[BaseException] = []

    def on_token(_token: str) -> None:
        try:
            client.send(
                "nested callback prompt",
                conversation=ChatConversation(
                    conversation_id="conversation-1",
                    message_id="attached-parent",
                    parent_message_id="attached-parent",
                ),
            )
        except BaseException as error:
            nested_errors.append(error)

    response = transport.send_text(
        "browserless prompt",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="stale-caller-parent",
            parent_message_id="stale-caller-parent",
        ),
        timeout=2.0,
        poll_interval=0.01,
        on_token=on_token,
    )

    assert response.text == "browserless canonical answer"
    assert len(nested_errors) == 1
    assert isinstance(nested_errors[0], RequestError)
    assert "same-client nested mutation send while browserless_request owns mutation authority" in str(
        nested_errors[0]
    )
    assert client.browserless_send_calls == 1
    assert client.ordinary_send_calls == 0


def test_top_level_raw_payload_still_validates_stale_parent() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    with pytest.raises(
        RequestError,
        match="shared-client mutation fence rejected a stale raw-payload parent",
    ):
        client.send_payload(
            {
                "conversation_id": "conversation-1",
                "parent_message_id": "stale-inner-parent",
                "action": "next",
            }
        )

    assert client.raw_payload_calls == 0


def test_nested_same_client_mutation_fails_closed_before_raw_validation_or_write() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    def replacement_send(prompt, *, conversation=None, **kwargs):
        client.send_payload(
            {
                "conversation_id": "conversation-1",
                "parent_message_id": "attached-parent",
                "action": "next",
            }
        )
        raise AssertionError("nested mutation should have failed before raw mutation")

    client.send = replacement_send

    with pytest.raises(
        RequestError,
        match="same-client nested mutation send_payload while send owns mutation authority",
    ):
        client.send(
            "outer prompt",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="attached-parent",
                parent_message_id="attached-parent",
            ),
        )

    assert client.raw_payload_calls == 0


def test_nested_cross_client_mutation_fails_closed_before_second_lock() -> None:
    outer_client = _RaceFenceClient()
    inner_client = _RaceFenceClient()
    BrowserlessRequestTransport(outer_client)
    BrowserlessRequestTransport(inner_client)
    inner_entered = Event()

    def inner_send(prompt, *, conversation=None, **kwargs):
        inner_entered.set()
        return ChatResponse(
            text="inner answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="inner-assistant",
                parent_message_id="inner-assistant",
            ),
        )

    def outer_send(prompt, *, conversation=None, **kwargs):
        return inner_client.send(
            "inner prompt",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="stale-inner-parent",
                parent_message_id="stale-inner-parent",
            ),
        )

    inner_client.send = inner_send
    outer_client.send = outer_send

    with pytest.raises(
        RequestError,
        match="cross-client nested mutation send while send owns mutation authority",
    ):
        outer_client.send(
            "outer prompt",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="stale-outer-parent",
                parent_message_id="stale-outer-parent",
            ),
        )

    assert inner_entered.is_set() is False


def test_opposite_order_cross_client_nested_mutations_fail_without_deadlock() -> None:
    client_a = _RaceFenceClient()
    client_b = _RaceFenceClient()
    BrowserlessRequestTransport(client_a)
    BrowserlessRequestTransport(client_b)
    both_outer_locks_held = Barrier(2)
    errors: list[BaseException] = []

    def send_a(prompt, *, conversation=None, **kwargs):
        both_outer_locks_held.wait(timeout=1.0)
        return client_b.send(
            "nested-b",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="attached-parent",
                parent_message_id="attached-parent",
            ),
        )

    def send_b(prompt, *, conversation=None, **kwargs):
        both_outer_locks_held.wait(timeout=1.0)
        return client_a.send(
            "nested-a",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="attached-parent",
                parent_message_id="attached-parent",
            ),
        )

    client_a.send = send_a
    client_b.send = send_b

    def run(client: _RaceFenceClient, label: str) -> None:
        try:
            client.send(
                label,
                conversation=ChatConversation(
                    conversation_id="conversation-1",
                    message_id="attached-parent",
                    parent_message_id="attached-parent",
                ),
            )
        except BaseException as error:
            errors.append(error)

    thread_a = Thread(target=run, args=(client_a, "outer-a"))
    thread_b = Thread(target=run, args=(client_b, "outer-b"))
    thread_a.start()
    thread_b.start()
    thread_a.join(2.0)
    thread_b.join(2.0)

    assert thread_a.is_alive() is False
    assert thread_b.is_alive() is False
    assert len(errors) == 2
    assert all(isinstance(error, RequestError) for error in errors)
    assert all("cross-client nested mutation send" in str(error) for error in errors)


def test_direct_chat_conversation_attach_result_is_supported_by_fence() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    def direct_attach(_conversation):
        return ChatConversation(
            conversation_id="conversation-1",
            message_id="direct-parent",
            parent_message_id="direct-parent",
        )

    client.attach_conversation = direct_attach

    client.send(
        "ordinary prompt",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="stale-parent",
            parent_message_id="stale-parent",
        ),
    )
    assert client.ordinary_parent_message_id == "direct-parent"

    result = client.send_payload(
        {
            "conversation_id": "conversation-1",
            "parent_message_id": "direct-parent",
            "action": "next",
        }
    )
    assert result == {"ok": True}
    assert client.raw_payload_calls == 1
    assert client.raw_payload_parent == "direct-parent"


def test_mapping_attach_result_is_supported_by_fence_and_raw_parent_validation() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    def mapping_attach(_conversation):
        return {
            "conversation": {
                "conversation_id": "conversation-1",
                "message_id": "mapping-parent",
                "parent_message_id": "mapping-parent",
            }
        }

    client.attach_conversation = mapping_attach

    client.send(
        "ordinary prompt",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="stale-parent",
            parent_message_id="stale-parent",
        ),
    )
    assert client.ordinary_parent_message_id == "mapping-parent"

    result = client.send_payload(
        {
            "conversation_id": "conversation-1",
            "parent_message_id": "mapping-parent",
            "action": "next",
        }
    )
    assert result == {"ok": True}
    assert client.raw_payload_calls == 1
    assert client.raw_payload_parent == "mapping-parent"


def test_fenced_mutation_entrypoint_cannot_be_deleted_normally() -> None:
    client = _RaceFenceClient()
    BrowserlessRequestTransport(client)

    with pytest.raises(TypeError, match="cannot delete fenced mutation entrypoint send"):
        del client.send
