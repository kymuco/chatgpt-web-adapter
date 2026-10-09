from __future__ import annotations

import asyncio
from contextvars import Context
import threading
from time import monotonic
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browserless_request_transport as browserless_module
from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessProtocolDriftError,
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.sentinel_bundle import prepared_send_active
from chatgpt_web_adapter.types import ChatMessage


_PREPARE_PATH = "/backend-api/f/conversation/prepare"
_WRITE_PATH = "/backend-api/f/conversation"
_SENTINEL_PREPARE_PATH = "/backend-api/sentinel/chat-requirements/prepare"
_SENTINEL_FINALIZE_PATH = "/backend-api/sentinel/chat-requirements/finalize"
_EPHEMERAL_HEADERS = {
    "x-conduit-token",
    "openai-sentinel-chat-requirements-token",
    "openai-sentinel-proof-token",
    "openai-sentinel-turnstile-token",
}


class _IsolationClient:
    def __init__(self, *, failure_at: str | None = None) -> None:
        self.failure_at = failure_at
        self.timeout = 60.0
        self.base_headers = {"user-agent": "test-agent"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.delegate_ready_calls = 0
        self.delegate_header_calls = 0
        self.delegate_refill_calls = 0
        self.json_request_calls = 0
        self.send_calls = 0

    def _get_ready_requirements(self):
        self.delegate_ready_calls += 1
        return {"token": "foreign-token"}, "foreign-proof"

    def _build_headers(self, extra=None):
        target_path = dict(extra or {}).get("x-openai-target-path")
        if self.failure_at == "prepare_headers" and target_path == _SENTINEL_PREPARE_PATH:
            raise OSError("prepare headers unavailable")
        if self.failure_at == "finalize_headers" and target_path == _SENTINEL_FINALIZE_PATH:
            raise OSError("finalize headers unavailable")
        self.delegate_header_calls += 1
        return {"delegated": "yes", **(extra or {})}

    def _build_curl_command(
        self,
        method,
        url,
        headers,
        header_path,
        body_path=None,
        *,
        no_buffer=False,
        follow_redirects=False,
    ):
        return [
            "curl",
            "--max-time",
            str(self.timeout),
            "-X",
            str(method).upper(),
            str(url),
        ]

    def _json_request(self, method, url, payload, headers):
        self.json_request_calls += 1
        assert method == "POST"
        if url.endswith("/chat-requirements/prepare"):
            if self.failure_at == "prepare_request":
                raise OSError("prepare transport unavailable")
            return 200, {
                "persona": "chatgpt-test",
                "prepare_token": "prepare-token",
                "proofofwork": {"required": False},
                "so": {"required": False},
                "turnstile": {"required": False},
            }
        if url.endswith("/chat-requirements/finalize"):
            if self.failure_at == "finalize_request":
                raise OSError("finalize transport unavailable")
            return 200, {
                "persona": "chatgpt-test",
                "token": "requirements-token",
                "expire_after": 60,
                "expire_at": 9999999999,
            }
        raise AssertionError(f"unexpected URL: {url}")

    def start_sentinel_bundle_refill(self, *args, **kwargs):
        self.delegate_refill_calls += 1
        return "foreign-refill"

    def send(self, prompt, **kwargs):
        self.send_calls += 1
        raise AssertionError("send is not expected in these focused tests")

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", finish_reason="stop")

    def get_messages(self, conversation, **kwargs):
        return [ChatMessage(role="assistant", text="answer", message_id="message-1")]

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation=conversation)


class _CredentialIsolationClient(_IsolationClient):
    def __init__(self) -> None:
        super().__init__()
        self.base_headers.update(
            {
                "OpenAI-Sentinel-Chat-Requirements-Token": "stale-requirements",
                "openai-sentinel-proof-token": "stale-proof",
                "OPENAI-SENTINEL-TURNSTILE-TOKEN": "stale-turnstile",
                "X-Conduit-Token": "stale-conduit",
            }
        )
        self.request_headers: list[tuple[str, dict[str, str]]] = []

    def _build_headers(self, extra=None):
        self.delegate_header_calls += 1
        headers = dict(self.base_headers)
        headers.update(
            {
                key: value
                for key, value in dict(extra or {}).items()
                if value is not None
            }
        )
        return headers

    def _json_request(self, method, url, payload, headers):
        self.request_headers.append((str(url), dict(headers)))
        return super()._json_request(method, url, payload, headers)


class _RecoveryIsolationClient(_IsolationClient):
    def __init__(self) -> None:
        super().__init__()
        self.poll_timeouts: list[float] = []
        self.ws_started = 0
        self.ws_cancelled = 0

    async def _stream_handoff_via_ws_topic_async(self, *args, **kwargs):
        self.ws_started += 1
        try:
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            self.ws_cancelled += 1
            raise
        return "late-ws-result"

    def _poll_conversation_after_prepare(self, *args, timeout, **kwargs):
        self.poll_timeouts.append(float(timeout))
        return "poll-result"


def _curl_max_time(command: list[str]) -> float:
    index = command.index("--max-time")
    return float(command[index + 1])


def _lower_header_names(headers: dict[str, str]) -> set[str]:
    return {str(key).strip().lower() for key in headers}


def test_prepared_binding_is_visible_only_to_own_execution_context() -> None:
    client = _IsolationClient()
    transport = BrowserlessRequestTransport(client)
    requirements = {
        "token": "browserless-token",
        "persona": "chatgpt-test",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    write_state = {"final_write_started": False}

    original_ready = client._get_ready_requirements
    original_headers = client._build_headers
    original_refill = client.start_sentinel_bundle_refill
    original_curl = client._build_curl_command
    deadline = monotonic() + 10.0

    with transport._bind_current_prepared_write(
        requirements,
        write_state=write_state,
        deadline=deadline,
    ):
        assert prepared_send_active() is True

        foreign = Context()
        assert foreign.run(prepared_send_active) is False
        assert foreign.run(client._get_ready_requirements) == (
            {"token": "foreign-token"},
            "foreign-proof",
        )
        foreign_headers = foreign.run(
            client._build_headers,
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
            },
        )
        assert foreign_headers["delegated"] == "yes"
        assert "x-oai-turn-trace-id" not in foreign_headers
        assert write_state["final_write_started"] is False
        assert foreign.run(client.start_sentinel_bundle_refill) == "foreign-refill"

        foreign_curl = foreign.run(
            client._build_curl_command,
            "POST",
            "https://chatgpt.com/backend-api/f/conversation",
            {},
            "headers.txt",
        )
        assert _curl_max_time(foreign_curl) == pytest.approx(60.0)

        foreign.run(setattr, client, "timeout", 77.0)
        foreign_curl_after_update = foreign.run(
            client._build_curl_command,
            "POST",
            "https://chatgpt.com/backend-api/f/conversation",
            {},
            "headers.txt",
        )
        assert _curl_max_time(foreign_curl_after_update) == pytest.approx(77.0)

        owner_curl = client._build_curl_command(
            "POST",
            "https://chatgpt.com/backend-api/f/conversation",
            {},
            "headers.txt",
        )
        owner_max_time = _curl_max_time(owner_curl)
        assert 0.0 < owner_max_time <= 10.0
        assert owner_max_time != pytest.approx(77.0)

        owner_requirements, owner_proof = client._get_ready_requirements()
        assert owner_requirements["token"] == "browserless-token"
        assert owner_proof is None
        owner_headers = client._build_headers(
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
            }
        )
        assert "x-oai-turn-trace-id" in owner_headers
        assert "delegated" not in owner_headers
        assert write_state["final_write_started"] is True
        assert client.start_sentinel_bundle_refill() is False

    assert prepared_send_active() is False
    assert client._get_ready_requirements == original_ready
    assert client._build_headers == original_headers
    assert client.start_sentinel_bundle_refill == original_refill
    assert client._build_curl_command == original_curl
    assert client.timeout == pytest.approx(77.0)
    assert client.delegate_ready_calls == 1
    assert client.delegate_header_calls == 1
    assert client.delegate_refill_calls == 1


def test_browserless_strips_inherited_ephemeral_credentials_from_every_request_plane() -> None:
    client = _CredentialIsolationClient()
    transport = BrowserlessRequestTransport(client)

    requirements = transport._acquire_unprotected_requirements()

    assert requirements["token"] == "requirements-token"
    assert len(client.request_headers) == 2
    for _url, headers in client.request_headers:
        assert _lower_header_names(headers).isdisjoint(_EPHEMERAL_HEADERS)
        assert headers["user-agent"] == "test-agent"

    write_state = {"final_write_started": False}
    with transport._bind_current_prepared_write(
        requirements,
        write_state=write_state,
        deadline=monotonic() + 10.0,
    ):
        owner_headers = client._build_headers(
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
                "openai-sentinel-chat-requirements-token": "requirements-token",
                "x-conduit-token": "current-conduit",
            }
        )
        lower_owner = _lower_header_names(owner_headers)
        assert "openai-sentinel-chat-requirements-token" in lower_owner
        assert "x-conduit-token" in lower_owner
        assert "openai-sentinel-proof-token" not in lower_owner
        assert "openai-sentinel-turnstile-token" not in lower_owner
        assert owner_headers["openai-sentinel-chat-requirements-token"] == "requirements-token"
        assert owner_headers["x-conduit-token"] == "current-conduit"

        with pytest.raises(BrowserlessProtocolDriftError):
            client._build_headers(
                {
                    "x-openai-target-path": _WRITE_PATH,
                    "openai-sentinel-proof-token": "forbidden-proof",
                }
            )
        with pytest.raises(BrowserlessProtocolDriftError):
            client._build_headers(
                {
                    "x-openai-target-path": _WRITE_PATH,
                    "openai-sentinel-chat-requirements-token": "stale-requirements",
                }
            )
        with pytest.raises(BrowserlessProtocolDriftError):
            client._build_headers(
                {
                    "x-openai-target-path": _PREPARE_PATH,
                    "x-conduit-token": "misplaced-conduit",
                }
            )


def test_recovery_poll_timeout_is_owner_deadline_scoped_and_foreign_unchanged() -> None:
    client = _RecoveryIsolationClient()
    transport = BrowserlessRequestTransport(client)
    requirements = {
        "token": "browserless-token",
        "persona": "chatgpt-test",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    write_state = {"final_write_started": True}

    with transport._bind_current_prepared_write(
        requirements,
        write_state=write_state,
        deadline=monotonic() + 1.0,
    ):
        assert client._poll_conversation_after_prepare(
            "conversation-id",
            timeout=90.0,
        ) == "poll-result"
        owner_timeout = client.poll_timeouts[-1]
        assert 0.0 < owner_timeout <= 1.0

        foreign = Context()
        assert foreign.run(
            client._poll_conversation_after_prepare,
            "conversation-id",
            timeout=90.0,
        ) == "poll-result"
        assert client.poll_timeouts[-1] == pytest.approx(90.0)


def test_websocket_recovery_is_cancelled_at_browserless_total_deadline() -> None:
    client = _RecoveryIsolationClient()
    transport = BrowserlessRequestTransport(client)
    requirements = {
        "token": "browserless-token",
        "persona": "chatgpt-test",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    write_state = {"final_write_started": True}

    started = monotonic()
    with transport._bind_current_prepared_write(
        requirements,
        write_state=write_state,
        deadline=started + 0.05,
    ):
        with pytest.raises(BrowserlessRequestTransportError) as captured:
            asyncio.run(client._stream_handoff_via_ws_topic_async("topic-id"))
    elapsed = monotonic() - started

    error = captured.value
    assert error.request_stage == "conversation_stream"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert client.ws_started == 1
    assert client.ws_cancelled == 1
    assert elapsed < 0.20


def test_expired_deadline_blocks_final_mutation_before_write_state_changes() -> None:
    client = _IsolationClient()
    transport = BrowserlessRequestTransport(client)
    requirements = {
        "token": "browserless-token",
        "persona": "chatgpt-test",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    write_state = {"final_write_started": False}

    with transport._bind_current_prepared_write(
        requirements,
        write_state=write_state,
        deadline=monotonic() - 1.0,
    ):
        with pytest.raises(BrowserlessRequestTransportError) as captured:
            client._build_headers(
                {
                    "x-openai-target-path": _WRITE_PATH,
                    "x-openai-target-route": _WRITE_PATH,
                }
            )

    error = captured.value
    assert error.request_stage == "browserless_write_deadline"
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert write_state["final_write_started"] is False


def test_expired_queued_call_stops_before_sentinel_or_send(monkeypatch) -> None:
    client = _IsolationClient()
    transport = BrowserlessRequestTransport(client)
    clock = iter((0.0, 2.0))

    class _AdvancingLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    transport._write_lock = _AdvancingLock()
    monkeypatch.setattr(browserless_module, "monotonic", lambda: next(clock))

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        transport.send_text("hello", timeout=1.0)

    error = captured.value
    assert error.request_stage == "browserless_write_queue"
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.json_request_calls == 0
    assert client.send_calls == 0


def test_multiple_browserless_transports_share_one_client_write_lock() -> None:
    client = _IsolationClient()
    first = BrowserlessRequestTransport(client)
    second = BrowserlessRequestTransport(client)
    other_client_transport = BrowserlessRequestTransport(_IsolationClient())

    assert first._write_lock is second._write_lock
    assert first._write_lock is not other_client_transport._write_lock
    assert first.governance()["browserless_shared_client_write_serialization"] == (
        "PER_CANONICAL_CLIENT"
    )
    assert first.governance()["browserless_timeout_scope"] == (
        "EXECUTION_CONTEXT_TOTAL_DEADLINE"
    )
    assert first.governance()["browserless_ephemeral_header_policy"] == (
        "STRIP_INHERITED_ALLOW_CURRENT_REQUIREMENTS_CONDUIT"
    )

    first_acquired = threading.Event()
    release_first = threading.Event()
    second_acquired = threading.Event()

    def hold_first() -> None:
        with first._write_lock:
            first_acquired.set()
            assert release_first.wait(2.0)

    def acquire_second() -> None:
        assert first_acquired.wait(2.0)
        with second._write_lock:
            second_acquired.set()

    first_thread = threading.Thread(target=hold_first)
    second_thread = threading.Thread(target=acquire_second)
    first_thread.start()
    assert first_acquired.wait(2.0)
    second_thread.start()

    assert second_acquired.wait(0.1) is False
    release_first.set()
    first_thread.join(2.0)
    second_thread.join(2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert second_acquired.is_set() is True


@pytest.mark.parametrize(
    ("failure_at", "expected_stage"),
    [
        ("prepare_headers", "browserless_sentinel_prepare"),
        ("prepare_request", "browserless_sentinel_prepare"),
        ("finalize_headers", "browserless_sentinel_finalize"),
        ("finalize_request", "browserless_sentinel_finalize"),
    ],
)
def test_generic_preflight_operational_failures_are_structured_zero_write(
    failure_at: str,
    expected_stage: str,
) -> None:
    client = _IsolationClient(failure_at=failure_at)

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.request_stage == expected_stage
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.send_calls == 0
