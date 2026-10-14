"""Experimental direct HTTPS transport for chat.qwen.ai.

The web protocol is private and may change. No implicit retries of generation.
Credentials are always caller supplied or loaded from the separate Qwen store.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .types import ChatConversation, ChatResponse

QWEN_ORIGIN = "https://chat.qwen.ai"


class QwenHttpError(RuntimeError):
    """Direct Qwen API failure; never includes bearer or cookie values."""


class QwenHttpWriteOutcomeAmbiguousError(QwenHttpError):
    reconciliation_required = True
    automatic_retry_allowed = False


@dataclass(repr=False)
class QwenHttpCredentials:
    access_token: str = field(repr=False)
    cookies: dict[str, str] = field(default_factory=dict, repr=False)
    expires_at: float | None = None

    def __post_init__(self) -> None:
        self.access_token = self.access_token.removeprefix("Bearer ").strip()
        if not self.access_token:
            raise ValueError("Qwen access token required")
        if any(
            not isinstance(k, str)
            or not isinstance(v, str)
            or any(c in k + v for c in "\r\n;")
            for k, v in self.cookies.items()
        ):
            raise ValueError("Invalid Qwen cookies")


@dataclass(frozen=True)
class QwenHttpConversation:
    chat_id: str
    parent_id: str | None = None


class QwenHttpClient:
    """Direct HTTPS client with a caller-controlled conversation and session.

    The opener is injectable for deterministic tests. No browser/extension is used
    during send_text. No silent fallback into a browser is allowed.
    """

    def __init__(
        self,
        credentials: QwenHttpCredentials,
        *,
        model: str = "qwen-max-latest",
        timeout: float = 180.0,
        opener: Callable[..., Any] = urlopen,
        refresh_path: str | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if refresh_path is not None and (
            not refresh_path.startswith("/api/")
            or "//" in refresh_path
            or "?" in refresh_path
        ):
            raise ValueError("refresh_path must be an absolute Qwen API path")
        self.credentials = credentials
        self.model = model
        self.timeout = timeout
        self._open = opener
        self.refresh_path = refresh_path
        self.conversation: QwenHttpConversation | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": "Bearer " + self.credentials.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Origin": QWEN_ORIGIN,
            "Referer": QWEN_ORIGIN + "/",
            "User-Agent": "Mozilla/5.0 QwenDirectExperimental/1.0",
        }
        if self.credentials.cookies:
            headers["Cookie"] = "; ".join(
                name + "=" + value for name, value in self.credentials.cookies.items()
            )
        return headers

    def _record_cookies(self, response: Any) -> None:
        headers = getattr(response, "headers", None)
        values = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
        for value in values or []:
            jar = SimpleCookie()
            try:
                jar.load(value)
            except Exception:
                continue
            for name, item in jar.items():
                self.credentials.cookies[name] = item.value

    def _request(
        self, method: str, path: str, *, payload: Any = None, stream: bool = False
    ) -> Any:
        if not path.startswith("/api/") or "//" in path:
            raise ValueError("Only Qwen API paths are supported")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            QWEN_ORIGIN + path, data=data, headers=self._headers(), method=method
        )
        try:
            response = self._open(request, timeout=self.timeout)
        except HTTPError as error:
            # A definitive 401 is not an authorization to replay a mutation.
            raise QwenHttpError(
                f"QWEN_HTTP_{error.code}: {method} {path.split('?')[0]}"
            ) from None
        except (URLError, TimeoutError, OSError) as error:
            if method == "POST" and "completions" in path:
                raise QwenHttpWriteOutcomeAmbiguousError(
                    "QWEN_HTTP_GENERATION_DELIVERY_UNCERTAIN"
                ) from error
            raise QwenHttpError(f"QWEN_HTTP_TRANSPORT_ERROR: {method}") from error
        self._record_cookies(response)
        return response

    def refresh(self) -> None:
        """Pre-send renewal only; requires a separately verified refresh path."""
        if not self.refresh_path or not self.credentials.cookies:
            raise QwenHttpError("QWEN_REFRESH_UNAVAILABLE_REIMPORT_BROWSER_SESSION")
        with self._request("GET", self.refresh_path) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise QwenHttpError("QWEN_REFRESH_INVALID_RESPONSE")
        data = payload.get("data", payload)
        token = (
            data.get("access_token", data.get("token"))
            if isinstance(data, dict)
            else None
        )
        if not isinstance(token, str) or not token:
            raise QwenHttpError("QWEN_REFRESH_TOKEN_MISSING")
        self.credentials.access_token = token.removeprefix("Bearer ")
        self.credentials.expires_at = None

    def _preflight_auth(self) -> None:
        expiry = self.credentials.expires_at
        if expiry is not None and expiry <= time.time() + 60:
            self.refresh()

    def create_chat(self, *, model: str | None = None) -> QwenHttpConversation:
        self._preflight_auth()
        selected = model or self.model
        payload = {
            "title": "Qwen Direct",
            "models": [selected],
            "chat_mode": "normal",
            "chat_type": "t2t",
            "timestamp": int(time.time() * 1000),
            "project_id": "",
        }
        with self._request("POST", "/api/v2/chats/new", payload=payload) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise QwenHttpError("QWEN_NEW_CHAT_INVALID_RESPONSE")
        data = body.get("data", body)
        chat_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(chat_id, str) or not chat_id:
            raise QwenHttpError("QWEN_NEW_CHAT_ID_MISSING")
        self.conversation = QwenHttpConversation(chat_id=chat_id)
        return self.conversation

    @staticmethod
    def _payload(text: str, model: str, state: QwenHttpConversation) -> dict[str, Any]:
        timestamp = int(time.time())
        return {
            "stream": True,
            "version": "2.1",
            "incremental_output": True,
            "chat_id": state.chat_id,
            "chat_mode": "normal",
            "model": model,
            "parent_id": state.parent_id,
            "timestamp": timestamp,
            "messages": [
                {
                    "fid": str(uuid.uuid4()),
                    "parentId": state.parent_id,
                    "parent_id": state.parent_id,
                    "childrenIds": [],
                    "role": "user",
                    "content": text,
                    "user_action": "chat",
                    "files": [],
                    "timestamp": timestamp,
                    "models": [model],
                    "chat_type": "t2t",
                    "sub_chat_type": "t2t",
                    "feature_config": {
                        "thinking_enabled": False,
                        "thinking_budget": 0,
                        "output_schema": None,
                    },
                    "extra": {"meta": {"subChatType": "t2t"}},
                }
            ],
        }

    def send_text(
        self,
        text: str,
        *,
        conversation: QwenHttpConversation | None = None,
        model: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> ChatResponse:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 200_000:
            raise ValueError("text too large")
        selected = model or self.model
        self._preflight_auth()
        state = conversation or self.conversation or self.create_chat(model=selected)
        path = "/api/v2/chat/completions?" + urlencode({"chat_id": state.chat_id})
        chunks: list[str] = []
        parent_id: str | None = None
        finished = False
        # One and only one completion POST. On interrupted stream, never replay.
        try:
            with self._request(
                "POST", path, payload=self._payload(text, selected, state), stream=True
            ) as response:
                for line in response:
                    raw = (
                        line.decode("utf-8", "replace")
                        if isinstance(line, bytes)
                        else line
                    )
                    if not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        finished = True
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    created = event.get("response.created")
                    if isinstance(created, dict):
                        maybe_parent = created.get("response_id")
                        if isinstance(maybe_parent, str) and maybe_parent:
                            parent_id = maybe_parent
                    choices = event.get("choices")
                    if (
                        not isinstance(choices, list)
                        or not choices
                        or not isinstance(choices[0], dict)
                    ):
                        continue
                    choice = choices[0]
                    delta = choice.get("delta")
                    chunk = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(chunk, str) and chunk:
                        chunks.append(chunk)
                        if on_token is not None:
                            on_token(chunk)
                    if choice.get("finish_reason") in {"stop", "length"}:
                        finished = True
        except QwenHttpError:
            raise
        except (OSError, ValueError) as error:
            raise QwenHttpWriteOutcomeAmbiguousError(
                "QWEN_HTTP_RESPONSE_INCOMPLETE"
            ) from error
        if not finished or not chunks:
            raise QwenHttpWriteOutcomeAmbiguousError("QWEN_HTTP_FINALITY_NOT_PROVEN")
        self.conversation = QwenHttpConversation(state.chat_id, parent_id)
        return ChatResponse(
            text="".join(chunks),
            conversation=ChatConversation(conversation_id=state.chat_id),
        )
