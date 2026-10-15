from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from chatgpt_web_adapter import qwen_client as module
from chatgpt_web_adapter.qwen_http import (
    QwenHttpConversation,
    QwenHttpCredentials,
    QwenHttpVerificationRequiredError,
)


def test_session_import_preserves_conversation_and_credentials(monkeypatch):
    credentials = QwenHttpCredentials(
        "fresh", {"session": "secret"}, headers={"user-agent": "Chrome"}
    )
    monkeypatch.setattr(
        module,
        "QwenBrowserTurnProvider",
        lambda: SimpleNamespace(export_auth=lambda: credentials),
    )
    save = Mock()
    monkeypatch.setattr(module, "save_qwen_credentials", save)
    client = module.QwenClient(transport="http", browser_session_refresh=True)
    state = QwenHttpConversation("chat", "parent")
    client._http = SimpleNamespace(conversation=state)
    client.refresh_browser_auth()
    assert client._http.conversation == state
    assert client._http.credentials is credentials
    save.assert_called_once_with(credentials)


def test_generation_verification_does_not_trigger_refresh_or_resend(monkeypatch):
    client = module.QwenClient(transport="http", browser_session_refresh=True)
    client._last_browser_auth_import = module.time.monotonic()
    send = Mock(side_effect=QwenHttpVerificationRequiredError("verification"))
    client._http = SimpleNamespace(
        credentials=QwenHttpCredentials("example"), send_text=send
    )
    refresh = Mock()
    monkeypatch.setattr(client, "refresh_browser_auth", refresh)
    with pytest.raises(QwenHttpVerificationRequiredError):
        client.send_text("message")
    send.assert_called_once()
    refresh.assert_not_called()


def test_strict_http_never_imports_browser(monkeypatch):
    client = module.QwenClient(transport="http")
    client._http = SimpleNamespace(send_text=Mock(return_value="reply"))
    refresh = Mock()
    monkeypatch.setattr(client, "refresh_browser_auth", refresh)
    assert client.send_text("message") == "reply"
    refresh.assert_not_called()
