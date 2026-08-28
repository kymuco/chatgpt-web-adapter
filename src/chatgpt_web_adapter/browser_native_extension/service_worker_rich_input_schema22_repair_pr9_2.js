// PR9.2 schema-22 live composer attachment-evidence classification repair.
//
// Loaded after schema 21. The first authenticated schema-21 live attempt failed
// closed before staging because the current ChatGPT composer exposes ordinary
// visible role=group/aria-label controls. Schema 11 treated every such group as
// attachment evidence, so a genuinely attachment-clean fresh composer was
// classified as dirty.
//
// Schema 22 keeps the exact-set / cross-channel / literal-basename authority but
// narrows role-group evidence to structurally attachment-owned groups: a group is
// eligible only when it contains a visible remove/delete/discard control. Global
// structured removal controls remain an independent evidence channel, so a manual
// or stale attachment still blocks pre-stage cleanliness even if its filename
// group is absent or arranged differently by the page.

const _pr92Schema22PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA22_REPAIR_SCHEMA = 22;

function _pr92Schema22AttachmentEvidenceExpression(expectedNames) {
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
        ignoredComposerGroupLabelCount: 0,
        removalLabelCount: 0,
        exactAttachmentSet: false,
        crossEvidenceChannelExact: false,
        officialComposerMounted: false,
        exactBasenameAssociation: false,
        structuredRemovalBasenameAssociation: false,
        attachmentOwnedRoleGroupsOnly: true,
        evidenceKind: 'official-composer-missing'
      };
    }

    const normalize = (value) => typeof value === 'string' ? value.trim() : '';
    const isStructuredRemovalLabel = (label) =>
      /^(remove|delete|discard|удалить)(?:\\s+|:\\s*)/i.test(normalize(label));
    const removalControlSelector = 'button[aria-label], [role="button"][aria-label]';
    const hasVisibleStructuredRemovalControl = (group) =>
      Array.from(group.querySelectorAll(removalControlSelector))
        .filter(isVisible)
        .some((element) => isStructuredRemovalLabel(element.getAttribute('aria-label')));

    const rawGroupElements = Array.from(composer.querySelectorAll('[role="group"][aria-label]'))
      .filter(isVisible);
    const groupLabels = rawGroupElements
      .filter(hasVisibleStructuredRemovalControl)
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter(Boolean);
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
      ignoredComposerGroupLabelCount: Math.max(0, rawGroupElements.length - groupLabels.length),
      removalLabelCount: removalLabels.length,
      exactAttachmentSet,
      crossEvidenceChannelExact,
      officialComposerMounted: true,
      exactBasenameAssociation: true,
      structuredRemovalBasenameAssociation: true,
      attachmentOwnedRoleGroupsOnly: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-attachment-owned-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-structured-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// All pre-stage clean polls, post-stage stable evidence reads, and schema-7's
// final synchronous validate+click resolve this binding at call time. Therefore
// the classification repair is consistent across every attachment authority
// boundary rather than being a special-case live-gate bypass.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema22AttachmentEvidenceExpression;

executeNativeTurn = async function _executeNativeTurnWithPr92Schema22Repair(message) {
  const result = await _pr92Schema22PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA22_REPAIR_SCHEMA,
    attachmentEvidenceRoleGroupsRequireRemovalControl: true,
    composerControlRoleGroupsExcludedFromAttachmentEvidence: true,
    preStageCleanUsesAttachmentOwnedEvidenceOnly: true
  };
};
