"""Two explicitly selected transports for the same Qwen Web product."""

from __future__ import annotations

from typing import Any, Callable, Literal

from .qwen_auth_store import load_qwen_credentials, save_qwen_credentials
from .qwen_http import QwenHttpClient, QwenHttpConversation
from .qwen_web import QwenBrowserTurnProvider, QwenWebTransport
from .types import ChatResponse


class QwenClient:
    """Choose browser or direct HTTP without implicit fallback.

    HTTP may outlive Chrome once imported credentials remain valid.
    Browser session import happens only when import_browser_auth() is invoked.
    """

    def __init__(
        self,
        *,
        transport: Literal["browser", "http"] = "browser",
        model: str = "qwen-max-latest",
        refresh_path: str | None = None,
    ) -> None:
        if transport not in {"browser", "http"}:
            raise ValueError("transport must be browser or http")
        self.transport = transport
        self.model = model
        self.refresh_path = refresh_path
        self._browser: QwenWebTransport | None = None
        self._http: QwenHttpClient | None = None

    def import_browser_auth(self) -> None:
        """Explicit local opt-in; requires Chrome with an authenticated Qwen tab."""
        credentials = QwenBrowserTurnProvider().export_auth()
        save_qwen_credentials(credentials)
        self._http = QwenHttpClient(
            credentials,
            model=self.model,
            refresh_path=self.refresh_path,
            on_auth_updated=save_qwen_credentials,
        )

    def _http_client(self) -> QwenHttpClient:
        if self._http is None:
            self._http = QwenHttpClient(
                load_qwen_credentials(),
                model=self.model,
                refresh_path=self.refresh_path,
                on_auth_updated=save_qwen_credentials,
            )
        return self._http

    def send_text(
        self,
        text: str,
        *,
        conversation: Any = None,
        model: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> ChatResponse:
        if self.transport == "http":
            if conversation is not None and not isinstance(
                conversation, QwenHttpConversation
            ):
                raise ValueError(
                    "Direct HTTP requires QwenHttpConversation(chat_id, parent_id)"
                )
            return self._http_client().send_text(
                text,
                conversation=conversation,
                model=model,
                on_token=on_token,
            )
        if model is not None or on_token is not None:
            raise ValueError(
                "Browser provider does not support model selection or token streaming"
            )
        if self._browser is None:
            self._browser = QwenWebTransport()
        return self._browser.send_text(text, conversation=conversation)
