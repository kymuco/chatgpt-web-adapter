from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from .product_submission import ProductSubmissionAck
from .product_transport import ConversationInput, EventCallback, TokenCallback
from .types import ChatResponse, MediaItem

if TYPE_CHECKING:
    from .product_runtime import ChatGPTProductRuntime


class ProductSubmissionLifecycleUnavailableError(RuntimeError):
    """Fail-closed refusal before write when split submission is unavailable."""

    def __init__(self, *, transport: str, conversation_mode: str) -> None:
        self.transport = transport
        self.conversation_mode = conversation_mode
        super().__init__(
            "PRODUCT_SUBMISSION_LIFECYCLE_UNAVAILABLE: "
            f"transport={transport!r} conversation_mode={conversation_mode!r}; "
            "fallback=none"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": str(self),
            "transport": self.transport,
            "conversation_mode": self.conversation_mode,
            "write_may_have_been_submitted": False,
            "automatic_write_retry": False,
            "fallback_transport": None,
        }


def _submission_transport(
    runtime: ChatGPTProductRuntime,
    conversation_mode: str,
) -> Any:
    from .product_runtime import _normalize_conversation_mode

    mode = _normalize_conversation_mode(conversation_mode)
    writer = runtime.write_transport
    governance = dict(writer.governance())
    submit = getattr(writer, "submit_text", None)
    await_final = getattr(writer, "await_final", None)
    if (
        mode != "normal"
        or governance.get("submission_lifecycle_supported") is not True
        or not callable(submit)
        or not callable(await_final)
    ):
        raise ProductSubmissionLifecycleUnavailableError(
            transport=runtime.transport,
            conversation_mode=mode,
        )
    return writer


def submit_product_turn(
    runtime: ChatGPTProductRuntime,
    text: str,
    *,
    conversation: ConversationInput = None,
    timeout: float = 150.0,
    poll_interval: float = 0.5,
    on_token: TokenCallback = None,
    on_event: EventCallback = None,
    conversation_mode: str = "normal",
    browser_authority_policy: str | None = None,
    browser_authority_ttl_ms: int | None = None,
    model_profile: str | None = None,
    media: Sequence[MediaItem] | None = None,
) -> ProductSubmissionAck:
    """Submit one normal product turn and return before canonical finality."""

    from .product_runtime import (
        _browser_authority_override_kwargs,
        _model_profile_override_kwargs,
        _normalize_conversation_mode,
        _rich_input_scope,
    )

    mode = _normalize_conversation_mode(conversation_mode)
    writer = _submission_transport(runtime, mode)
    transport_kwargs = _browser_authority_override_kwargs(
        writer,
        browser_authority_policy=browser_authority_policy,
        browser_authority_ttl_ms=browser_authority_ttl_ms,
    )
    transport_kwargs.update(
        _model_profile_override_kwargs(
            writer,
            model_profile=model_profile,
        )
    )

    with _rich_input_scope(
        writer,
        media=media,
        conversation_mode=mode,
    ):
        ack = writer.submit_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
            **transport_kwargs,
        )
    if not isinstance(ack, ProductSubmissionAck):
        raise TypeError("write transport submit_text() must return ProductSubmissionAck")
    if ack.transport != runtime.transport:
        raise RuntimeError(
            "write transport returned submission for unexpected transport "
            f"{ack.transport!r}"
        )
    return ack


def await_product_submission(
    runtime: ChatGPTProductRuntime,
    submission: ProductSubmissionAck,
) -> ChatResponse:
    """Resolve canonical finality for a runtime-bound submission acknowledgement."""

    if not isinstance(submission, ProductSubmissionAck):
        raise TypeError("submission must be ProductSubmissionAck")
    if submission.transport != runtime.transport:
        raise ValueError("submission transport does not match selected runtime transport")
    writer = _submission_transport(runtime, "normal")
    response = writer.await_final(submission)
    if not isinstance(response, ChatResponse):
        raise TypeError("write transport await_final() must return ChatResponse")
    return response


def submission_lifecycle_snapshot(runtime: ChatGPTProductRuntime) -> dict[str, Any]:
    writer = runtime.write_transport
    snapshot = getattr(writer, "submission_lifecycle_snapshot", None)
    if not callable(snapshot):
        return {
            "supported": False,
            "pending": False,
            "submission_id": None,
        }
    value = snapshot()
    payload = dict(value) if isinstance(value, dict) else {}
    payload["supported"] = True
    return payload
