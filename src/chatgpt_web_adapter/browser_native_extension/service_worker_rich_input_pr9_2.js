// PR9.2 rich-input overlay.
//
// This file is imported by the existing final PR8.7 worker after that worker has
// assembled the full prior service-worker chain. Attachment bytes never cross
// Native Messaging. The Python side sends only validated local file paths. The
// overlay stages those paths only after PR8.11 stale-UI recovery has completed,
// then delegates the actual product turn to the previously-proven browser-owned
// chain. The official page therefore remains responsible for upload semantics,
// Sentinel/proof handling, request construction, and the protected write.

const _pr92RichInputPriorExecuteNativeTurn = executeNativeTurn;
const _pr92PriorMaybeRecoverStaleRuntimeUi = (
  typeof _pr811MaybeRecoverStaleRuntimeUi === "function"
    ? _pr811MaybeRecoverStaleRuntimeUi
    : null
);
const _pr92PriorReloadRuntimeTabAndWait = (
  typeof _pr811ReloadRuntimeTabAndWait === "function"
    ? _pr811ReloadRuntimeTabAndWait
    : null
);
const _pr92PriorWaitForTabComplete = (
  typeof waitForTabComplete === "function" ? waitForTabComplete : null
);
const _pr92PriorExecuteOfficialPageTurn = (
  typeof executeOfficialPageTurn === "function" ? executeOfficialPageTurn : null
);
const PR92_RICH_INPUT_SCHEMA = 1;
const PR92_MAX_ATTACHMENT_COUNT = 32;
const PR92_DIRTY_ATTACHMENT_STORAGE_KEY = "pr92DirtyAttachmentFenceV1";
const PR92_STALE_UI_RELOAD_TIMEOUT_CAP_MS = 45_000;
const PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE = Boolean(
  _pr92PriorMaybeRecoverStaleRuntimeUi &&
  _pr92PriorReloadRuntimeTabAndWait &&
  _pr92PriorWaitForTabComplete &&
  _pr92PriorExecuteOfficialPageTurn
);

let _pr92ActiveTurnContext = null;
let _pr92ActiveRichInputContext = null;
let _pr92DirtyAttachmentTabId = null;

function _pr92NormalizeAttachmentPaths(value) {
  if (value == null) return [];
  if (!Array.isArray(value)) throw new Error("PR9_2_ATTACHMENT_PATHS_ARRAY_REQUIRED");
  if (value.length > PR92_MAX_ATTACHMENT_COUNT) {
    throw new Error("PR9_2_ATTACHMENT_COUNT_EXCEEDED");
  }
  return value.map((item) => {
    if (typeof item !== "string" || !item.trim()) {
      throw new Error("PR9_2_ATTACHMENT_PATH_INVALID");
    }
    return item;
  });
}

function _pr92TurnTimeoutMs(message) {
  if (!Number.isFinite(message?.timeoutMs)) return DEFAULT_TIMEOUT_MS;
  const timeoutMs = Number(message.timeoutMs);
  if (timeoutMs <= 0) throw new Error("PR9_2_TURN_TIMEOUT_MUST_BE_POSITIVE");
  return Math.min(timeoutMs, 300_000);
}

function _pr92CreateTurnContext(message) {
  const timeoutMs = _pr92TurnTimeoutMs(message);
  const startedAt = performance.now();
  return {
    startedAt,
    timeoutMs,
    deadlineAt: startedAt + timeoutMs,
    attachmentPaths: [],
    staged: false,
    stagedTabId: null,
    attachmentCount: 0
  };
}

function _pr92RemainingTurnMs(context, stage) {
  const remaining = Math.ceil(context.deadlineAt - performance.now());
  if (!Number.isFinite(remaining) || remaining <= 0) {
    throw new Error(`PR9_2_TOTAL_TURN_TIMEOUT:${stage}`);
  }
  return remaining;
}

function _pr92RemainingTurnMsOrZero(context) {
  const remaining = Math.ceil(context.deadlineAt - performance.now());
  return Number.isFinite(remaining) && remaining > 0 ? remaining : 0;
}

function _pr92CapTimeoutToTurn(context, requestedMs, stage) {
  const remaining = _pr92RemainingTurnMs(context, stage);
  if (!Number.isFinite(requestedMs)) return remaining;
  return Math.max(1, Math.min(Number(requestedMs), remaining));
}

async function _pr92BoundedSleep(context, requestedMs, stage) {
  const duration = _pr92CapTimeoutToTurn(context, requestedMs, stage);
  await sleep(duration);
  _pr92RemainingTurnMs(context, stage);
}

// The prior worker chain contains waits which predate PR9.2 and therefore own
// their own local timeouts. While a PR9.2 turn is active, cap those waits to the
// single outer RPC deadline. Text-only turns outside this overlay context retain
// the exact prior behavior.
if (_pr92PriorWaitForTabComplete) {
  waitForTabComplete = async function _pr92WaitForTabCompleteWithinTurn(
    tabId,
    timeoutMs = 45_000
  ) {
    const context = _pr92ActiveTurnContext;
    if (context === null) {
      return _pr92PriorWaitForTabComplete(tabId, timeoutMs);
    }
    return _pr92PriorWaitForTabComplete(
      tabId,
      _pr92CapTimeoutToTurn(context, timeoutMs, "TAB_LOAD")
    );
  };
}

if (_pr92PriorExecuteOfficialPageTurn) {
  executeOfficialPageTurn = async function _pr92ExecuteOfficialPageTurnWithinTurn(args) {
    const context = _pr92ActiveTurnContext;
    if (context === null) return _pr92PriorExecuteOfficialPageTurn(args);
    return _pr92PriorExecuteOfficialPageTurn({
      ...args,
      timeoutMs: _pr92CapTimeoutToTurn(
        context,
        args?.timeoutMs,
        "PROTECTED_PAGE_DISPATCH"
      )
    });
  };
}

// PR8.11 stale-UI recovery has a fixed 45s reload timer. Reproduce that bounded
// reload under an active PR9.2 turn so recovery cannot consume a fresh timeout
// before attachment staging. No retry is introduced and a timeout occurs before
// attachment selection/write authority.
if (_pr92PriorReloadRuntimeTabAndWait) {
  _pr811ReloadRuntimeTabAndWait = async function _pr92ReloadRuntimeTabWithinTurn(
    tabId,
    expectedConversationId
  ) {
    const context = _pr92ActiveTurnContext;
    if (context === null) {
      return _pr92PriorReloadRuntimeTabAndWait(tabId, expectedConversationId);
    }

    const startedAt = performance.now();
    const reloadTimeoutMs = _pr92CapTimeoutToTurn(
      context,
      PR92_STALE_UI_RELOAD_TIMEOUT_CAP_MS,
      "STALE_UI_RELOAD"
    );
    await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error = null) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        if (error) reject(error);
        else resolve();
      };
      const timer = setTimeout(
        () => finish(new Error("CHATGPT_STALE_UI_RELOAD_TIMEOUT")),
        reloadTimeoutMs
      );
      function onUpdated(updatedTabId, changeInfo) {
        if (updatedTabId === tabId && changeInfo.status === "complete") finish();
      }
      chrome.tabs.onUpdated.addListener(onUpdated);
      chrome.tabs.reload(tabId).catch((error) => finish(error));
    });

    _pr92RemainingTurnMs(context, "STALE_UI_RELOAD_VERIFY");
    const reloadedTab = await chrome.tabs.get(tabId);
    _pr92RemainingTurnMs(context, "STALE_UI_RELOAD_VERIFY");
    const conversationId = conversationIdFromUrl(reloadedTab.url || "");
    if (conversationId !== expectedConversationId) {
      throw new Error("CHATGPT_STALE_UI_RELOAD_CONVERSATION_MISMATCH");
    }
    return Math.round(performance.now() - startedAt);
  };
}

async function _pr92ReadDirtyAttachmentFence() {
  try {
    const stored = await chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY);
    const record = stored?.[PR92_DIRTY_ATTACHMENT_STORAGE_KEY];
    const tabId = Number.isInteger(record?.tabId) ? record.tabId : null;
    _pr92DirtyAttachmentTabId = tabId;
    return tabId;
  } catch {
    // A storage read failure means we cannot prove that a previous worker did not
    // leave a staged file in the persistent composer. Fail closed before any turn.
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_READ_FAILED");
  }
}

async function _pr92PersistDirtyAttachmentFence(tabId) {
  if (!Number.isInteger(tabId)) {
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_TAB_REQUIRED");
  }
  try {
    // Persist BEFORE DOM.setFileInputFiles. A worker crash after the file selection
    // can therefore never erase the authority fence while the runtime tab survives.
    await chrome.storage.local.set({
      [PR92_DIRTY_ATTACHMENT_STORAGE_KEY]: {
        schema: 1,
        tabId
      }
    });
  } catch {
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_PERSIST_FAILED");
  }
  _pr92DirtyAttachmentTabId = tabId;
}

async function _pr92TryClearDirtyAttachmentFence() {
  try {
    await chrome.storage.local.remove(PR92_DIRTY_ATTACHMENT_STORAGE_KEY);
    _pr92DirtyAttachmentTabId = null;
    return true;
  } catch {
    // Retaining the fence is safe: the next turn will retry cleanup before write.
    return false;
  }
}

function _pr92FindFileInputExpression() {
  return `(() => {
    const seen = new Set();
    const visit = (root) => {
      if (!root || seen.has(root)) return null;
      seen.add(root);
      try {
        const direct = root.querySelector && root.querySelector('input[type="file"]');
        if (direct) return direct;
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element && element.shadowRoot) {
            const nested = visit(element.shadowRoot);
            if (nested) return nested;
          }
        }
      } catch {}
      return null;
    };
    return visit(document);
  })()`;
}

async function _pr92FindFileInputObjectId(debuggee) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr92FindFileInputExpression(),
    returnByValue: false,
    awaitPromise: true
  });
  const objectId = result?.result?.objectId;
  return typeof objectId === "string" && objectId ? objectId : null;
}

async function _pr92TryRevealFileInput(debuggee, context) {
  try {
    _pr92RemainingTurnMs(context, "REVEAL_FILE_INPUT");
    await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: `(() => {
        const selectors = [
          'button[data-testid="composer-plus-btn"]',
          'button[data-testid="composer-button-add-files"]',
          'button[aria-label*="Attach"]',
          'button[aria-label*="attach"]',
          'button[aria-label*="Upload"]',
          'button[aria-label*="Add files"]',
          'button[aria-label*="Прикреп"]'
        ];
        for (const selector of selectors) {
          const button = document.querySelector(selector);
          if (!button) continue;
          const rect = button.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) continue;
          button.click();
          return selector;
        }
        return null;
      })()`,
      returnByValue: true,
      awaitPromise: true
    });
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")) {
      throw error;
    }
    // The bounded hidden-input path is preferred; reveal is only a compatibility aid.
  }
  await _pr92BoundedSleep(context, 100, "REVEAL_FILE_INPUT_SETTLE");
}

async function _pr92StageOfficialPageAttachments(tabId, attachmentPaths, context) {
  if (attachmentPaths.length === 0) return 0;
  const debuggee = { tabId };
  const stageTimeoutMs = _pr92RemainingTurnMs(context, "ATTACHMENT_STAGE");
  const startedAt = performance.now();
  let attached = false;
  let objectId = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    _pr92RemainingTurnMs(context, "ATTACHMENT_STAGE");
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "DOM.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(
        remainingMs(startedAt, stageTimeoutMs, 1),
        _pr92RemainingTurnMs(context, "ATTACHMENT_STAGE_READY"),
        DEFAULT_READY_TIMEOUT_MS
      )
    );

    _pr92RemainingTurnMs(context, "ATTACHMENT_FILE_INPUT_LOOKUP");
    objectId = await _pr92FindFileInputObjectId(debuggee);
    if (!objectId) {
      await _pr92TryRevealFileInput(debuggee, context);
      objectId = await _pr92FindFileInputObjectId(debuggee);
    }
    if (!objectId) throw new Error("PR9_2_FILE_INPUT_NOT_FOUND");

    // The persistent fence is authoritative across Manifest V3 worker restarts.
    // It must exist before the browser is allowed to select any local file.
    _pr92RemainingTurnMs(context, "ATTACHMENT_FENCE_PERSIST");
    await _pr92PersistDirtyAttachmentFence(tabId);
    _pr92RemainingTurnMs(context, "ATTACHMENT_FILE_SELECTION");
    await chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
      files: attachmentPaths,
      objectId
    });
    await _pr92BoundedSleep(context, 100, "ATTACHMENT_SELECTION_SETTLE");
    return attachmentPaths.length;
  } catch (error) {
    if (error instanceof Error && error.message === "PR9_2_FILE_INPUT_NOT_FOUND") {
      throw error;
    }
    if (
      error instanceof Error &&
      (
        error.message.startsWith("PR9_2_STALE_ATTACHMENT_FENCE_") ||
        error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")
      )
    ) {
      throw error;
    }
    throw new Error("PR9_2_ATTACHMENT_STAGE_FAILED");
  } finally {
    if (objectId) {
      try {
        await chrome.debugger.sendCommand(debuggee, "Runtime.releaseObject", { objectId });
      } catch {}
    }
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _pr92ClearOfficialPageAttachments(tabId, timeoutMs) {
  if (!Number.isInteger(tabId) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return false;
  }
  try {
    await chrome.tabs.get(tabId);
  } catch {
    // A removed tab cannot retain a stale composer attachment.
    return true;
  }

  try {
    await waitForTabComplete(tabId, Math.max(1, Math.min(timeoutMs, 10_000)));
  } catch {
    return false;
  }

  const debuggee = { tabId };
  let attached = false;
  let objectId = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "DOM.enable");
    objectId = await _pr92FindFileInputObjectId(debuggee);
    if (!objectId) return false;
    await chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
      files: [],
      objectId
    });
    return true;
  } catch {
    return false;
  } finally {
    if (objectId) {
      try {
        await chrome.debugger.sendCommand(debuggee, "Runtime.releaseObject", { objectId });
      } catch {}
    }
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _pr92RequireCleanAttachmentState(context) {
  _pr92RemainingTurnMs(context, "STALE_ATTACHMENT_FENCE_READ");
  const dirtyTabId = await _pr92ReadDirtyAttachmentFence();
  if (!Number.isInteger(dirtyTabId)) return;

  const cleared = await _pr92ClearOfficialPageAttachments(
    dirtyTabId,
    _pr92RemainingTurnMs(context, "STALE_ATTACHMENT_CLEANUP")
  );
  if (!cleared) {
    throw new Error("PR9_2_STALE_ATTACHMENT_CLEANUP_REQUIRED");
  }
  _pr92RemainingTurnMs(context, "STALE_ATTACHMENT_FENCE_CLEAR");
  if (!await _pr92TryClearDirtyAttachmentFence()) {
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_CLEAR_FAILED");
  }
}

// Recovery is the last operation that is allowed to reload the runtime tab before
// the core page turn. Hook immediately after it rather than staging in the outer
// executeNativeTurn wrapper. This preserves PR8.11 recovery semantics while the
// active PR9.2 context makes recovery + staging + dispatch share one deadline.
if (_pr92PriorMaybeRecoverStaleRuntimeUi) {
  _pr811MaybeRecoverStaleRuntimeUi = async function _pr92RecoverThenStage(message) {
    const recovery = await _pr92PriorMaybeRecoverStaleRuntimeUi(message);
    const context = _pr92ActiveRichInputContext;
    if (context === null) return recovery;
    if (context.staged === true) {
      throw new Error("PR9_2_ATTACHMENT_STAGE_REENTRANCY");
    }

    _pr92RemainingTurnMs(context, "POST_RECOVERY");
    const conversationId = typeof message?.conversationId === "string" && message.conversationId.trim()
      ? message.conversationId.trim()
      : null;
    const tab = await ensureRuntimeTab(conversationId);
    _pr92RemainingTurnMs(context, "POST_RECOVERY_TAB");
    if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");

    const count = await _pr92StageOfficialPageAttachments(
      tab.id,
      context.attachmentPaths,
      context
    );
    context.staged = true;
    context.stagedTabId = tab.id;
    context.attachmentCount = count;

    // The prior core worker snapshots message.timeoutMs only after this recovery
    // hook returns. Hand it the remaining outer budget, not a fresh full turn.
    message.timeoutMs = _pr92RemainingTurnMs(context, "PRE_DISPATCH");
    return recovery;
  };
}

executeNativeTurn = async function _executeNativeTurnWithPr92RichInput(message) {
  if (message?.characterizeRichInputSupport === true) {
    if (message?.text != null || message?.attachmentPaths != null) {
      throw new Error("PR9_2_RICH_INPUT_SUPPORT_PROBE_MUST_BE_NO_WRITE");
    }
    return {
      richInputSupported: true,
      richInputSchemaVersion: PR92_RICH_INPUT_SCHEMA,
      stagingPrimitive: "DOM.setFileInputFiles",
      maxAttachmentCount: PR92_MAX_ATTACHMENT_COUNT,
      nativeMessagingCarriesAttachmentBytes: false,
      officialPageOwnsUpload: true,
      officialPageOwnsProtectedWrite: true,
      recoveryBeforeAttachmentStaging: true,
      staleAttachmentFailureFence: true,
      staleAttachmentFencePersistentAcrossWorkerRestart: true,
      singleTotalTurnDeadline: PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE,
      automaticWriteRetry: false,
      fallbackTransport: null,
      writePerformed: false
    };
  }

  if (_pr92ActiveTurnContext !== null) {
    throw new Error("PR9_2_TURN_CONTEXT_BUSY");
  }

  const context = _pr92CreateTurnContext(message);
  _pr92ActiveTurnContext = context;
  try {
    await _pr92RequireCleanAttachmentState(context);

    const attachmentPaths = _pr92NormalizeAttachmentPaths(message?.attachmentPaths);
    message.timeoutMs = _pr92RemainingTurnMs(context, "POST_PREFLIGHT");
    if (attachmentPaths.length === 0) {
      return await _pr92RichInputPriorExecuteNativeTurn(message);
    }

    if (
      message?.probeTemporaryMode === true ||
      message?.characterizeTemporaryTurn === true ||
      message?.probeTemporaryHistoryPresence === true ||
      message?.characterizeManualTemporaryGroundTruth === true ||
      message?.probeTemporaryRouteReopen === true ||
      message?.characterizeProductModelProfileSupport === true ||
      message?.characterizeProductModelProfileSelectionRecord === true
    ) {
      throw new Error("PR9_2_ATTACHMENT_PROBE_FLAG_CONFLICT");
    }
    if (!PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE) {
      throw new Error("PR9_2_TOTAL_DEADLINE_HOOK_UNAVAILABLE");
    }
    if (_pr92ActiveRichInputContext !== null) {
      throw new Error("PR9_2_RICH_INPUT_CONTEXT_BUSY");
    }

    context.attachmentPaths = attachmentPaths;
    _pr92ActiveRichInputContext = context;
    try {
      const result = await _pr92RichInputPriorExecuteNativeTurn(message);
      if (context.staged !== true || context.attachmentCount !== attachmentPaths.length) {
        throw new Error("PR9_2_ATTACHMENT_STAGE_NOT_PROVEN");
      }

      // A completed write must not erase the persistent fence merely by returning.
      // Cleanup consumes only the outer budget. If no budget remains, retain the
      // durable fence and return the already-completed write; the next turn is
      // blocked until cleanup is proven instead of fabricating response ambiguity.
      const cleanupBudget = _pr92RemainingTurnMsOrZero(context);
      if (
        Number.isInteger(context.stagedTabId) &&
        cleanupBudget > 0 &&
        await _pr92ClearOfficialPageAttachments(context.stagedTabId, cleanupBudget)
      ) {
        if (_pr92RemainingTurnMsOrZero(context) > 0) {
          await _pr92TryClearDirtyAttachmentFence();
        }
      }
      return {
        ...result,
        attachmentCount: context.attachmentCount
      };
    } catch (error) {
      // No retry after delegation. Spend only remaining budget on best-effort
      // cleanup. If the durable fence remains, surface cleanup-unproven and keep
      // the fence authoritative for the next turn/worker generation.
      const dirtyTabId = _pr92DirtyAttachmentTabId;
      const cleanupBudget = _pr92RemainingTurnMsOrZero(context);
      if (
        Number.isInteger(dirtyTabId) &&
        cleanupBudget > 0 &&
        await _pr92ClearOfficialPageAttachments(dirtyTabId, cleanupBudget)
      ) {
        if (_pr92RemainingTurnMsOrZero(context) > 0) {
          await _pr92TryClearDirtyAttachmentFence();
        }
      }
      if (Number.isInteger(_pr92DirtyAttachmentTabId)) {
        const detail = error instanceof Error ? error.message : String(error);
        throw new Error(`PR9_2_DOWNSTREAM_FAILED_AND_ATTACHMENT_CLEANUP_UNPROVEN:${detail}`);
      }
      throw error;
    } finally {
      _pr92ActiveRichInputContext = null;
    }
  } finally {
    _pr92ActiveTurnContext = null;
  }
};