from __future__ import annotations

import webchat_adapter
from webchat_adapter import ChatMetrics, ChatResponse
from webchat_adapter.types import ChatMetrics as TypesChatMetrics


def test_chat_metrics_positional_compatibility() -> None:
    metrics = ChatMetrics(1.0, 2.0, 3.0)

    assert metrics.first_token == 1.0
    assert metrics.last_token == 2.0
    assert metrics.total == 3.0
    assert metrics.requirements_latency is None
    assert metrics.stream_duration is None
    assert metrics.chars_per_second is None
    assert metrics.backend_status is None


def test_chat_metrics_defaults_include_expanded_fields() -> None:
    metrics = ChatMetrics()

    assert metrics.first_token is None
    assert metrics.last_token is None
    assert metrics.total is None
    assert metrics.requirements_latency is None
    assert metrics.stream_duration is None
    assert metrics.chars_per_second is None
    assert metrics.backend_status is None


def test_chat_metrics_accepts_expanded_fields() -> None:
    metrics = ChatMetrics(
        first_token=0.1,
        last_token=0.5,
        total=0.7,
        requirements_latency=0.05,
        stream_duration=0.6,
        chars_per_second=12.5,
        backend_status=200,
    )

    assert metrics.first_token == 0.1
    assert metrics.last_token == 0.5
    assert metrics.total == 0.7
    assert metrics.requirements_latency == 0.05
    assert metrics.stream_duration == 0.6
    assert metrics.chars_per_second == 12.5
    assert metrics.backend_status == 200


def test_chat_metrics_normalizes_invalid_values_to_none() -> None:
    metrics = ChatMetrics(
        first_token="bad",
        last_token=-1,
        total=None,
        requirements_latency="0.2",
        stream_duration=-0.1,
        chars_per_second="bad",
        backend_status="bad",
    )

    assert metrics.first_token is None
    assert metrics.last_token is None
    assert metrics.total is None
    assert metrics.requirements_latency == 0.2
    assert metrics.stream_duration is None
    assert metrics.chars_per_second is None
    assert metrics.backend_status is None


def test_chat_metrics_from_dict_reads_expanded_fields() -> None:
    metrics = ChatMetrics.from_dict(
        {
            "first_token": 0.1,
            "last_token": 0.5,
            "total": 0.7,
            "requirements_latency": 0.05,
            "stream_duration": 0.6,
            "chars_per_second": 12.5,
            "backend_status": 200,
        }
    )

    assert metrics.to_dict() == {
        "first_token": 0.1,
        "last_token": 0.5,
        "total": 0.7,
        "requirements_latency": 0.05,
        "stream_duration": 0.6,
        "chars_per_second": 12.5,
        "backend_status": 200,
    }


def test_chat_metrics_export_is_shared_with_types_module() -> None:
    assert webchat_adapter.ChatMetrics is ChatMetrics
    assert TypesChatMetrics is ChatMetrics
    assert "ChatMetrics" in webchat_adapter.__all__


def test_chat_response_default_metrics_uses_expanded_metrics() -> None:
    response = ChatResponse(text="hello")

    assert isinstance(response.metrics, ChatMetrics)
    assert hasattr(response.metrics, "requirements_latency")
