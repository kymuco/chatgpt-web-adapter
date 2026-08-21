from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def test_session_identity_overlays_load_after_temporary_production_layer() -> None:
    source = _source("service_worker_observability.js")
    production = 'importScripts("service_worker_temporary_chat_production_pr8_13.js");'
    identity = 'importScripts("service_worker_temporary_session_identity_pr8_13.js");'
    flush = 'importScripts("service_worker_temporary_fresh_identity_flush_pr8_13.js");'
    assert production in source
    assert identity in source
    assert flush in source
    assert source.index(production) < source.index(identity) < source.index(flush)


def test_session_identity_uses_only_bounded_live_sse_envelope_metadata() -> None:
    source = _source("service_worker_temporary_session_identity_pr8_13.js")
    assert "value.conversation_id ?? value.conversationId" in source
    assert "value.turn_exchange_id ?? value.turnExchangeId" in source
    assert '["payload", "data", "result", "turn"]' in source
    assert "Do not recursively inspect arbitrary tool" in source
    assert "Network.getResponseBody" not in source
    assert "backend-api/conversation" not in source
    assert "chrome.tabs.update" not in source
    assert "/c/" not in source


def test_temporary_id_is_explicitly_session_routing_not_public_authority() -> None:
    source = _source("service_worker_temporary_session_identity_pr8_13.js")
    assert "session-local routing metadata only" in source
    assert "never grants continuation authority" in source


def test_continuation_stream_identity_must_match_live_session_identity() -> None:
    source = _source("service_worker_temporary_session_identity_pr8_13.js")
    assert "temporaryContext.expectedConversationId !== null" in source
    assert "identity.conversationId !== temporaryContext.expectedConversationId" in source
    assert "TEMPORARY_STREAM_IDENTITY_CONVERSATION_MISMATCH" in source


def test_missing_base_turn_identity_can_be_filled_before_native_turn_returns() -> None:
    source = _source("service_worker_temporary_session_identity_pr8_13.js")
    assert "_pr813SessionIdentityPriorExecuteOfficialPageTurn" in source
    assert "temporaryContext.ephemeralConversationId" in source
    assert "conversationId," in source
    assert "turnExchangeId," in source


def test_fresh_temporary_identity_flush_uses_extension_local_sentinel_only() -> None:
    source = _source("service_worker_temporary_fresh_identity_flush_pr8_13.js")
    assert "PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL" in source
    assert "_pr813ConversationIdWithFreshIdentitySentinel" in source
    assert "conversationId: PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL" in source
    assert "LIVE_SSE_STREAM" in source
    assert "TEMPORARY_SESSION_ROUTING_IDENTITY_MISSING_AFTER_STREAM_FLUSH" in source
    assert "Network.getResponseBody" not in source
    assert "Fetch.continueRequest" not in source
    assert "backend-api/conversation" not in source
    assert "chrome.tabs.update" not in source
    assert "/c/" not in source


def test_fresh_identity_sentinel_resolves_only_from_live_temporary_context() -> None:
    source = _source("service_worker_temporary_fresh_identity_flush_pr8_13.js")
    assert "_pr813TemporaryTurnContext" in source
    assert "ephemeralConversationId" in source
    assert "_pr813LiveTemporaryLifecycle" in source
    assert "conversationId: resolvedConversationId" in source
