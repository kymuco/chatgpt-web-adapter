from __future__ import annotations

import time
from types import SimpleNamespace

from chatgpt_web_adapter.client import DEFAULT_STREAM_RECOVERY_POLL_TIMEOUT_SECONDS
from chatgpt_web_adapter.conversation_prepare import prepare_text_turn
from chatgpt_web_adapter.diagnostic_metrics import send_with_expanded_metrics
from chatgpt_web_adapter.prepared_text_send import send_existing_text_prepared
from chatgpt_web_adapter.types import ChatConversation, ChatMetrics, ChatResponse


def test_prepare_requires_explicit_ok_status() -> None:
    class Client:
        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        @staticmethod
        def _json_request(method, url, payload, headers):
            return 200, {"conduit_token": "secret-conduit"}

    result, _payload = prepare_text_turn(
        Client(),
        "hello",
        model="gpt-5-6-thinking",
        conversation={"conversation_id": "conv-1", "message_id": "parent-1"},
        partial_query_message_id="user-1",
    )

    assert result.status_code == 200
    assert result.conduit_token_present is True
    assert result.status_ok is False


def test_fallback_token_metrics_exclude_pre_requirements_delay() -> None:
    class Client:
        @staticmethod
        def _get_ready_requirements():
            return {"token": "chat-token", "turnstile": {"required": False}}, "proof"

        @staticmethod
        def _extract_status_code(header_text):
            return 200

        @staticmethod
        def _build_curl_command(
            method,
            url,
            headers,
            header_path,
            body_path=None,
            *,
            no_buffer=False,
            follow_redirects=False,
        ):
            return [method, url]

    def prepared_like_send(self, *args, **kwargs):
        # Simulate a slow prepare phase that is intentionally outside the helper's
        # returned `total` metric.
        time.sleep(0.02)
        total_started = time.perf_counter()
        self._get_ready_requirements()
        kwargs["on_token"]("ok")
        total = time.perf_counter() - total_started
        return ChatResponse(
            text="ok",
            conversation=ChatConversation(
                conversation_id="conv-1",
                message_id="assistant-1",
            ),
            metrics=ChatMetrics(total=total),
        )

    response = send_with_expanded_metrics(prepared_like_send)(
        Client(),
        model="gpt-5-6-thinking",
        conversation=ChatConversation(conversation_id="conv-1", message_id="parent-1"),
    )

    assert response.metrics.first_token is not None
    assert response.metrics.last_token is not None
    assert response.metrics.total is not None
    assert 0 <= response.metrics.first_token <= response.metrics.last_token
    assert response.metrics.last_token <= response.metrics.total


def test_prepared_recovery_uses_legacy_timeout_floor() -> None:
    class Client:
        def __init__(self) -> None:
            self.timeout = 1
            self.auth = SimpleNamespace(turnstile_token=None)
            self.prefetched_requirements = None
            self.prefetched_proof_header = None
            self.prefetched_ts = 0.0
            self.recovery_timeout = None

        @staticmethod
        def _conversation_to_dict(conversation):
            if isinstance(conversation, ChatConversation):
                return conversation.to_dict()
            return dict(conversation)

        @staticmethod
        def _normalize_reasoning_effort(reasoning_effort):
            return reasoning_effort

        @staticmethod
        def _resolve_model(model, reasoning_effort):
            return model

        @staticmethod
        def _create_messages(prompt, system, *, image_requests=None, system_hints=None):
            return [
                {
                    "id": "user-1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [prompt]},
                }
            ]

        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        @staticmethod
        def _emit_event(callback, event_type, **payload):
            if callback is not None:
                callback({"type": event_type, **payload})

        @staticmethod
        def _json_request(method, url, payload, headers):
            return 200, {"status": "ok", "conduit_token": "secret-conduit"}

        @staticmethod
        def _get_ready_requirements():
            return {"token": "chat-token", "turnstile": {"required": False}}, "proof"

        @staticmethod
        def _parse_event(event_payload, state):
            return [], None

        @staticmethod
        def _stream_backend_payload(payload, headers, *, on_token=None, on_event=None):
            return "conv-1", None, ""

        def _poll_conversation_after_prepare(
            self,
            conversation_id,
            *,
            previous_message_id,
            timeout,
            interval,
            on_token=None,
            on_event=None,
            reason,
            allow_global_fallback,
        ):
            self.recovery_timeout = timeout
            return (
                {
                    "id": "assistant-final",
                    "metadata": {"finish_details": {"type": "stop"}},
                },
                "done",
                {},
            )

        @staticmethod
        def _capture_message_diagnostics(message, diagnostics):
            return None

    client = Client()
    response = send_existing_text_prepared(
        client,
        "hello",
        model="gpt-5-6-thinking",
        conversation=ChatConversation(conversation_id="conv-1", message_id="parent-1"),
    )

    assert response.text == "done"
    assert client.recovery_timeout == DEFAULT_STREAM_RECOVERY_POLL_TIMEOUT_SECONDS
