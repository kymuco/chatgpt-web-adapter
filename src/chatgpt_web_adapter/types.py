from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

MediaSource = bytes | bytearray | str | Path | os.PathLike[str]
MediaItem = MediaSource | tuple[MediaSource, str | None]
ConversationStatusValue = Literal[
    "completed",
    "running",
    "awaiting_tool_approval",
    "tool_calling",
    "tool_running",
    "user_last_message",
    "unknown",
]
CONVERSATION_STATUS_VALUES: tuple[ConversationStatusValue, ...] = (
    "completed",
    "running",
    "awaiting_tool_approval",
    "tool_calling",
    "tool_running",
    "user_last_message",
    "unknown",
)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _required_str(value: Any, field_name: str) -> str:
    value = _optional_str(value)
    if value is None:
        raise ValueError(f"{field_name} is required")
    return value


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


@dataclass(init=False)
class AuthData:
    accessToken: str | None = None
    accessTokenSource: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    expires: int | None = None
    proof_token: Any = None
    turnstile_token: str | None = None

    def __init__(
        self,
        accessToken: str | None = None,
        accessTokenSource: str | None = None,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        expires: int | None = None,
        proof_token: Any = None,
        turnstile_token: str | None = None,
        *,
        access_token: str | None = None,
        access_token_source: str | None = None,
        api_key: str | None = None,
        api_key_source: str | None = None,
    ) -> None:
        token = accessToken
        if token is None:
            token = access_token if access_token is not None else api_key
        token_source = accessTokenSource
        if token_source is None:
            token_source = (
                access_token_source
                if access_token_source is not None
                else api_key_source
            )
        self.accessToken = token
        self.accessTokenSource = token_source
        self.cookies = dict(cookies or {})
        self.headers = dict(headers or {})
        self.expires = expires
        self.proof_token = proof_token
        self.turnstile_token = turnstile_token

    @property
    def access_token(self) -> str | None:
        return self.accessToken

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        self.accessToken = value

    @property
    def access_token_source(self) -> str | None:
        return self.accessTokenSource

    @access_token_source.setter
    def access_token_source(self, value: str | None) -> None:
        self.accessTokenSource = value

    @property
    def api_key(self) -> str | None:
        return self.accessToken

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        self.accessToken = value

    @property
    def api_key_source(self) -> str | None:
        return self.accessTokenSource

    @api_key_source.setter
    def api_key_source(self, value: str | None) -> None:
        self.accessTokenSource = value

    @classmethod
    def from_json(cls, path: str | Path) -> "AuthData":
        import json

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        access_token = None
        for key in ("accessToken", "access_token", "api_key"):
            value = payload.get(key)
            if isinstance(value, str):
                value = value.strip()
            if value:
                access_token = value
                break
        return cls(
            accessToken=access_token,
            cookies=payload.get("cookies") or {},
            headers=payload.get("headers") or {},
            expires=payload.get("expires"),
            proof_token=payload.get("proof_token"),
            turnstile_token=payload.get("turnstile_token"),
        )


@dataclass
class ChatConversation:
    conversation_id: str | None = None
    message_id: str | None = None
    user_id: str | None = None
    finish_reason: str | None = None
    parent_message_id: str | None = None
    is_thinking: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ChatConversation":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            conversation_id=payload.get("conversation_id"),
            message_id=payload.get("message_id"),
            user_id=payload.get("user_id"),
            finish_reason=payload.get("finish_reason"),
            parent_message_id=payload.get("parent_message_id"),
            is_thinking=bool(payload.get("is_thinking", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "finish_reason": self.finish_reason,
            "parent_message_id": self.parent_message_id,
            "is_thinking": self.is_thinking,
        }


@dataclass(frozen=True)
class ConversationRef:
    conversation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_id, str):
            raise TypeError("conversation_id must be a string")
        conversation_id = self.conversation_id.strip()
        if not conversation_id:
            raise ValueError("conversation_id is required")
        if any(separator in conversation_id for separator in ("/", "?", "#")):
            raise ValueError("conversation_id must be a raw id, not a URL")
        object.__setattr__(self, "conversation_id", conversation_id)

    @classmethod
    def from_any(
        cls,
        value: "ConversationRef | ChatConversation | dict[str, Any] | str",
    ) -> "ConversationRef":
        if isinstance(value, cls):
            return value
        if isinstance(value, ChatConversation):
            return cls._from_optional_id(
                value.conversation_id,
                "conversation.conversation_id is required",
            )
        if isinstance(value, dict):
            return cls._from_optional_id(
                value.get("conversation_id"),
                "conversation_id is required",
            )
        if isinstance(value, str):
            return cls._from_string(value)
        raise TypeError(
            "conversation reference must be a raw id, ChatGPT conversation URL, "
            "ChatConversation, dict, or ConversationRef"
        )

    @classmethod
    def _from_optional_id(cls, value: Any, error_message: str) -> "ConversationRef":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(error_message)
        return cls(value)

    @classmethod
    def _from_string(cls, value: str) -> "ConversationRef":
        raw_value = value.strip()
        if not raw_value:
            raise ValueError("conversation_id is required")

        parsed = urlparse(raw_value)
        if parsed.scheme or parsed.netloc:
            return cls(cls._conversation_id_from_url(raw_value))
        return cls(raw_value)

    @staticmethod
    def _conversation_id_from_url(value: str) -> str:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("conversation URL must use http or https")
        if hostname not in {"chatgpt.com", "chat.openai.com"}:
            raise ValueError("conversation URL host is not supported")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2 or parts[0] != "c":
            raise ValueError("conversation URL must have /c/<conversation_id> path")
        return parts[1]


@dataclass
class AttachedConversation:
    conversation: ChatConversation
    current_node: str | None = None
    detected_model: str | None = None
    detected_reasoning_effort: str | None = None
    title: str | None = None
    raw_status: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.conversation, ChatConversation):
            raise TypeError("conversation must be a ChatConversation")
        ref = ConversationRef.from_any(self.conversation)
        conversation_dict = self.conversation.to_dict()
        conversation_dict["conversation_id"] = ref.conversation_id
        self.conversation = ChatConversation.from_dict(conversation_dict)
        self.current_node = _optional_str(self.current_node)
        self.detected_model = _optional_str(self.detected_model)
        self.detected_reasoning_effort = _optional_str(self.detected_reasoning_effort)
        self.title = _optional_str(self.title)
        if self.raw_status is None:
            self.raw_status = {}
        elif not isinstance(self.raw_status, dict):
            raise TypeError("raw_status must be a dict")
        else:
            self.raw_status = dict(self.raw_status)

    @property
    def conversation_id(self) -> str:
        ref = ConversationRef.from_any(self.conversation)
        return ref.conversation_id

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        conversation: ChatConversation | None = None,
        detected_model: str | None = None,
        detected_reasoning_effort: str | None = None,
        title: str | None = None,
        raw_status: dict[str, Any] | None = None,
    ) -> "AttachedConversation":
        if not isinstance(payload, dict):
            raise TypeError("conversation payload must be a dict")

        payload_conversation_id = _optional_str(payload.get("conversation_id"))
        conversation_id = (
            _optional_str(conversation.conversation_id)
            if conversation is not None
            else None
        )
        if (
            conversation_id
            and payload_conversation_id
            and conversation_id != payload_conversation_id
        ):
            raise ValueError(
                "conversation.conversation_id does not match payload.conversation_id"
            )

        if conversation is None:
            conversation = ChatConversation(conversation_id=payload_conversation_id)
        elif not conversation_id and payload_conversation_id:
            conversation_dict = conversation.to_dict()
            conversation_dict["conversation_id"] = payload_conversation_id
            conversation = ChatConversation.from_dict(conversation_dict)

        return cls(
            conversation=conversation,
            current_node=_optional_str(payload.get("current_node")),
            detected_model=detected_model,
            detected_reasoning_effort=detected_reasoning_effort,
            title=title if title is not None else _optional_str(payload.get("title")),
            raw_status=raw_status
            if raw_status is not None
            else cls._lightweight_status_from_payload(payload),
        )

    @staticmethod
    def _lightweight_status_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "async_status",
            "create_time",
            "update_time",
            "is_archived",
            "is_starred",
        )
        return {key: payload[key] for key in keys if key in payload}

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation": self.conversation.to_dict(),
            "conversation_id": self.conversation_id,
            "current_node": self.current_node,
            "detected_model": self.detected_model,
            "detected_reasoning_effort": self.detected_reasoning_effort,
            "title": self.title,
            "raw_status": dict(self.raw_status),
        }


@dataclass
class ConversationStatus:
    status: ConversationStatusValue = "unknown"
    node_id: str | None = None
    message_id: str | None = None
    role: str | None = None
    recipient: str | None = None
    async_status: str | None = None
    finish_reason: str | None = None
    pending_approval: bool = False
    metadata_preview: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = _optional_str(self.status)
        if status not in CONVERSATION_STATUS_VALUES:
            raise ValueError(f"unsupported conversation status: {self.status!r}")
        self.status = status
        self.node_id = _optional_str(self.node_id)
        self.message_id = _optional_str(self.message_id)
        self.role = _optional_str(self.role)
        self.recipient = _optional_str(self.recipient)
        self.async_status = _optional_str(self.async_status)
        self.finish_reason = _optional_str(self.finish_reason)
        self.pending_approval = bool(self.pending_approval)

        if self.metadata_preview is None:
            self.metadata_preview = {}
        elif not isinstance(self.metadata_preview, dict):
            raise TypeError("metadata_preview must be a dict")
        else:
            self.metadata_preview = copy.deepcopy(self.metadata_preview)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ConversationStatus":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            status=payload.get("status", "unknown"),
            node_id=payload.get("node_id"),
            message_id=payload.get("message_id"),
            role=payload.get("role"),
            recipient=payload.get("recipient"),
            async_status=payload.get("async_status"),
            finish_reason=payload.get("finish_reason"),
            pending_approval=payload.get("pending_approval", False),
            metadata_preview=payload.get("metadata_preview"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "node_id": self.node_id,
            "message_id": self.message_id,
            "role": self.role,
            "recipient": self.recipient,
            "async_status": self.async_status,
            "finish_reason": self.finish_reason,
            "pending_approval": self.pending_approval,
            "metadata_preview": copy.deepcopy(self.metadata_preview),
        }


@dataclass(frozen=True)
class PendingApproval:
    tool_message_id: str
    target_message_id: str
    recipient: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tool_message_id",
            _required_str(self.tool_message_id, "tool_message_id"),
        )
        object.__setattr__(
            self,
            "target_message_id",
            _required_str(self.target_message_id, "target_message_id"),
        )
        object.__setattr__(self, "recipient", _required_str(self.recipient, "recipient"))

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PendingApproval | None":
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                tool_message_id=payload.get("tool_message_id"),
                target_message_id=payload.get("target_message_id"),
                recipient=payload.get("recipient"),
            )
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_message_id": self.tool_message_id,
            "target_message_id": self.target_message_id,
            "recipient": self.recipient,
        }


@dataclass
class ChatMessage:
    node_id: str | None = None
    message_id: str | None = None
    role: str | None = None
    text: str = ""
    create_time: float | None = None
    recipient: str | None = None
    model: str | None = None
    finish_reason: str | None = None
    metadata_preview: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.node_id = _optional_str(self.node_id)
        self.message_id = _optional_str(self.message_id)
        self.role = _optional_str(self.role)
        self.text = "" if self.text is None else str(self.text)
        self.recipient = _optional_str(self.recipient)
        self.model = _optional_str(self.model)
        self.finish_reason = _optional_str(self.finish_reason)

        if self.create_time is not None:
            try:
                self.create_time = float(self.create_time)
            except (TypeError, ValueError):
                self.create_time = None

        if self.metadata_preview is None:
            self.metadata_preview = {}
        elif not isinstance(self.metadata_preview, dict):
            raise TypeError("metadata_preview must be a dict")
        else:
            self.metadata_preview = copy.deepcopy(self.metadata_preview)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ChatMessage":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            node_id=payload.get("node_id"),
            message_id=payload.get("message_id"),
            role=payload.get("role"),
            text=payload.get("text"),
            create_time=payload.get("create_time"),
            recipient=payload.get("recipient"),
            model=payload.get("model"),
            finish_reason=payload.get("finish_reason"),
            metadata_preview=payload.get("metadata_preview"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "message_id": self.message_id,
            "role": self.role,
            "text": self.text,
            "create_time": self.create_time,
            "recipient": self.recipient,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "metadata_preview": copy.deepcopy(self.metadata_preview),
        }


@dataclass
class WaitResult:
    status: ConversationStatus
    message: ChatMessage | None = None
    approval: PendingApproval | None = None
    elapsed: float = 0.0
    polls: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, ConversationStatus):
            raise TypeError("status must be a ConversationStatus")
        if self.message is not None and not isinstance(self.message, ChatMessage):
            raise TypeError("message must be a ChatMessage or None")
        if self.approval is not None and not isinstance(self.approval, PendingApproval):
            raise TypeError("approval must be a PendingApproval or None")

        try:
            self.elapsed = float(self.elapsed)
        except (TypeError, ValueError):
            self.elapsed = 0.0
        if self.elapsed < 0:
            self.elapsed = 0.0

        try:
            self.polls = int(self.polls)
        except (TypeError, ValueError):
            self.polls = 0
        if self.polls < 0:
            self.polls = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "WaitResult":
        if not isinstance(payload, dict):
            return cls(status=ConversationStatus())
        message_payload = payload.get("message")
        return cls(
            status=ConversationStatus.from_dict(payload.get("status")),
            message=ChatMessage.from_dict(message_payload)
            if isinstance(message_payload, dict)
            else None,
            approval=PendingApproval.from_dict(payload.get("approval")),
            elapsed=payload.get("elapsed", 0.0),
            polls=payload.get("polls", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.to_dict(),
            "message": self.message.to_dict() if self.message is not None else None,
            "approval": self.approval.to_dict() if self.approval is not None else None,
            "elapsed": self.elapsed,
            "polls": self.polls,
        }


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


@dataclass
class ChatRequestDiagnostics:
    requested_model: str | None = None
    requested_reasoning_effort: str | None = None
    sent_model: str | None = None
    sent_reasoning_effort: str | None = None
    conversation_id: str | None = None
    parent_message_id: str | None = None
    is_continuation: bool = False
    web_search: bool = False
    temporary: bool = False
    has_media: bool = False
    message_count: int | None = None
    observed_model: str | None = None
    observed_reasoning_effort: str | None = None
    resume_kind: str | None = None
    resume_token_present: bool = False
    resume_turn_topic_id: str | None = None
    resume_with_websockets: bool = False
    turn_exchange_id: str | None = None

    def __post_init__(self) -> None:
        self.requested_model = _optional_str(self.requested_model)
        self.requested_reasoning_effort = _optional_str(self.requested_reasoning_effort)
        self.sent_model = _optional_str(self.sent_model)
        self.sent_reasoning_effort = _optional_str(self.sent_reasoning_effort)
        self.conversation_id = _optional_str(self.conversation_id)
        self.parent_message_id = _optional_str(self.parent_message_id)
        self.is_continuation = bool(self.is_continuation)
        self.web_search = bool(self.web_search)
        self.temporary = bool(self.temporary)
        self.has_media = bool(self.has_media)
        self.message_count = _optional_positive_int(self.message_count)
        self.observed_model = _optional_str(self.observed_model)
        self.observed_reasoning_effort = _optional_str(self.observed_reasoning_effort)
        self.resume_kind = _optional_str(self.resume_kind)
        self.resume_token_present = bool(self.resume_token_present)
        self.resume_turn_topic_id = _optional_str(self.resume_turn_topic_id)
        self.resume_with_websockets = bool(self.resume_with_websockets)
        self.turn_exchange_id = _optional_str(self.turn_exchange_id)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ChatRequestDiagnostics":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            requested_model=payload.get("requested_model"),
            requested_reasoning_effort=payload.get("requested_reasoning_effort"),
            sent_model=payload.get("sent_model"),
            sent_reasoning_effort=payload.get("sent_reasoning_effort"),
            conversation_id=payload.get("conversation_id"),
            parent_message_id=payload.get("parent_message_id"),
            is_continuation=payload.get("is_continuation", False),
            web_search=payload.get("web_search", False),
            temporary=payload.get("temporary", False),
            has_media=payload.get("has_media", False),
            message_count=payload.get("message_count"),
            observed_model=payload.get("observed_model"),
            observed_reasoning_effort=payload.get("observed_reasoning_effort"),
            resume_kind=payload.get("resume_kind"),
            resume_token_present=payload.get("resume_token_present", False),
            resume_turn_topic_id=payload.get("resume_turn_topic_id"),
            resume_with_websockets=payload.get("resume_with_websockets", False),
            turn_exchange_id=payload.get("turn_exchange_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_model": self.requested_model,
            "requested_reasoning_effort": self.requested_reasoning_effort,
            "sent_model": self.sent_model,
            "sent_reasoning_effort": self.sent_reasoning_effort,
            "conversation_id": self.conversation_id,
            "parent_message_id": self.parent_message_id,
            "is_continuation": self.is_continuation,
            "web_search": self.web_search,
            "temporary": self.temporary,
            "has_media": self.has_media,
            "message_count": self.message_count,
            "observed_model": self.observed_model,
            "observed_reasoning_effort": self.observed_reasoning_effort,
            "resume_kind": self.resume_kind,
            "resume_token_present": self.resume_token_present,
            "resume_turn_topic_id": self.resume_turn_topic_id,
            "resume_with_websockets": self.resume_with_websockets,
            "turn_exchange_id": self.turn_exchange_id,
        }


@dataclass
class ChatResponse:
    text: str
    title: str | None = None
    conversation: ChatConversation = field(default_factory=ChatConversation)
    metrics: ChatMetrics = field(default_factory=ChatMetrics)
    request: ChatRequestDiagnostics = field(default_factory=ChatRequestDiagnostics)
