// PR9.2 schema-9 exact-evidence repair.
//
// Schema 8 correctly required a clean composer before staging and exactness within
// each page-owned evidence channel, but its final OR allowed one exact channel to
// mask a different non-exact channel. Example: groupLabels=[requested] and
// removalLabels=[extra] could still satisfy groups.exact || removals.exact.
// Schema 9 requires every non-empty evidence channel to be exact, so no observed
// extra/partial attachment evidence can be hidden by another channel.

const _pr92Schema9PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA9_REPAIR_SCHEMA = 9;

function _pr92Schema9AttachmentEvidenceExpression(expectedNames) {
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
        crossEvidenceChannelExact: false,
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
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// This late override is consumed dynamically by schema 8 pre-stage checks,
// post-stage stable evidence, and schema 7's synchronous atomic final validator.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema9AttachmentEvidenceExpression;

executeNativeTurn = async function _executeNativeTurnWithPr92Schema9Repair(message) {
  const result = await _pr92Schema9PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA9_REPAIR_SCHEMA,
    crossEvidenceChannelExactness: true
  };
};
