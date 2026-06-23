from __future__ import annotations

import time
from typing import Any, Callable

from .exceptions import RequestError
from .types import ChatMetrics


def _chars_per_second(text: str, stream_duration: float | None) -> float | None:
    if stream_duration is None or stream_duration <= 0:
        return None
    return len(text) / stream_duration


def _emit_event(
    callback: Callable[[dict[str, Any]], None] | None,
    event_type: str,
    **payload: Any,
) -> None:
    if callback is None:
        return
    callback({"type": event_type, **payload})


def _is_stream_request(
    headers: Any,
    no_buffer: Any,
) -> bool:
    if no_buffer is not True or not isinstance(headers, dict):
        return False
    return headers.get("accept") == "text/event-stream"


def _fill_request_error(
    error: RequestError,
    *,
    status_code: int | None,
    endpoint: str | None,
    request_stage: str | None,
) -> None:
    if error.status_code is None and status_code is not None:
        error.status_code = status_code
    if endpoint is not None:
        error.endpoint = endpoint
    if error.request_stage is None and request_stage is not None:
        error.request_stage = request_stage


def send_with_expanded_metrics(original_send: Callable[..., Any]) -> Callable[..., Any]:
    def send(self: Any, *args: Any, **kwargs: Any) -> Any:
        on_event = kwargs.pop("on_event", None)
        on_token = kwargs.get("on_token")
        requirements_latency: float | None = None
        backend_status: int | None = None
        stream_endpoint: str | None = None
        request_stage: str | None = None
        stream_started = False
        first_token_seen = False
        request_started_at = time.perf_counter()
        original_get_ready_requirements = self._get_ready_requirements
        original_extract_status_code = self._extract_status_code
        original_build_curl_command = self._build_curl_command

        def timed_get_ready_requirements() -> tuple[dict[str, Any], str | None]:
            nonlocal requirements_latency, request_stage
            request_stage = "chat_requirements"
            started_at = time.perf_counter()
            requirements, proof_header = original_get_ready_requirements()
            requirements_latency = time.perf_counter() - started_at
            turnstile = requirements.get("turnstile") if isinstance(requirements, dict) else None
            _emit_event(
                on_event,
                "requirements_ready",
                latency=requirements_latency,
                token_present=bool(requirements.get("token")) if isinstance(requirements, dict) else False,
                proof_header_present=bool(proof_header),
                turnstile_required=bool(turnstile.get("required")) if isinstance(turnstile, dict) else False,
            )
            return requirements, proof_header

        def capture_status_code(header_text: str) -> int:
            nonlocal backend_status
            status = original_extract_status_code(header_text)
            backend_status = status if status > 0 else None
            return status

        def emit_stream_started_build_curl_command(
            method: str,
            url: str,
            headers: dict[str, str],
            header_path: str,
            body_path: str | None = None,
            *,
            no_buffer: bool = False,
            follow_redirects: bool = False,
        ) -> list[str]:
            nonlocal request_stage, stream_endpoint, stream_started
            command = original_build_curl_command(
                method,
                url,
                headers,
                header_path,
                body_path,
                no_buffer=no_buffer,
                follow_redirects=follow_redirects,
            )
            if not stream_started and _is_stream_request(headers, no_buffer):
                request_stage = "conversation_stream"
                stream_endpoint = url
                stream_started = True
                _emit_event(
                    on_event,
                    "stream_started",
                    method=method.upper(),
                    url=url,
                )
            return command

        def eventful_on_token(token: str) -> None:
            nonlocal first_token_seen
            elapsed = time.perf_counter() - request_started_at
            if not first_token_seen:
                first_token_seen = True
                _emit_event(on_event, "first_token", token=token, elapsed=elapsed)
            _emit_event(on_event, "assistant_token", token=token, elapsed=elapsed)
            if on_token is not None:
                on_token(token)

        kwargs["on_token"] = eventful_on_token if on_event is not None else on_token
        _emit_event(
            on_event,
            "request_started",
            model=kwargs.get("model"),
            has_conversation=kwargs.get("conversation") is not None,
            has_media=bool(kwargs.get("media")),
        )
        self._get_ready_requirements = timed_get_ready_requirements
        self._extract_status_code = capture_status_code
        self._build_curl_command = emit_stream_started_build_curl_command
        try:
            response = original_send(self, *args, **kwargs)
        except Exception as error:
            if isinstance(error, RequestError):
                _fill_request_error(
                    error,
                    status_code=backend_status,
                    endpoint=stream_endpoint,
                    request_stage=request_stage,
                )
            _emit_event(
                on_event,
                "error",
                error_type=type(error).__name__,
                message=str(error),
                status_code=getattr(error, "status_code", None),
                endpoint=getattr(error, "endpoint", None),
                body_preview=getattr(error, "body_preview", None),
                request_stage=getattr(error, "request_stage", None),
            )
            raise
        finally:
            self._get_ready_requirements = original_get_ready_requirements
            self._extract_status_code = original_extract_status_code
            self._build_curl_command = original_build_curl_command

        previous_metrics = getattr(response, "metrics", None)
        total_latency = getattr(previous_metrics, "total", None)
        if (
            total_latency is not None
            and requirements_latency is not None
            and total_latency >= requirements_latency
        ):
            stream_duration = total_latency - requirements_latency
        else:
            stream_duration = total_latency
        text = getattr(response, "text", "")
        if text is None:
            text = ""
        else:
            text = str(text)
        response.metrics = ChatMetrics(
            first_token=getattr(previous_metrics, "first_token", None),
            last_token=getattr(previous_metrics, "last_token", None),
            total=total_latency,
            requirements_latency=requirements_latency,
            stream_duration=stream_duration,
            chars_per_second=_chars_per_second(text, stream_duration),
            backend_status=backend_status,
        )
        _emit_event(
            on_event,
            "stream_completed",
            conversation_id=getattr(response.conversation, "conversation_id", None),
            message_id=getattr(response.conversation, "message_id", None),
            text_length=len(text),
        )
        _emit_event(
            on_event,
            "stream_done",
            conversation_id=getattr(response.conversation, "conversation_id", None),
            message_id=getattr(response.conversation, "message_id", None),
            text_length=len(text),
        )
        _emit_event(
            on_event,
            "request_completed",
            conversation_id=getattr(response.conversation, "conversation_id", None),
            message_id=getattr(response.conversation, "message_id", None),
            finish_reason=getattr(response.conversation, "finish_reason", None),
            total=response.metrics.total,
        )
        return response

    return send
