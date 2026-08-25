from __future__ import annotations

from functools import wraps
from types import SimpleNamespace

from chatgpt_web_adapter.browserless_request_scope import gate_browserless_request_execute
from chatgpt_web_adapter.browserless_request_transport import BrowserlessRequestTransport
from chatgpt_web_adapter.browserless_shared_write_fence import (
    _mutation_authority,
    unfenced_mutation_callable,
)


class _CompatibleSharedClient:
    def __init__(self) -> None:
        self.timeout = 60.0
        self.base_headers = {"user-agent": "multi-transport-test"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.send_calls: list[str] = []

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **dict(extra or {})}

    def _json_request(self, method, url, payload, headers):
        raise AssertionError("direct-send capture regression must not perform network I/O")

    def send(self, prompt, *, conversation=None, **kwargs):
        self.send_calls.append(prompt)
        return f"sent:{prompt}"

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation=conversation)

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", message_id="message-1")

    def get_messages(self, conversation, **kwargs):
        return []


def _execute_direct_probe(transport: BrowserlessRequestTransport, text: str) -> str:
    def direct_probe(
        current_transport,
        current_text,
        *,
        conversation,
        timeout,
        poll_interval,
        on_token,
        on_event,
    ):
        return current_transport._direct_send(current_text, conversation=conversation)

    execute = gate_browserless_request_execute(direct_probe)

    # Real BrowserlessRequestTransport execution already owns browserless_request
    # mutation authority before request-scope code runs.
    with _mutation_authority(transport.client, "browserless_request"):
        return execute(
            transport,
            text,
            conversation=None,
            timeout=1.0,
            poll_interval=0.1,
            on_token=None,
            on_event=None,
        )


def test_second_transport_unwraps_first_transport_send_fence_before_direct_execution() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    second = BrowserlessRequestTransport(client)

    # The first transport installs the shared-client mutation fence. A compatible
    # second transport therefore observes that wrapper during its original init.
    assert second._direct_send is not unfenced_mutation_callable(second._direct_send)

    result = _execute_direct_probe(second, "probe")

    assert result == "sent:probe"
    assert client.send_calls == ["probe"]
    assert second._direct_send is unfenced_mutation_callable(second._direct_send)
    assert first._write_lock is second._write_lock


def test_second_transport_preserves_plain_decorator_around_preexisting_send_fence() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    first_fenced_send = client.send
    decorator_calls: list[str] = []

    # A caller decorates the public mutation surface after the first transport has
    # installed its fence. The assignment guard creates:
    # fence(decorator(first_fence(original))).
    def decorated_send(prompt, *, conversation=None, **kwargs):
        decorator_calls.append(prompt)
        return first_fenced_send(prompt, conversation=conversation, **kwargs)

    client.send = decorated_send
    second = BrowserlessRequestTransport(client)

    result = _execute_direct_probe(second, "plain-decorator")

    assert result == "sent:plain-decorator"
    assert decorator_calls == ["plain-decorator"]
    assert client.send_calls == ["plain-decorator"]
    # Browserless direct normalization must preserve the unrelated decorator
    # rather than jumping straight to the original compatible-client method.
    assert getattr(second._direct_send, "__wrapped__", None) is decorated_send
    assert first._write_lock is second._write_lock


def test_second_transport_preserves_wraps_decorator_that_copied_fence_metadata() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    first_fenced_send = client.send
    decorator_calls: list[str] = []

    # functools.wraps copies the wrapped fence's __dict__. In particular, copied
    # package metadata must not make this unrelated decorator look like the real
    # fence wrapper and get stripped from browserless direct execution.
    @wraps(first_fenced_send)
    def decorated_send(prompt, *, conversation=None, **kwargs):
        decorator_calls.append(prompt)
        return first_fenced_send(prompt, conversation=conversation, **kwargs)

    copied_fence_identity = getattr(
        decorated_send,
        "_cwa_browserless_shared_write_fence_wrapper",
        None,
    )
    assert copied_fence_identity is first_fenced_send
    assert copied_fence_identity is not decorated_send

    client.send = decorated_send
    second = BrowserlessRequestTransport(client)

    result = _execute_direct_probe(second, "wraps-decorator")

    assert result == "sent:wraps-decorator"
    assert decorator_calls == ["wraps-decorator"]
    assert client.send_calls == ["wraps-decorator"]
    assert getattr(second._direct_send, "__wrapped__", None) is decorated_send
    assert first._write_lock is second._write_lock


def test_callable_object_decorator_preserves_ordinary_and_second_transport_direct_send() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    first_fenced_send = client.send
    decorator_calls: list[str] = []

    class Decorator:
        def __init__(self, delegate):
            self.delegate = delegate

        def __call__(self, prompt, *, conversation=None, **kwargs):
            decorator_calls.append(prompt)
            return self.delegate(prompt, conversation=conversation, **kwargs)

    decorated_send = Decorator(first_fenced_send)
    client.send = decorated_send

    # The assignment fence must preserve a class-based decorator even before a
    # second transport exists. Previously the decorator re-entered its captured
    # old fence under send authority and failed here.
    ordinary = client.send("callable-ordinary", conversation=None)
    assert ordinary == "sent:callable-ordinary"

    second = BrowserlessRequestTransport(client)
    direct = _execute_direct_probe(second, "callable-direct")

    assert direct == "sent:callable-direct"
    assert decorator_calls == ["callable-ordinary", "callable-direct"]
    assert client.send_calls == ["callable-ordinary", "callable-direct"]
    assert first._write_lock is second._write_lock


def test_slotted_callable_object_decorator_is_a_direct_predecessor_edge() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    first_fenced_send = client.send
    decorator_calls: list[str] = []

    class SlottedDecorator:
        __slots__ = ("delegate",)

        def __init__(self, delegate):
            self.delegate = delegate

        def __call__(self, prompt, *, conversation=None, **kwargs):
            decorator_calls.append(prompt)
            return self.delegate(prompt, conversation=conversation, **kwargs)

    decorated_send = SlottedDecorator(first_fenced_send)
    assert not hasattr(decorated_send, "__dict__")
    client.send = decorated_send
    second = BrowserlessRequestTransport(client)

    result = _execute_direct_probe(second, "slotted-callable")

    assert result == "sent:slotted-callable"
    assert decorator_calls == ["slotted-callable"]
    assert client.send_calls == ["slotted-callable"]
    assert first._write_lock is second._write_lock


def test_inherited_list_slots_preserve_exact_predecessor_for_ordinary_and_direct_send() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    first_fenced_send = client.send
    decorator_calls: list[str] = []

    class DelegateSlotBase:
        __slots__ = ["delegate"]

        def __init__(self, delegate):
            self.delegate = delegate

    class InheritedSlottedDecorator(DelegateSlotBase):
        __slots__ = ()

        def __call__(self, prompt, *, conversation=None, **kwargs):
            decorator_calls.append(prompt)
            return self.delegate(prompt, conversation=conversation, **kwargs)

    decorated_send = InheritedSlottedDecorator(first_fenced_send)
    assert not hasattr(decorated_send, "__dict__")
    assert isinstance(DelegateSlotBase.__slots__, list)
    client.send = decorated_send

    ordinary = client.send("inherited-slot-ordinary", conversation=None)
    assert ordinary == "sent:inherited-slot-ordinary"

    second = BrowserlessRequestTransport(client)
    direct = _execute_direct_probe(second, "inherited-slot-direct")

    assert direct == "sent:inherited-slot-direct"
    assert decorator_calls == ["inherited-slot-ordinary", "inherited-slot-direct"]
    assert client.send_calls == ["inherited-slot-ordinary", "inherited-slot-direct"]
    assert first._write_lock is second._write_lock
