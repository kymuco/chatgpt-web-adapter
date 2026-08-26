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
const PR92_RICH_INPUT_SCHEMA = 1;
const PR92_MAX_ATTACHMENT_COUNT = 32;
const PR92_DIRTY_ATTACHMENT_STORAGE_KEY = "pr92DirtyAttachmentFenceV1";

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
  return Number.isFinite(message?.timeoutMs)
    ? Math.max(10_000, Math.min(Number(message.timeoutMs), 300_000))
    : DEFAULT_TIMEOUT_MS;
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

async function _pr92TryRevealFileInput(debuggee) {
  try {
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
  } catch {
    // The bounded hidden-input path is preferred; reveal is only a compatibility aid.
  }
  await sleep(100);
}

async function _pr92StageOfficialPageAttachments(tabId, attachmentPaths, timeoutMs) {
  if (attachmentPaths.length === 0) return 0;
  const debuggee = { tabId };
  const startedAt = performance.now();
  let attached = false;
  let objectId = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    await chrome.debugger.sendCommand(debuggee, "DOM.enable");
    await waitForComposerReady(
      debuggee,
      Math.min(remainingMs(startedAt, timeoutMs), DEFAULT_READY_TIMEOUT_MS)
    );

    objectId = await _pr92FindFileInputObjectId(debuggee);
    if (!objectId) {
      await _pr92TryRevealFileInput(debuggee);
      objectId = await _pr92FindFileInputObjectId(debuggee);
    }
    if (!objectId) throw new Error("PR9_2_FILE_INPUT_NOT_FOUND");

    // The persistent fence is authoritative across Manifest V3 worker restarts.
    // It must exist before the browser is allowed to select any local file.
    await _pr92PersistDirtyAttachmentFence(tabId);
    await chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
      files: attachmentPaths,
      objectId
    });
    await sleep(100);
    return attachmentPaths.length;
  } catch (error) {
    if (error instanceof Error && error.message === "PR9_2_FILE_INPUT_NOT_FOUND") {
      throw error;
    }
    if (
      error instanceof Error &&
      error.message.startsWith("PR9_2_STALE_ATTACHMENT_FENCE_")
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
  if (!Number.isInteger(tabId)) return false;
  try {
    await chrome.tabs.get(tabId);
  } catch {
    // A removed tab cannot retain a stale composer attachment.
    return true;
  }

  try {
    await waitForTabComplete(tabId, Math.max(1000, Math.min(timeoutMs, 10_000)));
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

async function _pr92RequireCleanAttachmentState(timeoutMs) {
  const dirtyTabId = await _pr92ReadDirtyAttachmentFence();
  if (!Number.isInteger(dirtyTabId)) return;

  const cleared = await _pr92ClearOfficialPageAttachments(dirtyTabId, timeoutMs);
  if (!cleared) {
    throw new Error("PR9_2_STALE_ATTACHMENT_CLEANUP_REQUIRED");
  }
  if (!await _pr92TryClearDirtyAttachmentFence()) {
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_CLEAR_FAILED");
  }
}

// Recovery is the last operation that is allowed to reload the runtime tab before
// the core page turn. Hook immediately after it rather than staging in the outer
// executeNativeTurn wrapper. This preserves PR8.11 recovery/timing semantics and
// prevents a recovery reload from silently discarding the selected files.
if (_pr92PriorMaybeRecoverStaleRuntimeUi) {
  _pr811MaybeRecoverStaleRuntimeUi = async function _pr92RecoverThenStage(message) {
    const recovery = await _pr92PriorMaybeRecoverStaleRuntimeUi(message);
    const context = _pr92ActiveRichInputContext;
    if (context === null) return recovery;
    if (context.staged === true) {
      throw new Error("PR9_2_ATTACHMENT_STAGE_REENTRANCY");
    }

    const conversationId = typeof message?.conversationId === "string" && message.conversationId.trim()
      ? message.conversationId.trim()
      : null;
    const tab = await ensureRuntimeTab(conversationId);
    if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");

    const count = await _pr92StageOfficialPageAttachments(
      tab.id,
      context.attachmentPaths,
      context.timeoutMs
    );
    context.staged = true;
    context.stagedTabId = tab.id;
    context.attachmentCount = count;
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
      automaticWriteRetry: false,
      fallbackTransport: null,
      writePerformed: false
    };
  }

  const timeoutMs = _pr92TurnTimeoutMs(message);
  await _pr92RequireCleanAttachmentState(timeoutMs);

  const attachmentPaths = _pr92NormalizeAttachmentPaths(message?.attachmentPaths);
  if (attachmentPaths.length === 0) {
    return _pr92RichInputPriorExecuteNativeTurn(message);
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
  if (!_pr92PriorMaybeRecoverStaleRuntimeUi) {
    throw new Error("PR9_2_RECOVERY_HOOK_UNAVAILABLE");
  }
  if (_pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_RICH_INPUT_CONTEXT_BUSY");
  }

  const context = {
    attachmentPaths,
    timeoutMs,
    staged: false,
    stagedTabId: null,
    attachmentCount: 0
  };
  _pr92ActiveRichInputContext = context;
  try {
    const result = await _pr92RichInputPriorExecuteNativeTurn(message);
    if (context.staged !== true || context.attachmentCount !== attachmentPaths.length) {
      throw new Error("PR9_2_ATTACHMENT_STAGE_NOT_PROVEN");
    }
    // A completed write must not erase the persistent fence merely by returning.
    // Remove the fence only after explicit file-input cleanup (or tab removal)
    // succeeds. If cleanup is temporarily unavailable, retain the durable fence;
    // returning the already-canonical write is safer than fabricating ambiguity,
    // and the next turn will be blocked until cleanup is proven.
    if (
      Number.isInteger(context.stagedTabId) &&
      await _pr92ClearOfficialPageAttachments(context.stagedTabId, timeoutMs)
    ) {
      await _pr92TryClearDirtyAttachmentFence();
    }
    return {
      ...result,
      attachmentCount: context.attachmentCount
    };
  } catch (error) {
    const dirtyTabId = await _pr92ReadDirtyAttachmentFence();
    if (Number.isInteger(dirtyTabId)) {
      const cleared = await _pr92ClearOfficialPageAttachments(dirtyTabId, timeoutMs);
      if (cleared) await _pr92TryClearDirtyAttachmentFence();
    }
    if (Number.isInteger(await _pr92ReadDirtyAttachmentFence())) {
      const detail = error instanceof Error ? error.message : String(error);
      throw new Error(`PR9_2_DOWNSTREAM_FAILED_AND_ATTACHMENT_CLEANUP_UNPROVEN:${detail}`);
    }
    throw error;
  } finally {
    _pr92ActiveRichInputContext = null;
  }
};
