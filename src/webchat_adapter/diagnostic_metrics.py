from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


def _optional_non_negative_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


@dataclass
class ChatMetrics:
    first_token: float | None = None
    last_token: float | None = None
    total: float | None = None
    requirements_latency: float | None = None
    stream_duration: float | None = None
    chars_per_second: float | None = None
    backend_status: int | None = None

    def __post_init__(self) -> None:
        self.first_token = _optional_non_negative_float(self.first_token)
        self.last_token = _optional_non_negative_float(self.last_token)
        self.total = _optional_non_negative_float(self.total)
        self.requirements_latency = _optional_non_negative_float(
            self.requirements_latency
        )
        self.stream_duration = _optional_non_negative_float(self.stream_duration)
        self.chars_per_second = _optional_non_negative_float(self.chars_per_second)
        self.backend_status = _optional_positive_int(self.backend_status)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ChatMetrics":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            first_token=payload.get("first_token"),
            last_token=payload.get("last_token"),
            total=payload.get("total"),
            requirements_latency=payload.get("requirements_latency"),
            stream_duration=payload.get("stream_duration"),
            chars_per_second=payload.get("chars_per_second"),
            backend_status=payload.get("backend_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_token": self.first_token,
            "last_token": self.last_token,
            "total": self.total,
            "requirements_latency": self.requirements_latency,
            "stream_duration": self.stream_duration,
            "chars_per_second": self.chars_per_second,
            "backend_status": self.backend_status,
        }


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
