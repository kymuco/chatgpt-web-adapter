from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MediaSource = bytes | bytearray | str | Path | os.PathLike[str]
MediaItem = MediaSource | tuple[MediaSource, str | None]


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
