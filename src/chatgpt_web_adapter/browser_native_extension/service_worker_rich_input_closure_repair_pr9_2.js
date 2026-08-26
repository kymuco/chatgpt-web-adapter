// PR9.2 final closure repair overlay.
//
// Loaded after the rich-input and deadline-repair overlays. This layer closes two
// remaining authority gaps without changing text-only behavior:
//   1. protected rich-input submission never relies on a non-cancellable CDP
//      Input command; the official page performs a deadline-guarded Send click;
//   2. attachmentCount is accepted only after stable page-owned composer evidence
//      for every requested basename, and that evidence is revalidated immediately
//      before protected submission.

const _pr92ClosurePriorStageOfficialPageAttachments = _pr92StageOfficialPageAttachments;
const _pr92ClosurePriorClickSendButton = clickSendButton;
const _pr92ClosurePriorSubmitWithEnter = submitWithEnter;
const _pr92ClosurePriorSubmitOfficialPageTurn = submitOfficialPageTurn;
const _pr92ClosurePriorExecuteNativeTurn = executeNativeTurn;
const PR92_CLOSURE_REPAIR_SCHEMA = 6;
const PR92_PAGE_ATTACHMENT_EVIDENCE_SOURCE = "PAGE_OWNED_COMPOSER_ATTACHMENT_STATE";
const PR92_PAGE_ATTACHMENT_STABLE_POLLS = 2;
const PR92_PAGE_ATTACHMENT_POLL_MS = 150;
const PR92_PAGE_SUBMIT_DEADLINE_SAFETY_MS = 75;
const PR92_PAGE_GUARDED_SUBMIT_PRIMITIVE = "PAGE_DEADLINE_GUARDED_SEND_BUTTON_CLICK";

function _pr92ClosureExpectedBasenames(attachmentPaths) {
  return attachmentPaths.map((rawPath) => {
    const normalized = String(rawPath || "").replace(/\\/g, "/");
    const parts = normalized.split("/");
    const name = parts[parts.length - 1] || "";
    if (!name) throw new Error("PR9_2_ATTACHMENT_BASENAME_REQUIRED");
    return name;
  });
}

function _pr92ClosureAttachmentEvidenceExpression(expectedNames) {
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
      return { ready: false, rejected: false, matchedCount: 0, evidenceKind: 'composer-missing' };
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

    const matchesExpected = (labels) => {
      const pool = labels.slice();
      let matched = 0;
      for (const name of expected) {
        const index = pool.findIndex((label) => label === name || label.includes(name));
        if (index < 0) return { ready: false, matched };
        pool.splice(index, 1);
        matched += 1;
      }
      return { ready: matched === expected.length, matched };
    };

    const groups = matchesExpected(groupLabels);
    const removals = matchesExpected(removalLabels);
    const ready = groups.ready || removals.ready;
    const matchedCount = Math.max(groups.matched, removals.matched);

    const statusNodes = Array.from(
      composer.querySelectorAll('[role="alert"], [aria-live], [data-testid*="error"], [aria-label]')
    ).filter(isVisible);
    const statusText = statusNodes.map((element) => {
      return `${normalize(element.getAttribute('aria-label'))} ${normalize(element.textContent)}`;
    }).join(' ');
    const rejected = /(upload|attachment|file).{0,40}(failed|error|unsupported|too large)|` +
      `(failed|error|unsupported).{0,40}(upload|attachment|file)|` +
      `(не удалось|ошибка).{0,40}(загруз|файл)/i.test(statusText);

    return {
      ready,
      rejected,
      matchedCount,
      evidenceKind: groups.ready ? 'role-group-aria-label' :
        (removals.ready ? 'remove-control-aria-label' : 'not-ready')
    };
  })()`;
}

async function _pr92ClosureReadPageOwnedAttachmentEvidence(
  debuggee,
  expectedNames,
  context
) {
  _pr92RemainingTurnMs(context, "PAGE_ATTACHMENT_EVIDENCE_READ");
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: _pr92ClosureAttachmentEvidenceExpression(expectedNames),
    returnByValue: true,
    awaitPromise: true
  });
  _pr92RemainingTurnMs(context, "PAGE_ATTACHMENT_EVIDENCE_READ");
  const value = result?.result?.value;
  if (!value || typeof value !== "object") {
    throw new Error("PR9_2_PAGE_ATTACHMENT_EVIDENCE_INVALID");
  }
  return value;
}

async function _pr92ClosureWaitForPageOwnedAttachmentEvidence(
  debuggee,
  attachmentPaths,
  context,
  stablePolls = PR92_PAGE_ATTACHMENT_STABLE_POLLS
) {
  const expectedNames = _pr92ClosureExpectedBasenames(attachmentPaths);
  let stable = 0;
  while (true) {
    const evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
      debuggee,
      expectedNames,
      context
    );
    if (evidence.rejected === true) {
      throw new Error("PR9_2_PAGE_ATTACHMENT_REJECTED");
    }
    if (
      evidence.ready === true &&
      Number(evidence.matchedCount) === expectedNames.length
    ) {
      stable += 1;
      if (stable >= stablePolls) return expectedNames.length;
    } else {
      stable = 0;
    }
    await _pr92BoundedSleep(
      context,
      PR92_PAGE_ATTACHMENT_POLL_MS,
      "PAGE_ATTACHMENT_EVIDENCE_WAIT"
    );
  }
}

// The primary overlay stages with DOM.setFileInputFiles. Do not accept its path
// count as confirmation. Reattach only to observe the official page's composer and
// return a count derived from stable attachment chips/controls instead.
_pr92StageOfficialPageAttachments = async function _pr92StageWithPageOwnedEvidence(
  tabId,
  attachmentPaths,
  context
) {
  const stagedCount = await _pr92ClosurePriorStageOfficialPageAttachments(
    tabId,
    attachmentPaths,
    context
  );
  if (stagedCount !== attachmentPaths.length) {
    throw new Error("PR9_2_ATTACHMENT_STAGE_COUNT_MISMATCH");
  }

  const debuggee = { tabId };
  let attached = false;
  try {
    _pr92RemainingTurnMs(context, "PAGE_ATTACHMENT_EVIDENCE_ATTACH");
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const pageOwnedCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(
      debuggee,
      attachmentPaths,
      context,
      PR92_PAGE_ATTACHMENT_STABLE_POLLS
    );
    if (pageOwnedCount !== attachmentPaths.length) {
      throw new Error("PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH");
    }
    return pageOwnedCount;
  } catch (error) {
    if (
      error instanceof Error &&
      (
        error.message.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:") ||
        error.message === "PR9_2_PAGE_ATTACHMENT_REJECTED" ||
        error.message === "PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH"
      )
    ) {
      throw error;
    }
    throw new Error("PR9_2_PAGE_ATTACHMENT_EVIDENCE_FAILED");
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
};

function _pr92ClosurePageGuardedSubmitExpression(selector, deadlineEpochMs) {
  const encodedSelector = JSON.stringify(selector);
  const encodedDeadline = JSON.stringify(deadlineEpochMs);
  return `(() => {
    const deadlineEpochMs = ${encodedDeadline};
    if (!Number.isFinite(deadlineEpochMs) || Date.now() >= deadlineEpochMs) {
      return { clicked: false, reason: 'deadline-expired' };
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
    button.click();
    return { clicked: true, reason: 'page-owned-click' };
  })()`;
}

// Raw CDP Input events are non-cancellable after dispatch. They are therefore not
// a valid protected-submit primitive for rich turns: a Promise.race timeout can
// report failure while the queued mouse/key command later reaches the page. Keep
// historical behavior only for text-only turns and fail closed if an older rich
// path somehow tries to invoke these primitives.
clickSendButton = async function _pr92ClosureRejectRawMouseSubmit(debuggee, point) {
  if (_pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_RICH_INPUT_RAW_MOUSE_SUBMIT_FORBIDDEN");
  }
  return _pr92ClosurePriorClickSendButton(debuggee, point);
};

submitWithEnter = async function _pr92ClosureRejectRawEnterSubmit(debuggee) {
  if (_pr92ActiveRichInputContext !== null) {
    throw new Error("PR9_2_RICH_INPUT_RAW_ENTER_SUBMIT_FORBIDDEN");
  }
  return _pr92ClosurePriorSubmitWithEnter(debuggee);
};

submitOfficialPageTurn = async function _pr92ClosurePageDeadlineGuardedSubmit(
  debuggee,
  timeoutMs
) {
  const context = _pr92ActiveRichInputContext;
  if (context === null) {
    return _pr92ClosurePriorSubmitOfficialPageTurn(debuggee, timeoutMs);
  }

  // Validate page-owned attachment state before waiting for the Send control. This
  // fails early when staging was rejected, but is not the final authority because
  // upload/composer state may still change while Send readiness is being polled.
  const revalidatedCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(
    debuggee,
    context.attachmentPaths,
    context,
    1
  );
  if (revalidatedCount !== context.attachmentPaths.length) {
    throw new Error("PR9_2_PRE_SUBMIT_ATTACHMENT_EVIDENCE_MISMATCH");
  }

  const remaining = _pr92RemainingTurnMs(context, "PAGE_GUARDED_SUBMIT_READY");
  const readyBudget = Math.min(
    remaining,
    Number.isFinite(timeoutMs) ? Math.max(1, Number(timeoutMs)) : DEFAULT_SUBMIT_READY_TIMEOUT_MS,
    DEFAULT_SUBMIT_READY_TIMEOUT_MS
  );
  let point;
  try {
    point = await waitForSendButtonPoint(debuggee, readyBudget);
  } catch (error) {
    _pr92RemainingTurnMs(context, "PAGE_GUARDED_SUBMIT_READY");
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`PR9_2_RICH_INPUT_SEND_BUTTON_NOT_READY:${detail}`);
  }

  const selector = typeof point?.selector === "string" && point.selector
    ? point.selector
    : null;
  if (!selector) throw new Error("PR9_2_SEND_BUTTON_SELECTOR_REQUIRED");

  // Send-readiness polling can outlive an asynchronously rejected upload. Re-read
  // page-owned composer evidence AFTER that wait and immediately before the only
  // protected-submit command. A text-only Send control can therefore never inherit
  // a stale attachmentCount from the earlier staging/readiness phase.
  const postReadinessCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(
    debuggee,
    context.attachmentPaths,
    context,
    1
  );
  if (postReadinessCount !== context.attachmentPaths.length) {
    throw new Error("PR9_2_POST_READINESS_ATTACHMENT_EVIDENCE_MISMATCH");
  }

  const submitRemaining = _pr92RemainingTurnMs(context, "PAGE_GUARDED_SUBMIT");
  if (submitRemaining <= PR92_PAGE_SUBMIT_DEADLINE_SAFETY_MS) {
    throw new Error("PR9_2_TOTAL_TURN_TIMEOUT:PAGE_GUARDED_SUBMIT_RESERVE");
  }
  const pageDeadlineEpochMs = Date.now() +
    submitRemaining - PR92_PAGE_SUBMIT_DEADLINE_SAFETY_MS;

  const result = await _pr92DeadlineRepairRunUntil(
    context.deadlineAt,
    "PAGE_GUARDED_SUBMIT",
    () => chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr92ClosurePageGuardedSubmitExpression(
        selector,
        pageDeadlineEpochMs
      ),
      returnByValue: true,
      awaitPromise: true
    })
  );
  const value = result?.result?.value;
  if (value?.clicked !== true) {
    if (value?.reason === "deadline-expired") {
      throw new Error("PR9_2_TOTAL_TURN_TIMEOUT:PAGE_GUARDED_SUBMIT_PAGE_DEADLINE");
    }
    throw new Error(`PR9_2_PAGE_GUARDED_SUBMIT_FAILED:${value?.reason || 'unknown'}`);
  }
  return { strategy: "page_deadline_guarded_send_button_click", selector };
};

executeNativeTurn = async function _executeNativeTurnWithPr92ClosureRepair(message) {
  const result = await _pr92ClosurePriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport === true) {
    return {
      ...result,
      richInputSchemaVersion: PR92_CLOSURE_REPAIR_SCHEMA,
      attachmentCountEvidence: PR92_PAGE_ATTACHMENT_EVIDENCE_SOURCE,
      attachmentEvidenceStablePollCount: PR92_PAGE_ATTACHMENT_STABLE_POLLS,
      preSubmitAttachmentRevalidation: true,
      postSendReadinessAttachmentRevalidation: true,
      protectedSubmitPrimitive: PR92_PAGE_GUARDED_SUBMIT_PRIMITIVE,
      richInputRawCdpInputSubmitDisabled: true,
      richInputEnterFallbackEnabled: false,
      lateProtectedSubmitExecutionPreventedByPageDeadline: true
    };
  }

  if (
    Array.isArray(message?.attachmentPaths) &&
    message.attachmentPaths.length > 0 &&
    result &&
    typeof result === "object"
  ) {
    return {
      ...result,
      attachmentEvidenceSource: PR92_PAGE_ATTACHMENT_EVIDENCE_SOURCE
    };
  }
  return result;
};
