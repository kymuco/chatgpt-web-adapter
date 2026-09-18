from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
POOL = EXT / "service_worker_retained_conversation_tabs_pr14_8.js"
WRITE = EXT / "service_worker_runtime_write.js"


def test_pr14_8_is_assembled_before_rich_input_wrappers() -> None:
    write = WRITE.read_text(encoding="utf-8")
    retained = 'importScripts("service_worker_retained_conversation_tabs_pr14_8.js");'
    rich = 'importScripts("service_worker_rich_input_pr9_2.js");'

    assert retained in write
    assert rich in write
    assert write.index(retained) < write.index(rich)


def test_pr14_8_routes_saved_conversations_to_retained_background_tabs() -> None:
    source = POOL.read_text(encoding="utf-8")

    for token in (
        'const PR148_CONVERSATION_TAB_POOL_KEY = "browserNativeConversationTabsV1"',
        "const PR148_CONVERSATION_TAB_POOL_MAX = 16",
        "const _pr148PriorEnsureRuntimeTab = ensureRuntimeTab",
        "ensureRuntimeTab = async function _pr148EnsureRetainedConversationTab",
        "chrome.tabs.create({ url: targetUrl, active: false })",
        "conversationIdFromUrl(tab?.url || \"\") === conversationId",
        "_pr148BindConversationTab(savedConversationId, legacy.id)",
        "await _pr148PruneStalePoolBindings()",
        "PR14_8_CONVERSATION_TAB_POOL_LIMIT_REACHED",
        "return _pr148CreateConversationTab(savedConversationId)",
    ):
        assert token in source


def test_pr14_8_never_repurposes_retained_saved_tab_for_fresh_chat() -> None:
    source = POOL.read_text(encoding="utf-8")

    assert "await _pr148DetachLegacyPointerIfConversationBound()" in source
    assert "chrome.storage.local.remove(RUNTIME_TAB_KEY)" in source
    assert "return _pr148PriorEnsureRuntimeTab(conversationId)" in source
    assert "chrome.tabs.update(" not in source


def test_pr14_8_preserves_temporary_chat_lifecycle_authority() -> None:
    source = POOL.read_text(encoding="utf-8")

    temporary_guard = source.index(
        'typeof _pr813TemporaryTurnContext !== "undefined"'
    )
    saved_parse = source.index(
        "const savedConversationId = _pr148ConversationId(conversationId)"
    )
    delegate = source.index(
        "return _pr148PriorEnsureRuntimeTab(conversationId)",
        temporary_guard,
    )

    assert temporary_guard < delegate < saved_parse
    assert "temporaryLifecycleToken" not in source
    assert "history_and_training_disabled" not in source


def test_pr14_8_cleans_stale_or_retargeted_pool_bindings() -> None:
    source = POOL.read_text(encoding="utf-8")

    assert "chrome.tabs.onRemoved.addListener" in source
    assert "chrome.tabs.onUpdated.addListener" in source
    assert "chrome.tabs.onReplaced.addListener" in source
    assert "_pr148RemoveConversationBinding(conversationId)" in source
    assert "_pr148RemoveTabBinding(tabId)" in source


def test_pr14_8_is_routing_only_and_adds_no_product_write_or_retry_path() -> None:
    source = POOL.read_text(encoding="utf-8")

    for forbidden in (
        "executeOfficialPageTurn(",
        "submitOfficialPageTurn(",
        "Input.insertText",
        "Input.dispatchMouseEvent",
        "fetch(",
        "XMLHttpRequest",
        "get_messages",
        "get_status",
    ):
        assert forbidden not in source

    lowered = source.lower()
    assert "retry" in lowered  # scope comment states that this layer does not retry.
    assert "chrome.tabs.create" in source
    assert "chrome.tabs.remove" in source
