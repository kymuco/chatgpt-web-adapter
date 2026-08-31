// PR9.2 schema-23 independent filename-evidence / composer-control exclusion repair.
//
// Loaded after schema 22. Schema 22 fixed a real current-UI false positive by
// retaining role=group filename evidence only when the group contained a visible,
// recognized remove control. That made the filename channel depend on the removal
// channel and could hide a stale/manual attachment whose remove affordance was a
// sibling, hover-hidden, or differently localized.
//
// Schema 23 restores the filename role-group channel as independent authority.
// Instead of positively identifying attachments through remove controls, it
// excludes only role groups that are structurally proven to be ordinary official
// composer controls. Every other visible labelled role group is conservatively
// retained as attachment evidence. Therefore unknown/unclassified UI fails closed,
// while the current composer's prompt/control groups no longer create the schema-21
// clean-composer false positive. Structured removal controls remain a second,
// independent evidence channel exactly as before.

const _pr92Schema23PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA23_REPAIR_SCHEMA = 23;

function _pr92Schema23AttachmentEvidenceExpression(expectedNames) {
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
        rawGroupLabelCount: 0,
        excludedComposerControlGroupCount: 0,
        removalLabelCount: 0,
        exactAttachmentSet: false,
        crossEvidenceChannelExact: false,
        officialComposerMounted: false,
        exactBasenameAssociation: false,
        structuredRemovalBasenameAssociation: false,
        filenameGroupIndependentOfRemovalControl: true,
        unknownRoleGroupsFailClosed: true,
        evidenceKind: 'official-composer-missing'
      };
    }

    const normalize = (value) => typeof value === 'string' ? value.trim() : '';
    const isStructuredRemovalLabel = (label) =>
      /^(remove|delete|discard|удалить)(?:\\s+|:\\s*)/i.test(normalize(label));
    const removalControlSelector = 'button[aria-label], [role="button"][aria-label]';

    // These selectors identify stable official composer actions already used by
    // the browser-owned runtime itself. A group is excluded only when structural
    // containment proves that it belongs to those controls; aria-label wording is
    // deliberately not used as an allowlist, so localization cannot turn an
    // unknown filename group into an ignored group.
    const officialComposerControlSelectors = [
      'button[data-testid="composer-plus-btn"]',
      'button[data-testid="composer-button-add-files"]',
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]'
    ];
    const isOfficialComposerControlGroup = (group) => {
      if (!(group instanceof Element)) return false;
      // A labelled group that wraps the prompt editor is composer chrome, not an
      // attachment chip. Attachment groups cannot legitimately contain the one
      // official prompt editor used to define this composer.
      if (group.contains(prompt)) return true;
      return officialComposerControlSelectors.some((selector) =>
        group.querySelector(selector) instanceof Element
      );
    };

    const rawGroupElements = Array.from(composer.querySelectorAll('[role="group"][aria-label]'))
      .filter(isVisible);
    const attachmentGroupElements = rawGroupElements
      .filter((element) => !isOfficialComposerControlGroup(element));
    const groupLabels = attachmentGroupElements
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter(Boolean);

    // Keep removal evidence independent from role-group evidence. A removal
    // control may be nested, sibling-arranged, or the only structured channel.
    const removalLabels = Array.from(composer.querySelectorAll(removalControlSelector))
      .filter(isVisible)
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter(isStructuredRemovalLabel);

    const exactGroupBasename = (label, name) => label === name;
    const removalControlBasename = (label) => {
      const value = normalize(label);
      const action = value.match(/^(?:remove|delete|discard|удалить)(?:\\s+|:\\s*)/i);
      if (!action) return '';
      return value.slice(action[0].length).trim();
    };
    const exactRemovalBasename = (label, name) => removalControlBasename(label) === name;

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
      rawGroupLabelCount: rawGroupElements.length,
      excludedComposerControlGroupCount: Math.max(
        0,
        rawGroupElements.length - attachmentGroupElements.length
      ),
      removalLabelCount: removalLabels.length,
      exactAttachmentSet,
      crossEvidenceChannelExact,
      officialComposerMounted: true,
      exactBasenameAssociation: true,
      structuredRemovalBasenameAssociation: true,
      filenameGroupIndependentOfRemovalControl: true,
      unknownRoleGroupsFailClosed: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-independent-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-structured-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// Pre-stage clean polls, post-stage stable evidence, and schema-7's final atomic
// validate+click all resolve this binding dynamically. The same conservative
// classification therefore governs every attachment-authority boundary.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema23AttachmentEvidenceExpression;

executeNativeTurn = async function _executeNativeTurnWithPr92Schema23Repair(message) {
  const result = await _pr92Schema23PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA23_REPAIR_SCHEMA,
    // Explicitly supersede schema 22's too-strong ownership claim.
    attachmentEvidenceRoleGroupsRequireRemovalControl: false,
    attachmentFilenameGroupsIndependentOfRemovalControls: true,
    composerControlGroupExclusionUsesStructure: true,
    unclassifiedRoleGroupsFailClosedAsAttachmentEvidence: true,
    composerControlRoleGroupsExcludedFromAttachmentEvidence: true,
    preStageCleanUsesAttachmentOwnedEvidenceOnly: true
  };
};
