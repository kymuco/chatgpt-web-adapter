// PR14.8: retained per-conversation background tabs for saved conversations.
//
// Normal saved conversations no longer have to share the single legacy runtime tab.
// Each conversation may retain one background ChatGPT tab, keyed only by its exact
// conversation id. Fresh/new-chat routing and Temporary Chat keep their existing
// authority/lifecycle paths.
//
// This layer owns routing only. It does not type, submit, retry, canonically read,
// infer conversation identity, or change Temporary Chat semantics.

const PR148_CONVERSATION_TAB_POOL_KEY = "browserNativeConversationTabsV1";
const PR148_CONVERSATION_TAB_POOL_MAX = 16;
const _pr148PriorEnsureRuntimeTab = ensureRuntimeTab;

let _pr148PoolMutation = Promise.resolve();

function _pr148ConversationId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (
    !conversationId ||
    conversationId.includes("/") ||
    conversationId.includes("?") ||
    conversationId.includes("#")
  ) {
    return null;
  }
  return conversationId;
}

function _pr148NormalizePool(value) {
  if (!Array.isArray(value)) return [];
  const entries = [];
  const conversations = new Set();
  const tabs = new Set();
  for (const item of value) {
    const conversationId = _pr148ConversationId(item?.conversationId);
    const tabId = Number.isInteger(item?.tabId) ? item.tabId : null;
    if (conversationId === null || tabId === null) continue;
    if (conversations.has(conversationId) || tabs.has(tabId)) continue;
    conversations.add(conversationId);
    tabs.add(tabId);
    entries.push({ conversationId, tabId });
  }
  return entries.slice(0, PR148_CONVERSATION_TAB_POOL_MAX);
}

async function _pr148ReadPoolDirect() {
  const stored = await chrome.storage.local.get(PR148_CONVERSATION_TAB_POOL_KEY);
  return _pr148NormalizePool(stored?.[PR148_CONVERSATION_TAB_POOL_KEY]);
}

async function _pr148WritePoolDirect(entries) {
  await chrome.storage.local.set({
    [PR148_CONVERSATION_TAB_POOL_KEY]: _pr148NormalizePool(entries)
  });
}

async function _pr148ReadPool() {
  await _pr148PoolMutation;
  return _pr148ReadPoolDirect();
}

async function _pr148MutatePool(mutator) {
  const run = _pr148PoolMutation.then(async () => {
    const current = await _pr148ReadPoolDirect();
    const next = await mutator(current.slice());
    const normalized = _pr148NormalizePool(next);
    await _pr148WritePoolDirect(normalized);
    return normalized;
  });
  _pr148PoolMutation = run.catch(() => {});
  return run;
}

async function _pr148PruneStalePoolBindings() {
  return _pr148MutatePool(async (entries) => {
    const live = [];
    for (const entry of entries) {
      try {
        const tab = await chrome.tabs.get(entry.tabId);
        if (
          isChatGPTUrl(tab?.url || "") &&
          conversationIdFromUrl(tab?.url || "") === entry.conversationId
        ) {
          live.push(entry);
        }
      } catch {
        // Closed/missing tabs are stale retained state.
      }
    }
    return live;
  });
}

async function _pr148RemoveConversationBinding(conversationId) {
  await _pr148MutatePool((entries) =>
    entries.filter((entry) => entry.conversationId !== conversationId)
  );
}

async function _pr148RemoveTabBinding(tabId) {
  await _pr148MutatePool((entries) =>
    entries.filter((entry) => entry.tabId !== tabId)
  );
}

async function _pr148BindConversationTab(conversationId, tabId) {
  if (_pr148ConversationId(conversationId) === null) {
    throw new Error("PR14_8_CONVERSATION_ID_REQUIRED");
  }
  if (!Number.isInteger(tabId)) {
    throw new Error("PR14_8_TAB_ID_REQUIRED");
  }

  await _pr148PruneStalePoolBindings();
  await _pr148MutatePool((entries) => {
    const withoutTarget = entries.filter(
      (entry) =>
        entry.conversationId !== conversationId &&
        entry.tabId !== tabId
    );
    if (withoutTarget.length >= PR148_CONVERSATION_TAB_POOL_MAX) {
      throw new Error("PR14_8_CONVERSATION_TAB_POOL_LIMIT_REACHED");
    }
    return [...withoutTarget, { conversationId, tabId }];
  });
}

async function _pr148BoundConversationTab(conversationId) {
  const entries = await _pr148ReadPool();
  const binding = entries.find(
    (entry) => entry.conversationId === conversationId
  );
  if (!binding) return null;

  try {
    const tab = await chrome.tabs.get(binding.tabId);
    if (
      isChatGPTUrl(tab?.url || "") &&
      conversationIdFromUrl(tab?.url || "") === conversationId
    ) {
      return tab;
    }
  } catch {
    // Missing Chrome tab is stale retained state.
  }

  await _pr148RemoveConversationBinding(conversationId);
  return null;
}

async function _pr148LegacyRuntimeTabForConversation(conversationId) {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) return null;

  const entries = await _pr148ReadPool();
  const otherBinding = entries.find(
    (entry) =>
      entry.tabId === storedId &&
      entry.conversationId !== conversationId
  );
  if (otherBinding) return null;

  try {
    const tab = await chrome.tabs.get(storedId);
    if (
      isChatGPTUrl(tab?.url || "") &&
      conversationIdFromUrl(tab?.url || "") === conversationId
    ) {
      return tab;
    }
  } catch {
    return null;
  }
  return null;
}

async function _pr148DetachLegacyPointerIfConversationBound() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) return false;

  const entries = await _pr148ReadPool();
  if (!entries.some((entry) => entry.tabId === storedId)) return false;

  await chrome.storage.local.remove(RUNTIME_TAB_KEY);
  postNative({
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "runtime_state",
    runtimeTabId: null
  });
  return true;
}

async function _pr148CreateConversationTab(conversationId) {
  const targetUrl = `${CHATGPT_ORIGIN}/c/${encodeURIComponent(conversationId)}`;
  let tab = await chrome.tabs.create({ url: targetUrl, active: false });
  if (!Number.isInteger(tab?.id)) {
    throw new Error("PR14_8_CONVERSATION_TAB_CREATE_FAILED");
  }

  const tabId = tab.id;
  try {
    tab = await waitForTabComplete(tabId);
    if (
      !isChatGPTUrl(tab?.url || "") ||
      conversationIdFromUrl(tab?.url || "") !== conversationId
    ) {
      throw new Error("PR14_8_CONVERSATION_TAB_ROUTE_MISMATCH");
    }
    await _pr148BindConversationTab(conversationId, tabId);
    return tab;
  } catch (error) {
    try {
      await chrome.tabs.remove(tabId);
    } catch {
      // Best-effort cleanup of a tab created by this failed acquisition.
    }
    throw error;
  }
}

ensureRuntimeTab = async function _pr148EnsureRetainedConversationTab(conversationId) {
  // Temporary Chat owns a separate process-local lifecycle/tab authority. Never
  // route it through the saved-conversation pool.
  if (
    typeof _pr813TemporaryTurnContext !== "undefined" &&
    _pr813TemporaryTurnContext !== null
  ) {
    return _pr148PriorEnsureRuntimeTab(conversationId);
  }

  const savedConversationId = _pr148ConversationId(conversationId);
  if (savedConversationId === null) {
    // A fresh normal chat must not repurpose a tab that is now retained for an
    // existing saved conversation, even if that tab still occupies the historical
    // single-runtime storage slot.
    await _pr148DetachLegacyPointerIfConversationBound();
    return _pr148PriorEnsureRuntimeTab(conversationId);
  }

  const retained = await _pr148BoundConversationTab(savedConversationId);
  if (retained) return retained;

  // Adopt the historical runtime tab when it is already on the exact requested
  // conversation. This upgrades an existing live session without opening a
  // duplicate tab on the first PR14.8 turn.
  const legacy = await _pr148LegacyRuntimeTabForConversation(savedConversationId);
  if (legacy) {
    await _pr148BindConversationTab(savedConversationId, legacy.id);
    return legacy;
  }

  return _pr148CreateConversationTab(savedConversationId);
};

chrome.tabs.onRemoved.addListener((tabId) => {
  _pr148RemoveTabBinding(tabId).catch(() => {});
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (typeof changeInfo?.url !== "string") return;
  _pr148ReadPool().then((entries) => {
    const binding = entries.find((entry) => entry.tabId === tabId);
    if (!binding) return;
    if (conversationIdFromUrl(changeInfo.url) === binding.conversationId) return;
    _pr148RemoveTabBinding(tabId).catch(() => {});
  }).catch(() => {});
});

chrome.tabs.onReplaced.addListener((addedTabId, removedTabId) => {
  _pr148ReadPool().then(async (entries) => {
    const binding = entries.find((entry) => entry.tabId === removedTabId);
    if (!binding) return;

    let replacement = null;
    try {
      replacement = await chrome.tabs.get(addedTabId);
    } catch {
      replacement = null;
    }

    if (
      replacement &&
      isChatGPTUrl(replacement?.url || "") &&
      conversationIdFromUrl(replacement?.url || "") === binding.conversationId
    ) {
      await _pr148MutatePool((current) => [
        ...current.filter(
          (entry) =>
            entry.tabId !== removedTabId &&
            entry.tabId !== addedTabId &&
            entry.conversationId !== binding.conversationId
        ),
        { conversationId: binding.conversationId, tabId: addedTabId }
      ]);
      return;
    }

    await _pr148RemoveTabBinding(removedTabId);
  }).catch(() => {});
});
