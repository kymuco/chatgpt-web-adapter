from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from chatgpt_web_adapter.browser_context_canonical import (
    BROWSER_CONTEXT_CANONICAL_READ_PLANE,
    BrowserContextCanonicalClient,
    BrowserContextCanonicalReadError,
    _CanonicalReadChunkCollector,
)
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _payload() -> dict:
    return {
        "conversation_id": "conversation-1",
        "title": "Browser canonical",
        "current_node": "assistant-node",
        "mapping": {
            "assistant-node": {
                "id": "assistant-node",
                "parent": None,
                "children": [],
                "message": {
                    "id": "assistant-1",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": ["done"]},
                    "metadata": {
                        "finish_details": {"type": "stop"},
                        "message_status": "finished_successfully",
                    },
                    "end_turn": True,
                },
            }
        },
    }


def test_chunk_collector_reassembles_exact_sha256_sealed_bytes() -> None:
    body = json.dumps(_payload(), separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()
    split = len(body) // 2
    parts = (body[:split], body[split:])
    collector = _CanonicalReadChunkCollector(request_id="request-1")

    for index, part in enumerate(parts):
        collector.add(
            {
                "request_id": "request-1",
                "chunkIndex": index,
                "chunkCount": 2,
                "totalBytes": len(body),
                "sha256": digest,
                "data": base64.b64encode(part).decode(),
            }
        )

    assert collector.finish(
        {
            "chunkCount": 2,
            "totalBytes": len(body),
            "sha256": digest,
        }
    ) == body


def test_chunk_collector_rejects_integrity_mismatch() -> None:
    body = b'{"ok":true}'
    digest = hashlib.sha256(body).hexdigest()
    collector = _CanonicalReadChunkCollector(request_id="request-1")
    collector.add(
        {
            "request_id": "request-1",
            "chunkIndex": 0,
            "chunkCount": 1,
            "totalBytes": len(body),
            "sha256": digest,
            "data": base64.b64encode(body).decode(),
        }
    )

    with pytest.raises(ValueError, match="CANONICAL_READ_FINAL_MANIFEST_MISMATCH"):
        collector.finish(
            {
                "chunkCount": 1,
                "totalBytes": len(body),
                "sha256": "0" * 64,
            }
        )


def test_canonical_error_exports_only_sanitized_metadata() -> None:
    error = BrowserContextCanonicalReadError(
        "<html>secret challenge body</html>",
        conversation_id="conversation-1",
        status_code=403,
        content_type="text/html; charset=utf-8",
    )

    payload = error.to_dict()
    assert error.reason_code == "CANONICAL_READ_FAILED"
    assert payload["status_code"] == 403
    assert payload["content_type"] == "text/html; charset=utf-8"
    assert "secret challenge" not in str(error)
    assert "secret challenge" not in json.dumps(payload)
    assert payload["body_preview"] is None


def test_current_provider_exposes_read_and_terminal_ack_contract() -> None:
    assert callable(getattr(BrowserNativeTurnProvider, "read_conversation", None))
    assert callable(getattr(BrowserNativeTurnProvider, "complete_canonical_readback", None))
    assert callable(getattr(BrowserNativeTurnProvider, "set_browser_authority_lease", None))
    assert callable(getattr(BrowserNativeTurnProvider, "clear_browser_authority_lease", None))


def test_browser_context_client_keeps_python_status_interpreter(tmp_path, monkeypatch) -> None:
    provider = BrowserNativeTurnProvider(state_dir=tmp_path)
    client = BrowserContextCanonicalClient(object(), provider)
    monkeypatch.setattr(client.transport, "read_conversation", lambda _conversation: _payload())

    status = client.get_status("conversation-1")

    assert status.status == "completed"
    assert status.message_id == "assistant-1"


class _Canonical:
    def get_status(self, conversation):
        raise AssertionError("not used during construction")

    def get_messages(self, conversation, **kwargs):
        raise AssertionError("not used during construction")

    def attach_conversation(self, conversation):
        raise AssertionError("not used during construction")


def test_default_browser_owned_transport_assembles_browser_context_read_plane() -> None:
    transport = BrowserOwnedProductTransport(_Canonical())

    assert isinstance(transport.canonical_client, BrowserContextCanonicalClient)
    assert transport.governance()["read_plane"] == BROWSER_CONTEXT_CANONICAL_READ_PLANE
    assert (
        transport.governance()["browser_authority_release_event"]
        == "browser_native_readback_completed"
    )


def test_custom_provider_without_readback_contract_fails_before_write() -> None:
    class _CustomProvider:
        def status(self):
            raise AssertionError("not used")

        def send_text(self, *args, **kwargs):
            raise AssertionError("write must not occur")

    with pytest.raises(TypeError, match="browser-read and lease-fencing provider methods"):
        BrowserOwnedProductTransport(_Canonical(), provider=_CustomProvider())


def test_extension_fetches_exact_bytes_without_exporting_browser_protection_state() -> None:
    source = (EXTENSION / "service_worker_canonical_read.js").read_text(encoding="utf-8")
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["background"]["service_worker"] == "service_worker_canonical_read.js"
    assert 'credentials: "include"' in source
    assert "response.arrayBuffer()" in source
    assert 'crypto.subtle.digest("SHA-256", bytes)' in source
    assert "CWA_CANONICAL_CHUNK_BASE64_CHARS = 600_000" in source
    assert 'response.status === 404' in source
    assert '"CANONICAL_READ_AUTHENTICATION_REQUIRED"' in source
    assert '"CANONICAL_READ_ACCESS_CHALLENGED"' in source
    assert "document.cookie" not in source
    assert "cf_clearance" not in source
    assert "_puid" not in source
    assert "set-cookie" not in source.lower()


def test_host_serializes_write_read_and_close_on_one_authority_lane() -> None:
    source = (
        ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py"
    ).read_text(encoding="utf-8")

    assert '"canonical_read"' in source
    assert '"canonical_read_complete"' in source
    assert '"release_runtime_tab"' in source
    assert "_authority_reserved_lease_id" in source
    assert "_reserve_authority_for_readback" in source
    assert "_complete_authority_reservation" in source
    assert 'message.get("type") in {"turn_event", "canonical_read_chunk"}' in source
