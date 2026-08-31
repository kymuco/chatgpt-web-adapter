// PR9.2 schema-10 official-composer / basename / pre-stage deadline repair.
//
// Loaded after schema 9. This layer closes three fresh closure-review findings:
//   1. page-owned attachment evidence is unavailable until the official prompt
//      composer is mounted; document.body or an arbitrary form is never clean proof;
//   2. requested basenames are associated without substring aliases such as
//      report.txt <- old-report.txt;
//   3. pre-stage debugger attach/Runtime.enable are bounded by the one outer rich
//      turn deadline, and a late attach completion is followed by best-effort detach.

const _pr92Schema10PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA10_REPAIR_SCHEMA = 10;
const PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS = 2;

function _pr92Schema10AttachmentEvidenceExpression(expectedNames) {
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
      document.querySelector('[data-testid="prompt-textarea"]');
    const composer = prompt instanceof Element ? prompt.closest('form') : null;
    if (!(prompt instanceof Element) || !(composer instanceof Element)) {
      return {
        ready: false,
        rejected: false,
        matchedCount: 0,
        groupLabelCount: 0,
        removalLabelCount: 0,
        exactAttachmentSet: false,
        crossEvidenceChannelExact: false,
        officialComposerMounted: false,
        exactBasenameAssociation: false,
        evidenceKind: 'official-composer-missing'
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

    const exactGroupBasename = (label, name) => label === name;
    const exactRemovalBasename = (label, name) => {
      if (label === name) return true;
      if (!label.endsWith(name)) return false;
      const prefix = label.slice(0, label.length - name.length);
      if (!prefix) return true;
      // A whole-basename association may be preceded by whitespace or UI quoting,
      // but never by filename characters such as '-', '_', '.', or alphanumerics.
      return /[\\s\"'(:\\[]$/.test(prefix);
    };

    const matchesExpectedExactly = (labels, matcher) => {
      const pool = labels.slice();
      let matched = 0;
      for (const name of expected) {
        const index = pool.findIndex((label) => matcher(label, name));
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

    const groups = matchesExpectedExactly(groupLabels, exactGroupBasename);
    const removals = matchesExpectedExactly(removalLabels, exactRemovalBasename);
    const groupsCompatible = groupLabels.length === 0 || groups.exact;
    const removalsCompatible = removalLabels.length === 0 || removals.exact;
    const atLeastOneExpectedChannelExact = groups.exact || removals.exact;
    const crossEvidenceChannelExact = expected.length === 0
      ? groups.exact && removals.exact
      : groupsCompatible && removalsCompatible && atLeastOneExpectedChannelExact;
    const exactAttachmentSet = crossEvidenceChannelExact;
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
      crossEvidenceChannelExact,
      officialComposerMounted: true,
      exactBasenameAssociation: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// Every schema-8/9 clean/stable read and schema-7 atomic final validation resolves
// this binding at call time, so all later evidence uses schema-10 semantics.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema10AttachmentEvidenceExpression;

function _pr92Schema10BestEffortDetach(debuggee) {
  try {
    const pending = chrome.debugger.detach(debuggee);
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {}
}

async function _pr92Schema10RequireOfficialCleanComposerBeforeStaging(tabId, context) {
  const debuggee = { tabId };
  let attached = false;
  let attachPending = null;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA10_PRESTAGE_CLEAN_ATTACH");
    try {
      attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    } catch (error) {
      throw error;
    }
    if (attachPending && typeof attachPending.catch === "function") {
      attachPending.catch(() => {});
    }
    try {
      await _pr92Schema7RunUntil(
        context.deadlineAt,
        "SCHEMA10_PRESTAGE_CLEAN_DEBUGGER_ATTACH",
        () => attachPending
      );
      attached = true;
    } catch (error) {
      // Runtime debugger commands are not cancellable. If the attach itself wins
      // after our deadline race already failed, immediately relinquish that late
      // ownership instead of leaving the next turn blocked by a ghost attachment.
      if (attachPending && typeof attachPending.then === "function") {
        attachPending.then(
          () => _pr92Schema10BestEffortDetach(debuggee),
          () => {}
        );
      }
      throw error;
    }

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA10_PRESTAGE_CLEAN_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    let stable = 0;
    while (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
      const evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
        debuggee,
        [],
        context
      );
      const groupCount = Number(evidence?.groupLabelCount);
      const removalCount = Number(evidence?.removalLabelCount);
      const clean = evidence?.officialComposerMounted === true &&
        evidence?.exactBasenameAssociation === true &&
        evidence?.exactAttachmentSet === true &&
        groupCount === 0 && removalCount === 0;
      if (!clean) {
        throw new Error("PR9_2_OFFICIAL_COMPOSER_NOT_CLEAN_BEFORE_STAGING");
      }
      stable += 1;
      if (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA10_PRESTAGE_CLEAN_STABILITY"
        );
      }
    }
  } finally {
    if (attached) _pr92Schema10BestEffortDetach(debuggee);
  }
}

// Bypass only schema 8's unbounded pre-stage wrapper. The captured schema-8 prior
// points to the already-governed staging implementation before schema 8 was loaded.
_pr92StageOfficialPageAttachments = async function _pr92Schema10StageFromOfficialCleanComposer(
  tabId,
  attachmentPaths,
  context
) {
  if (attachmentPaths.length === 0) return 0;
  await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(tabId, context);
  return _pr92Schema8PriorStageOfficialPageAttachments(tabId, attachmentPaths, context);
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema10Repair(message) {
  const result = await _pr92Schema10PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA10_REPAIR_SCHEMA,
    officialComposerRequiredForAttachmentEvidence: true,
    exactBasenameAssociationRequired: true,
    preStageDebuggerSetupDeadlineBounded: true,
    latePreStageDebuggerAttachAutoDetached: true
  };
};
