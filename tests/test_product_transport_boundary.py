from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chatgpt_web_adapter"


def test_product_transport_protocol_has_no_browser_or_sentinel_dependency() -> None:
    source = (SRC / "product_transport.py").read_text(encoding="utf-8")

    for forbidden in (
        "browser_native",
        "browser_owned",
        "BrowserNative",
        "BrowserOwned",
        "Sentinel",
        "turnstile",
        "proof_token",
        "chrome.",
        "runtime_tab_id is required",
    ):
        assert forbidden not in source


def test_product_runtime_does_not_import_concrete_browser_writer_contract() -> None:
    source = (SRC / "product_runtime.py").read_text(encoding="utf-8")

    assert "BrowserOwnedProductWriteRuntime" not in source
    assert "BrowserNativeTurnProvider" not in source
    assert "from .browser_owned_write_runtime" not in source
    assert "from .browser_native_provider" not in source
    assert "ProductWriteTransport" in source
    assert "CanonicalConversationClient" in source


def test_browser_owned_transport_is_adapter_not_transport_reimplementation() -> None:
    source = (SRC / "browser_owned_product_transport.py").read_text(encoding="utf-8")

    assert "BrowserOwnedProductWriteRuntime" in source
    assert "self._runtime.send_text(" in source
    assert "self._runtime.send_text_observed(" in source
    for forbidden in (
        "send_browser_native(",
        "set_browser_native_turn_provider(",
        "Input.dispatchKeyEvent",
        "Input.dispatchMouseEvent",
        "chat-requirements",
        "turnstile",
        "proof_token",
    ):
        assert forbidden not in source


def test_pr84_does_not_modify_legacy_client_or_browser_owned_writer_contract() -> None:
    # These files are intentionally guarded by source ownership tests elsewhere.
    # PR8.4 adds an interface seam around them; it must not require edits to
    # either implementation to make transport injection work.
    runtime = (SRC / "browser_owned_write_runtime.py").read_text(encoding="utf-8")
    client = (SRC / "client.py").read_text(encoding="utf-8")

    assert "class BrowserOwnedProductWriteRuntime" in runtime
    assert "class ChatGPTWebClient" in client
