from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BASE = EXT / "service_worker.js"
WRITE = EXT / "service_worker_runtime_write.js"
PROVIDER = EXT / "service_worker_deepseek_web_provider.js"
MANIFEST = EXT / "manifest.json"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_manifest_allows_only_explicit_deepseek_web_origin() -> None:
    manifest = json.loads(_source(MANIFEST))

    assert "https://chat.deepseek.com/*" in manifest["host_permissions"]
    assert not any("api.deepseek.com" in value for value in manifest["host_permissions"])


def test_provider_dispatch_precedes_chatgpt_diagnostics_and_observers() -> None:
    source = _source(BASE)
    start = source.index("async function dispatchNativeTurn(message)")
    end = source.index("\nfunction sleep(", start)
    block = source[start:end]

    assert "await dispatchProductProviderTurn(message)" in block
    assert block.index("await dispatchProductProviderTurn(message)") < block.index(
        "const matching = []"
    )
    assert "registerProductProviderTurnHandler" in source
    assert 'rawProviderId === "chatgpt"' in source


def test_deepseek_provider_is_assembled_outside_chatgpt_lifecycle() -> None:
    write = _source(WRITE)
    provider = _source(PROVIDER)

    assert 'importScripts("service_worker_deepseek_web_provider.js");' in write
    assert "registerProductProviderTurnHandler(" in provider
    assert "executeNativeTurn(" not in provider
    assert "CWA_NATIVE_TURN_LAYERS" not in provider
    assert "CHATGPT_ORIGIN" not in provider
    assert "/backend-api" not in provider


def test_deepseek_provider_uses_page_dom_not_private_http_api() -> None:
    provider = _source(PROVIDER)

    assert "https://chat.deepseek.com" in provider
    assert "textarea#chat-input" in provider
    assert ".ds-markdown.ds-assistant-message-main-content" in provider
    assert "stable_assistant_dom" in provider
    assert "DEEPSEEK_WEB_STABLE_FINALITY_MS = 9_000" in provider
    assert "fetch(" not in provider
    assert "XMLHttpRequest" not in provider
    assert "api.deepseek.com" not in provider


def test_deepseek_continuation_uses_exact_stored_url_not_route_schema() -> None:
    provider = _source(PROVIDER)

    assert "DEEPSEEK_WEB_CONVERSATION_URLS_KEY" in provider
    assert "_deepseekWebStoreConversationUrl" in provider
    assert "_deepseekWebTargetUrl" in provider
    assert "/a/chat/s/" not in provider
    assert "crypto.randomUUID()" in provider


def test_deepseek_provider_never_retries_after_submit() -> None:
    provider = _source(PROVIDER)

    assert provider.count("_deepseekWebSubmit(debuggee)") == 1
    assert "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED" in provider
    assert "retry" not in provider.lower()
