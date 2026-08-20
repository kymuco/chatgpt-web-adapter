from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
PRODUCTION = EXTENSION / "service_worker_temporary_chat_production_pr8_13.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"


def _source() -> str:
    return PRODUCTION.read_text(encoding="utf-8")


def test_pr813_layer_loads_after_pr812_stream_and_answer_channel() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")
    activity = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    channel = 'importScripts("service_worker_answer_channel_pr8_12.js");'
    temporary = 'importScripts("service_worker_temporary_chat_production_pr8_13.js");'
    assert activity in source and channel in source and temporary in source
    assert source.index(activity) < source.index(channel) < source.index(temporary)


def test_temporary_write_is_paused_before_network_dispatch_for_mode_proof() -> None:
    source = _source()
    assert '"Fetch.enable"' in source
    assert 'requestStage: "Request"' in source
    assert 'method !== "Fetch.requestPaused"' in source
    assert "request.postData" in source
    assert "JSON.parse(request.postData)" in source
    assert "history_and_training_disabled !== true" in source
    assert 'proofKind: "FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE"' in source


def test_unproven_or_wrong_identity_temporary_request_is_aborted_not_downgraded() -> None:
    source = _source()
    assert '"Fetch.failRequest"' in source
    assert 'errorReason: "Aborted"' in source
    assert 'reason: "HISTORY_AND_TRAINING_DISABLED_NOT_TRUE"' in source
    assert 'reason: "FRESH_TEMPORARY_REQUEST_HAS_CONVERSATION_ID"' in source
    assert 'reason: "TEMPORARY_CONTINUATION_CONVERSATION_MISMATCH"' in source
    assert "payloadConversationId !== context.expectedConversationId" in source
    assert '"Fetch.continueRequest"' in source
    assert "if (inspection.proven !== true)" in source
    assert "_pr813RejectProof(" in source
    assert "_pr813ResolveProof(context, inspection.evidence)" in source


def test_request_body_is_browser_local_proof_only_and_never_rewritten() -> None:
    source = _source()
    # The layer reads the page-generated request body only inside the worker and
    # never supplies postData to continueRequest or a public turn_result field.
    assert "request.postData" in source
    assert "postData:" not in source
    assert "requestPostData" not in source
    assert "Fetch.continueRequest" in source
    assert "Fetch.fulfillRequest" not in source
    assert "Fetch.continueWithAuth" not in source
    assert "Network.setExtraHTTPHeaders" not in source


def test_fresh_temporary_lifecycle_gets_dedicated_inactive_tab_and_private_token() -> None:
    source = _source()
    assert "browserNativeTemporaryRuntimeTabIdV1" in source
    assert "?temporary-chat=true" in source
    assert "active: false" in source
    assert "temporaryLifecycleToken" in source
    assert "_pr813LiveTemporaryLifecycle" in source
    assert 'state: "LIVE"' in source
    assert 'throw new Error("PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE")' in source
    assert "live.conversationId !== expectedConversationId" in source
    assert "live.token !== token" in source
    assert "live.tabId" in source


def test_tab_or_worker_recreation_cannot_restore_temporary_write_authority() -> None:
    source = _source()
    # Stored tab id exists only for cleanup. No code reconstructs the module-live
    # lifecycle from storage.
    assert "_pr813StoredTemporaryTabId" in source
    assert "_pr813LiveTemporaryLifecycle = null" in source
    assert "_pr813RetireOwnedTemporaryTab" in source
    forbidden_rehydration = (
        "temporaryLifecycleTokenV1",
        "temporaryLifecycleConversationIdV1",
        "chrome.storage.local.set({ temporaryLifecycle",
    )
    for marker in forbidden_rehydration:
        assert marker not in source


def test_explicit_end_closes_owned_tab_and_revokes_live_authority() -> None:
    source = _source()
    assert "endTemporaryLifecycle" in source
    assert 'live.state = "ENDED"' in source
    assert "_pr813LiveTemporaryLifecycle = null" in source
    assert "await _pr813CloseTemporaryTab(tabId)" in source
    assert "await _pr813ClearStoredTemporaryTabId(tabId)" in source
    assert 'temporaryLifecycleState: "ENDED"' in source
    assert "temporaryLiveWriteAuthorityProven: false" in source


def test_normal_mode_delegates_to_existing_production_chain() -> None:
    source = _source()
    assert "const _pr813PriorExecuteNativeTurn = executeNativeTurn;" in source
    assert 'if (mode !== "temporary") return _pr813PriorExecuteNativeTurn(message);' in source
    assert "const _pr813PriorEnsureRuntimeTab = ensureRuntimeTab;" in source
    assert "if (context === null) return _pr813PriorEnsureRuntimeTab(conversationId);" in source


def test_pr813_adds_no_retry_or_second_product_write_path() -> None:
    source = _source()
    assert "automatic_retry" not in source.lower()
    assert "retry" not in source.lower()
    assert source.count("_pr813PriorExecuteNativeTurn({") == 1
    assert "fetch(" not in source.lower()
    assert "XMLHttpRequest" not in source
