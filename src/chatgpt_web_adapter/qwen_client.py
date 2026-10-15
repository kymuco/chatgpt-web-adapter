"""Two explicitly selected transports for the same Qwen Web product."""

from __future__ import annotations

import time
from typing import Any, Callable, Literal

from .qwen_auth_store import load_qwen_credentials, save_qwen_credentials
from .qwen_http import QwenHttpClient, QwenHttpConversation
from .qwen_web import QwenBrowserTurnProvider, QwenWebTransport
from .types import ChatResponse


class QwenClient:
    """Choose browser or direct HTTP without implicit fallback.

    HTTP may outlive Chrome once imported credentials remain valid.
    Browser session import is explicit, or opt-in before sends via
    browser_session_refresh=True.
    """

    def __init__(
        self,
        *,
        transport: Literal["browser", "http"] = "browser",
        model: str = "qwen3.7-plus",
        refresh_path: str | None = None,
        browser_session_refresh: bool = False,
        session_refresh_interval: float = 300.0,
        auto_confirm_age: bool = False,
        birth_year: int = 2000,
        foreground_tab: bool = False,
    ) -> None:
        if transport not in {"browser", "http"}:
            raise ValueError("transport must be browser or http")
        if session_refresh_interval <= 0:
            raise ValueError("session_refresh_interval must be positive")
        if (
            isinstance(birth_year, bool)
            or not isinstance(birth_year, int)
            or not 1900 <= birth_year <= time.localtime().tm_year
        ):
            raise ValueError("birth_year must be a valid year")
        if not isinstance(foreground_tab, bool):
            raise ValueError("foreground_tab must be a bool")
        self.foreground_tab = foreground_tab
        self.auto_confirm_age = auto_confirm_age
        self.birth_year = birth_year
        self.browser_session_refresh = browser_session_refresh
        self.session_refresh_interval = session_refresh_interval
        self._last_browser_auth_import = None
        self.transport = transport
        self.model = model
        self.refresh_path = refresh_path
        self._browser: QwenWebTransport | None = None
        self._http: QwenHttpClient | None = None

    def import_browser_auth(self) -> None:
        """Explicit local opt-in; requires Chrome with an authenticated Qwen tab."""
        credentials = QwenBrowserTurnProvider().export_auth()
        previous_conversation = self._http.conversation if self._http else None
        save_qwen_credentials(credentials)
        self._http = QwenHttpClient(
            credentials,
            model=self.model,
            refresh_path=self.refresh_path,
            on_auth_updated=save_qwen_credentials,
        )

        self._http.conversation = previous_conversation
        self._last_browser_auth_import = time.monotonic()

    def refresh_browser_auth(self) -> None:
        """Refresh the local snapshot from an existing Qwen tab; never sends a prompt."""
        self.import_browser_auth()

    def _prepare_http_session(self) -> None:
        if not self.browser_session_refresh:
            return
        expired = (
            self._http is not None
            and self._http.credentials.expires_at is not None
            and self._http.credentials.expires_at <= time.time() + 60
        )
        due = (
            self._last_browser_auth_import is None
            or time.monotonic() - self._last_browser_auth_import
            >= self.session_refresh_interval
        )
        if expired or due:
            self.refresh_browser_auth()

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
        on_text: Callable[[str], None] | None = None,
    ) -> ChatResponse:
        if self.transport == "http":
            if on_text is not None:
                raise ValueError(
                    "on_text snapshots are supported only by browser transport"
                )
            self._prepare_http_session()
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
        if model is not None:
            raise ValueError("Browser provider does not support model selection")
        if self._browser is None:
            self._browser = QwenWebTransport()
        return self._browser.send_text(
            text,
            conversation=conversation,
            on_text=on_text,
            on_token=on_token,
            auto_confirm_age=self.auto_confirm_age,
            birth_year=self.birth_year,
            foreground_tab=self.foreground_tab,
        )
