from __future__ import annotations

from contextvars import Context
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.types import ChatConversation, ChatMessage, ChatResponse


_EPHEMERAL = {
    "x-conduit-token",
    "openai-sentinel-chat-requirements-token",
    "openai-sentinel-proof-token",
    "openai-sentinel-turnstile-token",
}


def _lower_names(headers: dict[str, str]) -> set[str]:
    return {str(key).strip().lower() for key in headers}


def _max_time(command: list[str]) -> float:
    index = command.index("--max-time")
    return float(command[index + 1])


class _ScopedFlowClient:
    def __init__(self, *, send_delay: float = 0.0) -> None:
        self.timeout = 90.0
        self.send_delay = float(send_delay)
        self.base_headers = {
            "authorization": "Bearer test",
            "user-agent": "scope-test-agent",
            "OpenAI-Sentinel-Chat-Requirements-Token": "stale-requirements",
            "openai-sentinel-proof-token": "stale-proof",
            "OPENAI-SENTINEL-TURNSTILE-TOKEN": "stale-turnstile",
            "X-Conduit-Token": "stale-conduit",
        }
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.records: list[tuple[str, dict[str, str], float]] = []
        self.foreign_headers: dict[str, str] | None = None
        self.foreign_max_time: float | None = None

    def _build_headers(self, extra=None):
        headers = dict(self.base_headers)
        headers.update(
            {
                str(key): str(value)
                for key, value in dict(extra or {}).items()
                if value is not None
            }
        )
        return headers

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

    def _record(self, stage: str, headers: dict[str, str], *, method: str = "GET") -> None:
        command = self._build_curl_command(
            method,
            f"https://chatgpt.com/{stage}",
            headers,
            "headers.txt",
        )
        self.records.append((stage, dict(headers), _max_time(command)))

    def _json_request(self, method, url, payload, headers):
        if url.endswith("/chat-requirements/prepare"):
            self._record("sentinel_prepare", dict(headers), method=method)
            return 200, {
                "persona": "chatgpt-test",
                "prepare_token": "prepare-token",
                "proofofwork": {"required": False},
                "so": {"required": False},
                "turnstile": {"required": False},
            }
        if url.endswith("/chat-requirements/finalize"):
            self._record("sentinel_finalize", dict(headers), method=method)
            return 200, {
                "persona": "chatgpt-test",
                "token": "requirements-token",
                "expire_after": 60,
                "expire_at": 9999999999,
            }
        raise AssertionError(f"unexpected URL: {url}")

    def _get_ready_requirements(self):
        raise AssertionError("owner browserless flow must bind finalized requirements")

    def start_sentinel_bundle_refill(self, *args, **kwargs):
        return False

    def send(self, prompt, *, conversation=None, on_token=None, on_event=None, **kwargs):
        requirements, proof = self._get_ready_requirements()
        assert proof is None
        assert requirements["token"] == "requirements-token"

        prepare_headers = self._build_headers(
            {
                "x-openai-target-path": "/backend-api/f/conversation/prepare",
                "x-openai-target-route": "/backend-api/f/conversation/prepare",
            }
        )
        self._record("conversation_prepare", prepare_headers, method="POST")

        final_headers = self._build_headers(
            {
                "x-openai-target-path": "/backend-api/f/conversation",
                "x-openai-target-route": "/backend-api/f/conversation",
                "openai-sentinel-chat-requirements-token": requirements["token"],
                "x-conduit-token": "current-conduit",
            }
        )
        self._record("conversation_write", final_headers, method="POST")

        foreign = Context()
        self.foreign_headers = foreign.run(
            self._build_headers,
            {"x-openai-target-path": "/backend-api/conversations"},
        )
        foreign_command = foreign.run(
            self._build_curl_command,
            "GET",
            "https://chatgpt.com/backend-api/conversations",
            self.foreign_headers,
            "headers.txt",
        )
        self.foreign_max_time = _max_time(foreign_command)

        if self.send_delay > 0:
            sleep(self.send_delay)
        if on_token is not None:
            on_token("stream answer")
        return ChatResponse(
            text="stream answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="canonical-message",
                parent_message_id="canonical-message",
            ),
        )

    def attach_conversation(self, conversation):
        headers = self._build_headers(
            {"x-openai-target-path": "/backend-api/conversation/attached"}
        )
        self._record("canonical_attach", headers)
        return SimpleNamespace(
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="attached-parent",
                parent_message_id="attached-parent",
            )
        )

    def get_status(self, conversation):
        headers = self._build_headers(
            {"x-openai-target-path": "/backend-api/conversation/status"}
        )
        self._record("canonical_status", headers)
        return SimpleNamespace(status="completed", finish_reason="stop")

    def get_messages(self, conversation, **kwargs):
        headers = self._build_headers(
            {"x-openai-target-path": "/backend-api/conversation/messages"}
        )
        self._record("canonical_messages", headers)
        return [
            ChatMessage(role="user", text="prompt", message_id="user-message"),
            ChatMessage(
                role="assistant",
                text="canonical answer",
                message_id="canonical-message",
                model="gpt-test",
                finish_reason="stop",
            ),
        ]


def test_browserless_health_strips_ephemeral_credentials_without_write_deadline() -> None:
    client = _ScopedFlowClient()
    transport = BrowserlessRequestTransport(client)

    health = transport.health(
        ChatConversation(
            conversation_id="conversation-1",
            message_id="message-1",
            parent_message_id="message-1",
        )
    )

    assert health.ready is True
    assert health.canonical_status == "completed"
    assert health.canonical_read_checked is True
    assert len(client.records) == 1
    stage, headers, max_time = client.records[0]
    assert stage == "canonical_status"
    assert _lower_names(headers).isdisjoint(_EPHEMERAL)
    # Health has no caller-supplied write deadline; it preserves ordinary read
    # timeout semantics while applying only browserless no-replay header hygiene.
    assert max_time == pytest.approx(90.0)

    ordinary_headers = client._build_headers(
        {"x-openai-target-path": "/backend-api/conversations"}
    )
    assert _EPHEMERAL.issubset(_lower_names(ordinary_headers))
    assert client.timeout == pytest.approx(90.0)


def test_request_scope_covers_attach_sentinel_write_and_canonical_reads() -> None:
    client = _ScopedFlowClient(send_delay=0.02)
    transport = BrowserlessRequestTransport(client)

    response = transport.send_text(
        "hello",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="stale-parent",
            parent_message_id="stale-parent",
        ),
        timeout=0.5,
    )

    assert response.text == "canonical answer"
    by_stage = {stage: (headers, max_time) for stage, headers, max_time in client.records}
    assert set(by_stage) == {
        "canonical_attach",
        "sentinel_prepare",
        "sentinel_finalize",
        "conversation_prepare",
        "conversation_write",
        "canonical_status",
        "canonical_messages",
    }

    for stage, (headers, max_time) in by_stage.items():
        assert 0.0 < max_time <= 0.5
        lower = _lower_names(headers)
        if stage == "conversation_write":
            assert headers["openai-sentinel-chat-requirements-token"] == "requirements-token"
            assert headers["x-conduit-token"] == "current-conduit"
            assert "openai-sentinel-proof-token" not in lower
            assert "openai-sentinel-turnstile-token" not in lower
        else:
            assert lower.isdisjoint(_EPHEMERAL)

    assert by_stage["canonical_status"][1] < by_stage["sentinel_prepare"][1]
    assert by_stage["canonical_messages"][1] <= by_stage["canonical_status"][1]

    # A foreign context on the same shared client remains ordinary and therefore
    # sees its unchanged caller-owned headers/timeout rather than browserless policy.
    assert client.foreign_headers is not None
    assert "openai-sentinel-proof-token" in _lower_names(client.foreign_headers)
    assert client.foreign_max_time == pytest.approx(90.0)
    assert client.timeout == pytest.approx(90.0)


def test_expired_postwrite_canonical_read_is_ambiguous_without_full_client_timeout() -> None:
    client = _ScopedFlowClient(send_delay=0.06)
    transport = BrowserlessRequestTransport(client)

    started = monotonic()
    with pytest.raises(BrowserlessRequestTransportError) as captured:
        transport.send_text("hello", timeout=0.03)
    elapsed = monotonic() - started

    error = captured.value
    assert error.request_stage == "canonical_reconciliation"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert elapsed < 0.20
    assert client.timeout == pytest.approx(90.0)


def test_sentinel_preflight_curl_uses_total_invocation_deadline() -> None:
    client = _ScopedFlowClient()
    transport = BrowserlessRequestTransport(client)

    response = transport.send_text("hello", timeout=0.2)

    assert response.text == "canonical answer"
    sentinel = {
        stage: max_time
        for stage, _headers, max_time in client.records
        if stage in {"sentinel_prepare", "sentinel_finalize"}
    }
    assert set(sentinel) == {"sentinel_prepare", "sentinel_finalize"}
    assert 0.0 < sentinel["sentinel_prepare"] <= 0.2 + 1e-9
    assert 0.0 < sentinel["sentinel_finalize"] <= sentinel["sentinel_prepare"]
