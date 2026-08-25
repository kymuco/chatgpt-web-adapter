// PR9.2 rich-input overlay.
//
// This file is imported by the existing final PR8.7 worker after that worker has
// assembled the full prior service-worker chain. Attachment bytes never cross
// Native Messaging. The Python side sends only validated local file paths. This
// overlay gives those paths to the official ChatGPT page file input through CDP
// DOM.setFileInputFiles, then delegates the actual product turn to the entire
// previously-proven browser-owned worker chain. The page therefore remains
// responsible for upload semantics, Sentinel/proof handling, request construction,
// and the protected conversation write.

const _pr92RichInputPriorExecuteNativeTurn = executeNativeTurn;
const PR92_MAX_ATTACHMENT_COUNT = 32;

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

    await chrome.debugger.sendCommand(debuggee, "DOM.setFileInputFiles", {
      files: attachmentPaths,
      objectId
    });

    // Do not infer upload completion here. The existing official-turn path waits
    // for the page's enabled submit control before it can dispatch a write.
    await sleep(100);
    return attachmentPaths.length;
  } catch (error) {
    if (error instanceof Error && error.message === "PR9_2_FILE_INPUT_NOT_FOUND") {
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

executeNativeTurn = async function _executeNativeTurnWithPr92RichInput(message) {
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

  const conversationId = typeof message?.conversationId === "string" && message.conversationId.trim()
    ? message.conversationId.trim()
    : null;
  const timeoutMs = Number.isFinite(message?.timeoutMs)
    ? Math.max(10_000, Math.min(Number(message.timeoutMs), 300_000))
    : DEFAULT_TIMEOUT_MS;

  const tab = await ensureRuntimeTab(conversationId);
  if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");

  const attachmentCount = await _pr92StageOfficialPageAttachments(
    tab.id,
    attachmentPaths,
    timeoutMs
  );
  const result = await _pr92RichInputPriorExecuteNativeTurn(message);
  return {
    ...result,
    attachmentCount
  };
};
