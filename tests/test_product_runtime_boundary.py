from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chatgpt_web_adapter"


def test_product_runtime_has_no_legacy_direct_write_fallback() -> None:
    source = (SRC / "product_runtime.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_PRODUCT_TRANSPORTS: tuple[str, ...] = (BROWSER_OWNED_PRODUCT_TRANSPORT,)' in source
    assert '"fallback_transport": None' in source
    assert '"legacy_direct_write_fallback": False' in source
    assert "self.client.send(" not in source
    assert "send_to_conversation(" not in source
    assert "send_payload(" not in source
    assert "CHAT_BACKEND_URL" not in source
    assert "proof_token" not in source.lower()
    assert "turnstile" not in source.lower()


def test_product_runtime_assembly_is_noninteractive_and_non_sentinel() -> None:
    source = (SRC / "product_runtime.py").read_text(encoding="utf-8")
    assert "auto_login=False" in source
    assert "auto_sentinel=False" in source
    assert "auto_refresh_auth=auto_refresh_auth" in source
    assert "BrowserOwnedProductWriteRuntime" in source


def test_cli_uses_same_product_runtime_assembly_contract() -> None:
    source = (SRC / "cli.py").read_text(encoding="utf-8")
    assert 'commands.add_parser(\n        "runtime"' in source
    assert 'runtime_commands.add_parser(\n        "status"' in source
    assert 'runtime_commands.add_parser(\n        "send"' in source
    assert "assemble_product_runtime(" in source
    assert "runtime.send_text_observed(" in source
