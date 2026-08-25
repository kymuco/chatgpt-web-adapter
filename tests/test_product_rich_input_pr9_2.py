from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_native_client import send_browser_native
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider
from chatgpt_web_adapter.product_media import (
    browser_owned_media_scope,
    current_browser_owned_attachment_paths,
)
from chatgpt_web_adapter.product_runtime import (
    ChatGPTProductRuntime,
    ProductRichInputUnavailableError,
)
from chatgpt_web_adapter.product_transport import (
    BROWSERLESS_REQUEST_PRODUCT_TRANSPORT,
    BROWSER_OWNED_PRODUCT_TRANSPORT,
)
from chatgpt_web_adapter.types import ChatConversation


class _CanonicalClient:
    def get_status(self, conversation):
        return object()

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return object()


class _ScopeAwareWriteTransport:
    def __init__(self, transport_id: str, *, temporary_supported: bool = False) -> None:
        self.transport_id = transport_id
        self.temporary_supported = temporary_supported
        self.send_calls = 0
        self.paths_seen: tuple[str, ...] | None = None

    def health(self, conversation=None):
        return object()

    def capabilities(self):
        return object()

    def governance(self):
        return {
            "temporary_chat_product_runtime_selection_supported": self.temporary_supported,
        }

    def send_text(self, text, **kwargs):
        self.send_calls += 1
        self.paths_seen = current_browser_owned_attachment_paths()
        if self.paths_seen:
            assert all(Path(path).is_file() for path in self.paths_seen)
        return "sent"

    def send_text_observed(self, text, **kwargs):
        raise AssertionError("not used by this focused test")


class _CapturingProvider(BrowserNativeTurnProvider):
    def __init__(self) -> None:
        super().__init__()
        self.payload = None

    def _rpc(self, payload, *, timeout, on_event=None):
        self.payload = dict(payload)
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": "conversation-1",
            "responseStatus": 200,
            "attachmentCount": len(payload.get("attachmentPaths") or []),
        }


class _LegacyTurnProvider:
    def send_text(self, text, *, conversation=None, timeout=None):
        return SimpleNamespace(
            conversation_id="conversation-legacy",
            turn_exchange_id="exchange-legacy",
            response_status=200,
            elapsed_ms=1,
            runtime_reloaded=False,
            runtime_reload_ms=None,
            tab_id=7,
            runtime_tab_preexisting=True,
            runtime_tab_created_for_turn=False,
            tab_was_active=False,
            tab_active_after=False,
            tab_activated_during_turn=False,
            foreground_activation_observed=False,
        )


class _LegacyBrowserNativeClient:
    def __init__(self) -> None:
        self._browser_native_turn_provider = _LegacyTurnProvider()

    def _emit_event(self, callback, event_type, **payload):
        if callback is not None:
            callback({"type": event_type, **payload})

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", message_id="assistant-legacy")

    def get_messages(self, conversation, **kwargs):
        return [
            SimpleNamespace(
                message_id="assistant-legacy",
                role="assistant",
                text="legacy-ok",
                finish_reason="stop",
                model="legacy-model",
            )
        ]

    def attach_conversation(self, conversation):
        return SimpleNamespace(
            title="Legacy",
            conversation=ChatConversation(
                conversation_id="conversation-legacy",
                message_id="assistant-legacy",
                parent_message_id="assistant-legacy",
                finish_reason="stop",
                is_thinking=False,
            ),
        )


def test_browser_owned_media_scope_materializes_bytes_without_bridge_payload(tmp_path):
    existing = tmp_path / "notes.txt"
    existing.write_text("hello", encoding="utf-8")

    assert current_browser_owned_attachment_paths() is None
    with browser_owned_media_scope(
        [existing, (b"\x89PNG\r\n", "image/png")]
    ) as materialization:
        assert materialization.count == 2
        assert materialization.materialized_byte_inputs == 1
        assert current_browser_owned_attachment_paths() == materialization.paths
        assert Path(materialization.paths[0]) == existing.resolve()
        generated = Path(materialization.paths[1])
        assert generated.suffix == ".png"
        assert generated.read_bytes() == b"\x89PNG\r\n"
    assert current_browser_owned_attachment_paths() is None
    assert not generated.exists()


def test_browser_owned_media_scope_rejects_nested_authority(tmp_path):
    media = tmp_path / "a.txt"
    media.write_text("a", encoding="utf-8")
    with browser_owned_media_scope([media]):
        with pytest.raises(RuntimeError, match="nested browser-owned media scopes"):
            with browser_owned_media_scope([media]):
                pass


def test_product_runtime_binds_media_only_during_browser_owned_normal_turn(tmp_path):
    media = tmp_path / "input.txt"
    media.write_text("payload", encoding="utf-8")
    transport = _ScopeAwareWriteTransport(BROWSER_OWNED_PRODUCT_TRANSPORT)
    runtime = ChatGPTProductRuntime(
        _CanonicalClient(),
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        write_transport=transport,
    )

    assert runtime.send_text("describe", media=[media]) == "sent"
    assert transport.send_calls == 1
    assert transport.paths_seen == (str(media.resolve()),)
    assert current_browser_owned_attachment_paths() is None


def test_product_runtime_browserless_media_fails_before_transport_dispatch(tmp_path):
    media = tmp_path / "input.txt"
    media.write_text("payload", encoding="utf-8")
    transport = _ScopeAwareWriteTransport(BROWSERLESS_REQUEST_PRODUCT_TRANSPORT)
    runtime = ChatGPTProductRuntime(
        _CanonicalClient(),
        transport=BROWSERLESS_REQUEST_PRODUCT_TRANSPORT,
        write_transport=transport,
    )

    with pytest.raises(ProductRichInputUnavailableError) as caught:
        runtime.send_text("describe", media=[media])
    assert caught.value.to_dict()["write_may_have_been_submitted"] is False
    assert transport.send_calls == 0


def test_product_runtime_temporary_media_fails_before_transport_dispatch(tmp_path):
    media = tmp_path / "input.txt"
    media.write_text("payload", encoding="utf-8")
    transport = _ScopeAwareWriteTransport(
        BROWSER_OWNED_PRODUCT_TRANSPORT,
        temporary_supported=True,
    )
    runtime = ChatGPTProductRuntime(
        _CanonicalClient(),
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        write_transport=transport,
    )

    with pytest.raises(ProductRichInputUnavailableError):
        runtime.send_text("describe", media=[media], conversation_mode="temporary")
    assert transport.send_calls == 0


def test_text_only_runtime_does_not_create_media_scope():
    transport = _ScopeAwareWriteTransport(BROWSER_OWNED_PRODUCT_TRANSPORT)
    runtime = ChatGPTProductRuntime(
        _CanonicalClient(),
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        write_transport=transport,
    )

    assert runtime.send_text("hello") == "sent"
    assert transport.paths_seen is None


def test_browser_native_provider_sends_paths_not_file_bytes(tmp_path):
    source = tmp_path / "secret-name.txt"
    source.write_bytes(b"local-file-body")
    provider = _CapturingProvider()

    result = provider.send_text(
        "inspect",
        attachment_paths=[source],
    )

    assert result.attachment_count == 1
    assert provider.payload is not None
    assert provider.payload["attachmentPaths"] == [str(source.resolve())]
    encoded = json.dumps(provider.payload)
    assert "local-file-body" not in encoded


def test_browser_native_provider_rejects_missing_attachment_before_rpc(tmp_path):
    provider = _CapturingProvider()
    missing = tmp_path / "missing.txt"

    with pytest.raises(ValueError, match=r"attachment_paths\[0\] is unavailable"):
        provider.send_text("inspect", attachment_paths=[missing])
    assert provider.payload is None


def test_text_only_legacy_provider_result_need_not_expose_attachment_count():
    response = send_browser_native(_LegacyBrowserNativeClient(), "hello")
    assert response.text == "legacy-ok"
    assert response.conversation.conversation_id == "conversation-legacy"


def test_packaged_extension_layers_pr9_2_above_preserved_entrypoint():
    extension = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "chatgpt_web_adapter"
        / "browser_native_extension"
    )
    manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"

    entrypoint = (extension / manifest["background"]["service_worker"]).read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_rich_input_pr9_2.js")' in entrypoint

    overlay = (extension / "service_worker_rich_input_pr9_2.js").read_text(encoding="utf-8")
    assert "DOM.setFileInputFiles" in overlay
    assert "attachmentPaths" in overlay
    assert "attachmentCount" in overlay
    assert "base64" not in overlay.lower()
    assert "_pr92RichInputPriorExecuteNativeTurn(message)" in overlay