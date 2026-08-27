// PR9.2 schema-8 closure repair.
//
// Loaded after schema 7. This layer closes two final review findings while
// preserving every previous rich-input authority boundary:
//   1. the composer must be attachment-clean before staging and page-owned
//      attachment evidence must describe the exact requested set, not merely a
//      requested subset;
//   2. destructive stale-runtime cleanup revalidates URL/runtime/fence ownership
//      immediately before tab removal and aborts if ownership changes while the
//      proof is being assembled.

const _pr92Schema8PriorStageOfficialPageAttachments = _pr92StageOfficialPageAttachments;
const _pr92Schema8PriorExecuteNativeTurn = executeNativeTurn;

const PR92_SCHEMA8_REPAIR_SCHEMA = 8;
const PR92_SCHEMA8_PRESTAGE_CLEAN_STABLE_POLLS = 2;

function _pr92Schema8AttachmentEvidenceExpression(expectedNames) {
  const encodedNames = JSON.stringify(expectedNames);
  return `(() => {
    const expected = ${encodedNames};
    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const prompt = document.querySelector('#prompt-textarea') ||
      document.querySelector('[data-testid="prompt-textarea"]') ||
      document.querySelector('[contenteditable="true"]');
    const composer = (prompt && prompt.closest('form')) || document.querySelector('form') || document.body;
    if (!composer) {
      return {
        ready: false,
        rejected: false,
        matchedCount: 0,
        groupLabelCount: 0,
        removalLabelCount: 0,
        exactAttachmentSet: false,
        evidenceKind: 'composer-missing'
      };
    }

    const normalize = (value) => typeof value === 'string' ? value.trim() : '';
    const groupLabels = Array.from(composer.querySelectorAll('[role="group"][aria-label]'))
      .filter(isVisible)
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter(Boolean);
    const removalLabels = Array.from(
      composer.querySelectorAll('button[aria-label], [role="button"][aria-label]')
    )
      .filter(isVisible)
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter((label) => /remove|delete|discard|удал/i.test(label));

    const matchesExpectedExactly = (labels) => {
      const pool = labels.slice();
      let matched = 0;
      for (const name of expected) {
        const index = pool.findIndex((label) => label === name || label.includes(name));
        if (index < 0) {
          return {
            exact: false,
            matched,
            totalCount: labels.length,
            unusedCount: pool.length
          };
        }
        pool.splice(index, 1);
        matched += 1;
      }
      return {
        exact: matched === expected.length && pool.length === 0,
        matched,
        totalCount: labels.length,
        unusedCount: pool.length
      };
    };

    const groups = matchesExpectedExactly(groupLabels);
    const removals = matchesExpectedExactly(removalLabels);
    const candidateCountsWithinExpected =
      groupLabels.length <= expected.length && removalLabels.length <= expected.length;
    const exactAttachmentSet = candidateCountsWithinExpected &&
      (groups.exact || removals.exact);
    const matchedCount = exactAttachmentSet
      ? expected.length
      : Math.max(groups.matched, removals.matched);

    const statusNodes = Array.from(
      composer.querySelectorAll('[role="alert"], [aria-live], [data-testid*="error"], [aria-label]')
    ).filter(isVisible);
    const statusText = statusNodes.map((element) => {
      return normalize(element.getAttribute('aria-label')) + ' ' + normalize(element.textContent);
    }).join(' ');
    const rejected = /(upload|attachment|file).{0,40}(failed|error|unsupported|too large)|(failed|error|unsupported).{0,40}(upload|attachment|file)|(не удалось|ошибка).{0,40}(загруз|файл)/i.test(statusText);

    return {
      ready: exactAttachmentSet,
      rejected,
      matchedCount,
      groupLabelCount: groupLabels.length,
      removalLabelCount: removalLabels.length,
      exactAttachmentSet,
      evidenceKind: groups.exact ? 'exact-role-group-aria-label-set' :
        (removals.exact ? 'exact-remove-control-aria-label-set' : 'not-ready')
    };
  })()`;
}

// Every later evidence read—including schema 7's atomic final validator—uses the
// exact-set expression. An old same-name chip cannot satisfy the turn because the
// schema-8 staging wrapper first proves the composer contains no attachment evidence.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema8AttachmentEvidenceExpression;

async function _pr92Schema8RequireAttachmentCleanComposerBeforeStaging(tabId, context) {
  const debuggee = { tabId };
  let attached = false;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA8_PRESTAGE_CLEAN_ATTACH");
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");

    let stable = 0;
    while (stable < PR92_SCHEMA8_PRESTAGE_CLEAN_STABLE_POLLS) {
      const evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
        debuggee,
        [],
        context
      );
      const groupCount = Number(evidence?.groupLabelCount);
      const removalCount = Number(evidence?.removalLabelCount);
      const clean = evidence?.exactAttachmentSet === true &&
        groupCount === 0 && removalCount === 0;
      if (!clean) {
        throw new Error("PR9_2_PREEXISTING_COMPOSER_ATTACHMENT_PRESENT");
      }
      stable += 1;
      if (stable < PR92_SCHEMA8_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA8_PRESTAGE_CLEAN_STABILITY"
        );
      }
    }
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

_pr92StageOfficialPageAttachments = async function _pr92Schema8StageFromCleanComposer(
  tabId,
  attachmentPaths,
  context
) {
  if (attachmentPaths.length === 0) return 0;
  await _pr92Schema8RequireAttachmentCleanComposerBeforeStaging(tabId, context);
  return _pr92Schema8PriorStageOfficialPageAttachments(tabId, attachmentPaths, context);
};

function _pr92Schema8FenceIdentityMatches(records, tabId) {
  const localIdentity = records?.local?.runtimeIdentity;
  const sessionIdentity = records?.session?.runtimeIdentity;
  return Boolean(
    Number.isInteger(records?.local?.tabId) &&
    records.local.tabId === tabId &&
    Number.isInteger(records?.session?.tabId) &&
    records.session.tabId === tabId &&
    typeof localIdentity === "string" &&
    localIdentity &&
    typeof sessionIdentity === "string" &&
    sessionIdentity === localIdentity
  );
}

_pr92ClearOfficialPageAttachments = async function _pr92Schema8ClearFencedRuntimeTab(
  tabId,
  timeoutMs
) {
  if (!Number.isInteger(tabId) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return false;
  }

  const richContext = _pr92ActiveRichInputContext;
  if (richContext !== null && richContext.staged === true) return false;

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

  // A non-ChatGPT reused numeric id cannot contain the old ChatGPT composer and
  // is never destructively closed.
  if (!isChatGPTUrl(candidate?.url || "")) return true;

  let ownershipInvalidated = false;
  let closeDispatched = false;
  const onUpdated = (updatedTabId, changeInfo) => {
    if (
      !closeDispatched &&
      updatedTabId === tabId &&
      (typeof changeInfo?.url === "string" || changeInfo?.status === "loading")
    ) {
      ownershipInvalidated = true;
    }
  };
  const onRemoved = (removedTabId) => {
    if (!closeDispatched && removedTabId === tabId) ownershipInvalidated = true;
  };
  const onStorageChanged = (changes, areaName) => {
    if (closeDispatched) return;
    if (
      areaName === "local" &&
      (Object.prototype.hasOwnProperty.call(changes, RUNTIME_TAB_KEY) ||
       Object.prototype.hasOwnProperty.call(changes, PR92_DIRTY_ATTACHMENT_STORAGE_KEY))
    ) {
      ownershipInvalidated = true;
    }
    if (
      areaName === "session" &&
      Object.prototype.hasOwnProperty.call(changes, PR92_SCHEMA7_SESSION_IDENTITY_KEY)
    ) {
      ownershipInvalidated = true;
    }
  };

  chrome.tabs.onUpdated.addListener(onUpdated);
  chrome.tabs.onRemoved.addListener(onRemoved);
  if (chrome.storage?.onChanged) chrome.storage.onChanged.addListener(onStorageChanged);

  try {
    let currentRuntimeTabId;
    let records;
    try {
      currentRuntimeTabId = await _pr92Schema7RunUntil(
        deadlineAt,
        "CLEANUP_RUNTIME_IDENTITY_CURRENT_ID",
        () => storedRuntimeTabId()
      );
      records = await _pr92Schema7ReadFenceRecords(deadlineAt);
    } catch {
      return false;
    }
    if (
      ownershipInvalidated ||
      currentRuntimeTabId !== tabId ||
      !_pr92Schema8FenceIdentityMatches(records, tabId)
    ) {
      return false;
    }

    // Re-read every destructive authority input after the potentially slow record
    // reads. The final tab snapshot is deliberately the last awaited proof before
    // chrome.tabs.remove() is dispatched.
    let finalRecords;
    let finalRuntimeTabId;
    let finalCandidate;
    try {
      finalRecords = await _pr92Schema7ReadFenceRecords(deadlineAt);
      finalRuntimeTabId = await _pr92Schema7RunUntil(
        deadlineAt,
        "CLEANUP_RUNTIME_IDENTITY_FINAL_ID",
        () => storedRuntimeTabId()
      );
      finalCandidate = await _pr92Schema7RunUntil(
        deadlineAt,
        "CLEANUP_RUNTIME_TAB_FINAL_LOOKUP",
        () => chrome.tabs.get(tabId)
      );
    } catch {
      return false;
    }

    if (
      ownershipInvalidated ||
      finalRuntimeTabId !== tabId ||
      !_pr92Schema8FenceIdentityMatches(finalRecords, tabId) ||
      !isChatGPTUrl(finalCandidate?.url || "") ||
      finalCandidate.url !== candidate.url
    ) {
      return false;
    }

    // No await occurs between the last authority check and dispatch of the close.
    closeDispatched = true;
    let removal;
    try {
      removal = chrome.tabs.remove(tabId);
    } catch {
      return false;
    }
    try {
      await _pr92Schema7RunUntil(
        deadlineAt,
        "CLEANUP_RUNTIME_TAB_CLOSE",
        () => removal
      );
    } catch (error) {
      if (_pr92DeadlineRepairIsTimeoutError(error)) return false;
      // A concurrent close is accepted only after explicit absence proof below.
    }
    return _pr92DeadlineRepairProveTabAbsent(tabId, deadlineAt);
  } finally {
    chrome.tabs.onUpdated.removeListener(onUpdated);
    chrome.tabs.onRemoved.removeListener(onRemoved);
    if (chrome.storage?.onChanged) chrome.storage.onChanged.removeListener(onStorageChanged);
  }
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema8Repair(message) {
  const result = await _pr92Schema8PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA8_REPAIR_SCHEMA,
    preStageComposerAttachmentClean: true,
    exactComposerAttachmentSetRequired: true,
    destructiveCleanupAuthorityRevalidatedAtClose: true,
    destructiveCleanupOwnershipChangeFailsClosed: true
  };
};
