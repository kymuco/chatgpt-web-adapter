// PR9.2 live composer-evidence diagnostic overlay.
//
// Diagnostic-only. This file does not change the advertised rich-input schema or
// any attachment/write authority. It exposes one explicit no-write RPC that reads
// the current official composer DOM and executes the same schema-24 production
// mount wait + empty-set clean proof used before attachment staging.

const _pr92Schema23DiagnosticPriorExecuteNativeTurn = executeNativeTurn;

function _pr92Schema23DiagnosticBestEffortDetach(debuggee) {
  try {
    const pending = chrome.debugger.detach(debuggee);
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

function _pr92Schema23DiagnosticExpression() {
  return `(() => {
    const normalize = (value) => typeof value === 'string' ? value.trim() : '';
    const isVisible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const prompt = document.querySelector('#prompt-textarea') ||
      document.querySelector('[data-testid="prompt-textarea"]');
    const composer = prompt instanceof Element ? prompt.closest('form') : null;
    if (!(prompt instanceof Element) || !(composer instanceof Element)) {
      return {
        officialComposerMounted: false,
        groups: [],
        buttons: []
      };
    }

    const stableComposerSelectors = [
      'button[data-testid="composer-plus-btn"]',
      'button[data-testid="composer-button-add-files"]',
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]'
    ];
    const classifyGroup = (group) => {
      const stableControls = stableComposerSelectors
        .filter((selector) => group.querySelector(selector) instanceof Element);
      const descendants = Array.from(
        group.querySelectorAll('button, [role="button"], [data-testid]')
      ).slice(0, 20).map((element) => ({
        tag: element.tagName.toLowerCase(),
        role: normalize(element.getAttribute('role')) || null,
        ariaLabel: normalize(element.getAttribute('aria-label')) || null,
        testId: normalize(element.getAttribute('data-testid')) || null,
        visible: isVisible(element)
      }));
      return {
        ariaLabel: normalize(group.getAttribute('aria-label')) || null,
        tag: group.tagName.toLowerCase(),
        testId: normalize(group.getAttribute('data-testid')) || null,
        className: typeof group.className === 'string' ? group.className.slice(0, 300) : null,
        containsPrompt: group.contains(prompt),
        stableComposerControls: stableControls,
        schema23ExcludedAsComposerControl:
          group.contains(prompt) || stableControls.length > 0,
        text: normalize(group.textContent).slice(0, 300),
        descendants
      };
    };

    const groups = Array.from(composer.querySelectorAll('[role="group"][aria-label]'))
      .filter(isVisible)
      .map(classifyGroup);
    const buttons = Array.from(
      composer.querySelectorAll('button[aria-label], [role="button"][aria-label], button[data-testid]')
    ).filter(isVisible).slice(0, 40).map((element) => ({
      tag: element.tagName.toLowerCase(),
      role: normalize(element.getAttribute('role')) || null,
      ariaLabel: normalize(element.getAttribute('aria-label')) || null,
      testId: normalize(element.getAttribute('data-testid')) || null,
      text: normalize(element.textContent).slice(0, 160)
    }));

    return {
      officialComposerMounted: true,
      promptTag: prompt.tagName.toLowerCase(),
      promptTestId: normalize(prompt.getAttribute('data-testid')) || null,
      composerClassName: typeof composer.className === 'string' ? composer.className.slice(0, 300) : null,
      visibleRoleGroupCount: groups.length,
      schema23RetainedRoleGroupCount: groups.filter((group) => !group.schema23ExcludedAsComposerControl).length,
      groups,
      buttons
    };
  })()`;
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema23Diagnostic(message) {
  if (message?.diagnosePr92ComposerEvidence !== true) {
    return _pr92Schema23DiagnosticPriorExecuteNativeTurn(message);
  }
  if (message?.text != null || message?.attachmentPaths != null) {
    throw new Error("PR9_2_COMPOSER_DIAGNOSTIC_MUST_BE_NO_WRITE");
  }

  const timeoutMs = Number.isFinite(message?.timeoutMs)
    ? Math.max(1_000, Math.min(Number(message.timeoutMs), 30_000))
    : 10_000;
  const context = {
    deadlineAt: performance.now() + timeoutMs
  };
  const tab = await _pr92Schema7RunUntil(
    context.deadlineAt,
    "SCHEMA24_DIAGNOSTIC_RUNTIME_TAB",
    () => ensureRuntimeTab(null)
  );
  if (!Number.isInteger(tab?.id)) throw new Error("CHATGPT_RUNTIME_TAB_MISSING_ID");

  const debuggee = { tabId: tab.id };
  let attached = false;
  try {
    attached = await _pr92Schema13AttachWithinDeadline(debuggee, context);
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA24_DIAGNOSTIC_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    // Exact schema-24 production dry-run: use the production mount wait and then
    // apply the production clean predicate to the mount evidence plus the second
    // stable poll. No text, files, staging, focus mutation, or submit is involved.
    let evidence = await _pr92Schema24WaitForOfficialComposerMounted(debuggee, context);
    const productionPolls = [];
    let stable = 0;
    while (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
      const clean = _pr92Schema24EvidenceIsClean(evidence);
      productionPolls.push({ index: stable, clean, evidence });
      if (!clean) break;
      stable += 1;
      if (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA24_DIAGNOSTIC_PRODUCTION_CLEAN_STABILITY"
        );
        evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
          debuggee,
          [],
          context
        );
      }
    }

    const evaluated = await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA24_DIAGNOSTIC_EVIDENCE_READ",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
        expression: _pr92Schema23DiagnosticExpression(),
        returnByValue: true,
        awaitPromise: false
      })
    );
    const result = {
      diagnosticOnly: true,
      writePerformed: false,
      attachmentStagingPerformed: false,
      protectedSubmitAttempted: false,
      richInputSchemaVersion: PR92_SCHEMA24_REPAIR_SCHEMA,
      tabId: tab.id,
      productionCleanProof: {
        stablePollsRequired: PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS,
        allPollsClean: stable === PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS,
        polls: productionPolls
      },
      evidence: evaluated?.result?.value || null
    };

    // A successful diagnostic is not complete until debugger ownership has been
    // relinquished. Otherwise the immediately following real turn can race a
    // still-pending detach and fail its own attach despite a valid clean proof.
    await _pr92Schema15DetachWithinDeadline(
      debuggee,
      context,
      "SCHEMA24_DIAGNOSTIC_DEBUGGER_DETACH"
    );
    attached = false;
    return result;
  } finally {
    // Failure/timeout cleanup remains best-effort and cannot extend/rewrite the
    // already failed diagnostic outcome.
    if (attached) _pr92Schema23DiagnosticBestEffortDetach(debuggee);
  }
};
