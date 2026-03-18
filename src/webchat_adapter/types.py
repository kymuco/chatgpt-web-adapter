from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MediaSource = bytes | bytearray | str | Path | os.PathLike[str]
MediaItem = MediaSource | tuple[MediaSource, str | None]


@dataclass
class AuthData:
    api_key: str | None = None
    api_key_source: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    expires: int | None = None
    proof_token: Any = None
    turnstile_token: str | None = None

    @classmethod
    def from_json(cls, path: str | Path) -> "AuthData":
        import json

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            api_key=payload.get("api_key"),
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


@dataclass
class ChatMetrics:
    first_token: float | None = None
    last_token: float | None = None
    total: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ChatMetrics":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            first_token=payload.get("first_token"),
            last_token=payload.get("last_token"),
            total=payload.get("total"),
        )


@dataclass
class ChatResponse:
    text: str
    title: str | None = None
    conversation: ChatConversation = field(default_factory=ChatConversation)
    metrics: ChatMetrics = field(default_factory=ChatMetrics)
