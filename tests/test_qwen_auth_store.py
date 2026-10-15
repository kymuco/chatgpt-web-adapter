from __future__ import annotations

import os
from pathlib import Path

import pytest

from chatgpt_web_adapter.qwen_auth_store import (
    QwenAuthStoreError,
    load_qwen_credentials,
    save_qwen_credentials,
)
from chatgpt_web_adapter.qwen_client import QwenClient
from chatgpt_web_adapter.qwen_http import QwenHttpCredentials


def test_store_roundtrip_outside_repo(tmp_path: Path):
    target = tmp_path / "auth.dat"
    first = QwenHttpCredentials("secret-token", {"session": "secret-cookie"}, 99999)
    save_qwen_credentials(first, path=target)
    assert b"secret-token" not in target.read_bytes() if os.name == "nt" else True
    second = load_qwen_credentials(path=target)
    assert second.access_token == first.access_token
    assert second.cookies == first.cookies
    if os.name != "nt":
        assert (target.stat().st_mode & 0o777) == 0o600


def test_store_rejects_corruption(tmp_path: Path):
    file = tmp_path / "auth.dat"
    file.write_bytes(b"not credentials")
    with pytest.raises(QwenAuthStoreError):
        load_qwen_credentials(path=file)


def test_client_explicit_transport_and_rejects_cross_transport_conversation():
    assert QwenClient(transport="http").transport == "http"
    assert QwenClient(transport="browser").transport == "browser"
    with pytest.raises(ValueError):
        QwenClient(transport="other")
    with pytest.raises(ValueError, match="QwenHttpConversation"):
        QwenClient(transport="http").send_text("x", conversation="browser-opaque-id")


def test_browser_model_fails_before_write():
    client = QwenClient(transport="browser")
    with pytest.raises(ValueError):
        client.send_text("x", model="any")
