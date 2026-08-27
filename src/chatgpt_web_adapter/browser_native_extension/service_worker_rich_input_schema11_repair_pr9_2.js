// PR9.2 schema-11 structured-basename / evidence-read deadline repair.
//
// Loaded after schema 10. This immutable layer closes the two fresh final-review
// findings without weakening any earlier rich-input authority contract:
//   1. removal-control evidence is parsed as a complete action payload and the
//      resulting basename must equal the requested basename exactly; suffix
//      aliases such as report.txt <- "Remove old report.txt" are impossible;
//   2. every page-owned attachment evidence read is raced against the one outer
//      rich-turn deadline instead of awaiting a raw Runtime.evaluate indefinitely.

const _pr92Schema11PriorExecuteNativeTurn = executeNativeTurn;
const _pr92Schema11PriorReadPageOwnedAttachmentEvidence =
  _pr92ClosureReadPageOwnedAttachmentEvidence;
const PR92_SCHEMA11_REPAIR_SCHEMA = 11;

function _pr92Schema11AttachmentEvidenceExpression(expectedNames) {
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
        structuredRemovalBasenameAssociation: false,
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
      .filter((label) => /^(remove|delete|discard|удалить)(?:\\s+|:\\s*)/i.test(label));

    const exactGroupBasename = (label, name) => label === name;
    const removalControlBasename = (label) => {
      let value = normalize(label);
      const action = value.match(/^(?:remove|delete|discard|удалить)(?:\\s+|:\\s*)/i);
      if (!action) return '';
      value = value.slice(action[0].length).trim();
      if (value.length >= 2) {
        const first = value[0];
        const last = value[value.length - 1];
        const paired = (first === '\"' && last === '\"') ||
          (first === "'" && last === "'") ||
          (first === '“' && last === '”') ||
          (first === '‘' && last === '’');
        if (paired) value = value.slice(1, -1).trim();
      }
      return value;
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
      removalLabelCount: removalLabels.length,
      exactAttachmentSet,
      crossEvidenceChannelExact,
      officialComposerMounted: true,
      exactBasenameAssociation: true,
      structuredRemovalBasenameAssociation: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-structured-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// Schema-7 atomic submit and every schema-8/9/10 evidence poll resolve this
// binding at call time, so the structured association is authoritative everywhere.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema11AttachmentEvidenceExpression;

// Bound the shared evidence-read primitive itself. The historical implementation
// performs the Runtime.evaluate and value-shape validation; schema 11 only adds the
// missing outer-deadline race around that complete read. A late DOM read has no
// write authority and cannot change the already-reported timeout outcome.
_pr92ClosureReadPageOwnedAttachmentEvidence = async function _pr92Schema11ReadPageOwnedAttachmentEvidence(
  debuggee,
  expectedNames,
  context
) {
  return _pr92Schema7RunUntil(
    context.deadlineAt,
    "SCHEMA11_PAGE_ATTACHMENT_EVIDENCE_READ",
    () => _pr92Schema11PriorReadPageOwnedAttachmentEvidence(
      debuggee,
      expectedNames,
      context
    )
  );
};

executeNativeTurn = async function _executeNativeTurnWithPr92Schema11Repair(message) {
  const result = await _pr92Schema11PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA11_REPAIR_SCHEMA,
    structuredRemovalControlBasenameParsing: true,
    attachmentEvidenceReadsDeadlineBounded: true
  };
};
