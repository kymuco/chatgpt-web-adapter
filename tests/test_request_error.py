from __future__ import annotations

from webchat_adapter import RequestError


def test_request_error_preserves_string_message() -> None:
    error = RequestError(
        "backend status=500: internal failure",
        status_code=502,
        endpoint="https://example.test/backend",
        body_preview="full backend body",
        request_stage="conversation_stream",
    )

    assert str(error) == "backend status=500: internal failure"
    assert error.status_code == 502
    assert error.endpoint == "https://example.test/backend"
    assert error.body_preview == "full backend body"
    assert error.request_stage == "conversation_stream"
    assert error.to_dict() == {
        "message": "backend status=500: internal failure",
        "status_code": 502,
        "endpoint": "https://example.test/backend",
        "body_preview": "full backend body",
        "request_stage": "conversation_stream",
    }


def test_request_error_infers_fields_from_legacy_backend_message() -> None:
    error = RequestError("backend status=429: rate limited")

    assert str(error) == "backend status=429: rate limited"
    assert error.status_code == 429
    assert error.endpoint == "conversation"
    assert error.body_preview == "rate limited"
    assert error.request_stage == "conversation_stream"


def test_request_error_infers_fields_from_legacy_requirements_message() -> None:
    error = RequestError("chat-requirements status=403")

    assert error.status_code == 403
    assert error.endpoint == "chat-requirements"
    assert error.body_preview is None
    assert error.request_stage == "chat_requirements"


def test_request_error_defaults_structured_fields_to_none() -> None:
    error = RequestError("custom failure")

    assert error.status_code is None
    assert error.endpoint is None
    assert error.body_preview is None
    assert error.request_stage is None
