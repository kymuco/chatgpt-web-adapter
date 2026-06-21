from __future__ import annotations

import time
from typing import Any, Callable

from .types import ChatMetrics


def _chars_per_second(text: str, stream_duration: float | None) -> float | None:
    if stream_duration is None or stream_duration <= 0:
        return None
    return len(text) / stream_duration


def send_with_expanded_metrics(original_send: Callable[..., Any]) -> Callable[..., Any]:
    def send(self: Any, *args: Any, **kwargs: Any) -> Any:
        requirements_latency: float | None = None
        backend_status: int | None = None
        original_get_ready_requirements = self._get_ready_requirements
        original_extract_status_code = self._extract_status_code

        def timed_get_ready_requirements() -> tuple[dict[str, Any], str | None]:
            nonlocal requirements_latency
            started_at = time.perf_counter()
            try:
                return original_get_ready_requirements()
            finally:
                requirements_latency = time.perf_counter() - started_at

        def capture_status_code(header_text: str) -> int:
            nonlocal backend_status
            status = original_extract_status_code(header_text)
            backend_status = status if status > 0 else None
            return status

        self._get_ready_requirements = timed_get_ready_requirements
        self._extract_status_code = capture_status_code
        try:
            response = original_send(self, *args, **kwargs)
        finally:
            self._get_ready_requirements = original_get_ready_requirements
            self._extract_status_code = original_extract_status_code

        previous_metrics = getattr(response, "metrics", None)
        stream_duration = getattr(previous_metrics, "total", None)
        text = getattr(response, "text", "")
        if text is None:
            text = ""
        else:
            text = str(text)
        response.metrics = ChatMetrics(
            first_token=getattr(previous_metrics, "first_token", None),
            last_token=getattr(previous_metrics, "last_token", None),
            total=getattr(previous_metrics, "total", None),
            requirements_latency=requirements_latency,
            stream_duration=stream_duration,
            chars_per_second=_chars_per_second(text, stream_duration),
            backend_status=backend_status,
        )
        return response

    return send
