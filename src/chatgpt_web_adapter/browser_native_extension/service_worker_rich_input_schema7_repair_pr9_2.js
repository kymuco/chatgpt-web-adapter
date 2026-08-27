// PR9.2 schema-7 final authority repair.
//
// Loaded after the schema-6 closure overlay. This layer closes the final three
// reviewed races without changing text-only behavior:
//   1. final attachment validation and Send click execute atomically in one
//      page-side expression;
//   2. the debugger acknowledgement of that click is never awaited, so a slow
//      synchronous click handler cannot turn an already-issued write into a local
//      timeout; the existing Network.requestWillBeSent observation remains the
//      first authoritative post-submit proof;
//   3. destructive stale-composer cleanup closes a tab only when a browser-session
//      identity proves that the numeric tab id still belongs to the fenced
//      extension-managed ChatGPT runtime.

const _pr92Schema7PriorPersistDirtyAttachmentFence = _pr92PersistDirtyAttachmentFence;
const _pr92Schema7PriorTryClearDirtyAttachmentFence = _pr92TryClearDirtyAttachmentFence;
const _pr92Schema7PriorClearOfficialPageAttachments = _pr92ClearOfficialPageAttachments;
const _pr92Schema7PriorSubmitOfficialPageTurn = submitOfficialPageTurn;
const _pr92Schema7PriorExecuteNativeTurn = executeNativeTurn;

const PR92_SCHEMA7_REPAIR_SCHEMA = 7;
const PR92_SCHEMA7_SESSION_IDENTITY_KEY = "pr92DirtyAttachmentSessionIdentityV1";
const PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS = DEFAULT_SUBMIT_ACK_TIMEOUT_MS + 500;
const PR92_SCHEMA7_PROTECTED_SUBMIT_PRIMITIVE =
  "PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK";
const PR92_SCHEMA7_POST_SUBMIT_PROOF = "NETWORK_REQUEST_OBSERVATION";

function _pr92Schema7NewRuntimeIdentity() {
  if (typeof crypto?.randomUUID === "function") return crypto.randomUUID();
  const words = new Uint32Array(4);
  crypto.getRandomValues(words);
  return Array.from(words, (word) => word.toString(16).padStart(8, "0")).join("");
}

async function _pr92Schema7RunUntil(deadlineAt, stage, operation) {
  return _pr92DeadlineRepairRunUntil(deadlineAt, stage, operation);
}

async function _pr92Schema7ReadFenceRecords(deadlineAt) {
  if (!chrome.storage?.session) {
    throw new Error("PR9_2_STALE_ATTACHMENT_SESSION_IDENTITY_UNAVAILABLE");
  }
  const local = await _pr92Schema7RunUntil(
    deadlineAt,
    "CLEANUP_FENCE_LOCAL_IDENTITY_READ",
    () => chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY)
  );
  const session = await _pr92Schema7RunUntil(
    deadlineAt,
    "CLEANUP_FENCE_SESSION_IDENTITY_READ",
    () => chrome.storage.session.get(PR92_SCHEMA7_SESSION_IDENTITY_KEY)
  );
  return {
    local: local?.[PR92_DIRTY_ATTACHMENT_STORAGE_KEY] || null,
    session: session?.[PR92_SCHEMA7_SESSION_IDENTITY_KEY] || null
  };
}

_pr92PersistDirtyAttachmentFence = async function _pr92PersistFenceWithSessionIdentity(tabId) {
  if (!Number.isInteger(tabId)) {
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_TAB_REQUIRED");
  }
  if (!chrome.storage?.session) {
    throw new Error("PR9_2_STALE_ATTACHMENT_SESSION_IDENTITY_UNAVAILABLE");
  }

  let tab;
  try {
    tab = await chrome.tabs.get(tabId);
  } catch {
    throw new Error("PR9_2_STALE_ATTACHMENT_RUNTIME_IDENTITY_UNAVAILABLE");
  }
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR9_2_STALE_ATTACHMENT_RUNTIME_IDENTITY_MISMATCH");
  }

  const runtimeIdentity = _pr92Schema7NewRuntimeIdentity();
  try {
    // Browser-session storage deliberately does not survive a browser restart.
    // Local storage remains the durable fence; the session token is only the
    // authority required before destructively closing a still-live tab id.
    await chrome.storage.session.set({
      [PR92_SCHEMA7_SESSION_IDENTITY_KEY]: {
        schema: 1,
        tabId,
        runtimeIdentity
      }
    });
    await chrome.storage.local.set({
      [PR92_DIRTY_ATTACHMENT_STORAGE_KEY]: {
        schema: 2,
        tabId,
        runtimeIdentity
      }
    });
  } catch {
    try { await chrome.storage.session.remove(PR92_SCHEMA7_SESSION_IDENTITY_KEY); } catch {}
    throw new Error("PR9_2_STALE_ATTACHMENT_FENCE_PERSIST_FAILED");
  }
  _pr92DirtyAttachmentTabId = tabId;
};

async function _pr92Schema7ClearFenceStorage() {
  if (!chrome.storage?.session) return false;
  try {
    // Remove the non-authoritative session token first. If the durable local
    // mutation then fails, the local fence remains and the next turn fails closed.
    await chrome.storage.session.remove(PR92_SCHEMA7_SESSION_IDENTITY_KEY);
    await chrome.storage.local.remove(PR92_DIRTY_ATTACHMENT_STORAGE_KEY);
    _pr92DirtyAttachmentTabId = null;
    return true;
  } catch {
    return false;
  }
}

_pr92TryClearDirtyAttachmentFence = async function _pr92Schema7TryClearDirtyAttachmentFence() {
  const richContext = _pr92ActiveRichInputContext;
  if (richContext !== null && richContext.staged === true) return false;

  const context = _pr92ActiveTurnContext;
  if (context === null) return _pr92Schema7ClearFenceStorage();
  try {
    return await _pr92Schema7RunUntil(
      context.deadlineAt,
      "STALE_ATTACHMENT_SCHEMA7_FENCE_CLEAR",
      _pr92Schema7ClearFenceStorage
    );
  } catch {
    return false;
  }
};

_pr92ClearOfficialPageAttachments = async function _pr92Schema7ClearFencedRuntimeTab(
  tabId,
  timeoutMs
) {
  if (!Number.isInteger(tabId) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return false;
  }

  const richContext = _pr92ActiveRichInputContext;
  if (richContext !== null && richContext.staged === true) {
    return false;
  }

  const deadlineAt = _pr92DeadlineRepairDeadlineFromBudget(timeoutMs);
  let candidate;
  try {
    candidate = await _pr92Schema7RunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_TAB_LOOKUP",
      () => chrome.tabs.get(tabId)
    );
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
    return _pr92DeadlineRepairIsMissingTabError(error);
  }

  // A reused numeric id that now points outside ChatGPT cannot contain the old
  // fenced composer. Treat it as absence of the old runtime and never close it.
  if (!isChatGPTUrl(candidate?.url || "")) return true;

  let currentRuntimeTabId;
  try {
    currentRuntimeTabId = await _pr92Schema7RunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_IDENTITY_CURRENT_ID",
      () => storedRuntimeTabId()
    );
  } catch {
    return false;
  }
  if (currentRuntimeTabId !== tabId) {
    // The extension has already moved on to a different managed runtime tab.
    return true;
  }

  let records;
  try {
    records = await _pr92Schema7ReadFenceRecords(deadlineAt);
  } catch {
    return false;
  }
  const localIdentity = records.local?.runtimeIdentity;
  const sessionIdentity = records.session?.runtimeIdentity;
  if (
    !Number.isInteger(records.local?.tabId) ||
    records.local.tabId !== tabId ||
    typeof localIdentity !== "string" ||
    !localIdentity
  ) {
    return false;
  }

  if (records.session == null) {
    // Browser restart clears storage.session while the durable local fence remains.
    // A restored/reused ChatGPT tab with the same numeric id is therefore not safe
    // to close automatically. Keep the fence and fail closed instead.
    return false;
  }
  if (
    records.session?.tabId !== tabId ||
    typeof sessionIdentity !== "string" ||
    sessionIdentity !== localIdentity
  ) {
    // Session identity mismatch proves this numeric id is not the fenced runtime.
    // Do not close the candidate; the old composer is absent in this session.
    return true;
  }

  try {
    await _pr92Schema7RunUntil(
      deadlineAt,
      "CLEANUP_RUNTIME_TAB_CLOSE",
      () => chrome.tabs.remove(tabId)
    );
  } catch (error) {
    if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
    // Concurrent removal is acceptable only after explicit absence proof below.
  }
  return _pr92DeadlineRepairProveTabAbsent(tabId, deadlineAt);
};

function _pr92Schema7AtomicAttachmentSubmitExpression(
  selector,
  deadlineEpochMs,
  expectedNames
) {
  const encodedSelector = JSON.stringify(selector);
  const encodedDeadline = JSON.stringify(deadlineEpochMs);
  const encodedExpected = JSON.stringify(expectedNames);
  const evidenceExpression = _pr92ClosureAttachmentEvidenceExpression(expectedNames);
  return `(() => {
    const deadlineEpochMs = ${encodedDeadline};
    const expected = ${encodedExpected};
    if (!Number.isFinite(deadlineEpochMs) || Date.now() >= deadlineEpochMs) {
      return { clicked: false, reason: 'deadline-expired' };
    }

    const evidence = ${evidenceExpression};
    if (evidence && evidence.rejected === true) {
      return { clicked: false, reason: 'attachment-rejected' };
    }
    if (!evidence || evidence.ready !== true || Number(evidence.matchedCount) !== expected.length) {
      return { clicked: false, reason: 'attachment-evidence-missing' };
    }

    const button = document.querySelector(${encodedSelector});
    if (!(button instanceof HTMLElement)) {
      return { clicked: false, reason: 'send-button-missing' };
    }
    const rect = button.getBoundingClientRect();
    const style = getComputedStyle(button);
    const visible = rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    const disabled = Boolean(button.disabled) || button.getAttribute('aria-disabled') === 'true';
    if (!visible || disabled) {
      return { clicked: false, reason: 'send-button-not-ready' };
    }
    if (Date.now() >= deadlineEpochMs) {
      return { clicked: false, reason: 'deadline-expired' };
    }

    // Validation and click are synchronous in this one page task. No page task can
    // remove an attachment between the final evidence check and button.click().
    button.click();
    return { clicked: true, reason: 'atomic-page-owned-click', matchedCount: expected.length };
  })()`;
}

submitOfficialPageTurn = async function _pr92Schema7AtomicAttachmentSubmit(
  debuggee,
  timeoutMs
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92Schema7PriorSubmitOfficialPageTurn(debuggee, timeoutMs);
  }

  // Keep the early page-owned evidence check to fail before a readiness wait when
  // the upload is already rejected. The final authority still lives inside the
  // single atomic page expression below.
  const earlyCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(
    debuggee,
    context.attachmentPaths,
    context,
    1
  );
  if (earlyCount !== context.attachmentPaths.length) {
    throw new Error("PR9_2_PRE_SUBMIT_ATTACHMENT_EVIDENCE_MISMATCH");
  }

  const remaining = _pr92RemainingTurnMs(context, "SCHEMA7_SEND_READY");
  const readyBudget = Math.min(
    remaining,
    Number.isFinite(timeoutMs) ? Math.max(1, Number(timeoutMs)) : DEFAULT_SUBMIT_READY_TIMEOUT_MS,
    DEFAULT_SUBMIT_READY_TIMEOUT_MS
  );
  let point;
  try {
    point = await waitForSendButtonPoint(debuggee, readyBudget);
  } catch (error) {
    _pr92RemainingTurnMs(context, "SCHEMA7_SEND_READY");
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`PR9_2_RICH_INPUT_SEND_BUTTON_NOT_READY:${detail}`);
  }

  const selector = typeof point?.selector === "string" && point.selector
    ? point.selector
    : null;
  if (!selector) throw new Error("PR9_2_SEND_BUTTON_SELECTOR_REQUIRED");

  const submitRemaining = _pr92RemainingTurnMs(context, "SCHEMA7_ATOMIC_SUBMIT");
  if (submitRemaining <= PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS) {
    throw new Error("PR9_2_TOTAL_TURN_TIMEOUT:SCHEMA7_SUBMIT_OBSERVATION_RESERVE");
  }
  const pageDeadlineEpochMs = Date.now() +
    submitRemaining - PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS;
  const expectedNames = _pr92ClosureExpectedBasenames(context.attachmentPaths);
  const expression = _pr92Schema7AtomicAttachmentSubmitExpression(
    selector,
    pageDeadlineEpochMs,
    expectedNames
  );

  // Do not await the debugger acknowledgement after a command that can click.
  // The page-side absolute deadline prevents late execution, while the existing
  // Network.requestWillBeSent listener (installed before submission) proves that
  // a protected conversation write actually occurred. No retry is introduced.
  try {
    const pending = chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: false
    });
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`PR9_2_ATOMIC_SUBMIT_DISPATCH_FAILED:${detail}`);
  }

  return {
    strategy: "page_deadline_guarded_atomic_attachment_validate_and_click",
    selector
  };
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema7Repair(message) {
  const result = await _pr92Schema7PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA7_REPAIR_SCHEMA,
    postSendReadinessAttachmentRevalidation: true,
    atomicAttachmentValidationAndSubmit: true,
    protectedSubmitPrimitive: PR92_SCHEMA7_PROTECTED_SUBMIT_PRIMITIVE,
    postClickDebuggerAckRequired: false,
    protectedSubmitOutcomeProof: PR92_SCHEMA7_POST_SUBMIT_PROOF,
    submitObservationReserveMs: PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS,
    staleAttachmentCleanupRequiresSessionRuntimeIdentity: true,
    staleAttachmentIdentityMismatchClosesTab: false,
    staleAttachmentUnprovenIdentityFailsClosed: true
  };
};
