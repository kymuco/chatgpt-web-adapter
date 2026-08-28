// PR9.2 schema-25 indexed removal-label normalization repair.
//
// Loaded after schema 24 and the diagnostic overlay. Authenticated schema-24 live
// validation proved staging succeeded and the real current UI exposed both exact
// filename-group evidence and a localized removal control:
//
//   role-group aria-label:  pr9_2_attachment_evidence.png
//   removal aria-label:     Удалить файл 1: pr9_2_attachment_evidence.png
//
// Schema 23 deliberately treated the two channels independently and required them
// to agree exactly, but its literal removal parser only stripped the action verb.
// It therefore compared `файл 1: <basename>` with `<basename>`, never reached exact
// cross-channel evidence, and timed out before any protected submit.
//
// Schema 25 keeps the same exact-set / cross-channel authority. It strips only an
// anchored, recognized UI metadata prefix consisting of a known file-like noun, a
// decimal ordinal, and a colon. Unknown wording remains part of the candidate and
// therefore fails exact basename comparison closed. No substring/suffix matching,
// write retry, fallback transport, or new submit authority is introduced.

const _pr92Schema25PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA25_REPAIR_SCHEMA = 25;

function _pr92Schema25RemovalControlBasename(label) {
  const normalize = (value) => typeof value === "string" ? value.trim() : "";
  const value = normalize(label);
  const action = value.match(/^(?:remove|delete|discard|удалить)(?:\s+|:\s*)/i);
  if (!action) return "";

  const payload = value.slice(action[0].length).trim();
  const indexedUiPrefix = payload.match(
    /^(?:file|image|attachment|document|файл|изображение|вложение|документ)\s+\d+\s*:\s*(.+)$/i
  );
  if (indexedUiPrefix) return normalize(indexedUiPrefix[1]);
  return payload;
}

function _pr92Schema25AttachmentEvidenceExpression(expectedNames) {
  const encodedNames = JSON.stringify(expectedNames);
  const removalParser = _pr92Schema25RemovalControlBasename.toString();
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
        indexedRemovalUiPrefixNormalized: true,
        evidenceKind: 'official-composer-missing'
      };
    }

    const normalize = (value) => typeof value === 'string' ? value.trim() : '';
    const isStructuredRemovalLabel = (label) =>
      /^(remove|delete|discard|удалить)(?:\\s+|:\\s*)/i.test(normalize(label));
    const removalControlSelector = 'button[aria-label], [role="button"][aria-label]';

    const officialComposerControlSelectors = [
      'button[data-testid="composer-plus-btn"]',
      'button[data-testid="composer-button-add-files"]',
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]'
    ];
    const isOfficialComposerControlGroup = (group) => {
      if (!(group instanceof Element)) return false;
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

    const removalLabels = Array.from(composer.querySelectorAll(removalControlSelector))
      .filter(isVisible)
      .map((element) => normalize(element.getAttribute('aria-label')))
      .filter(isStructuredRemovalLabel);

    const exactGroupBasename = (label, name) => label === name;
    const removalControlBasename = ${removalParser};
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
      indexedRemovalUiPrefixNormalized: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-independent-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-structured-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// The same dynamically bound expression is consumed by pre-stage cleanliness,
// post-stage stable evidence, revalidation after Send readiness, and schema-7's
// synchronous atomic validate+click boundary.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema25AttachmentEvidenceExpression;

function _pr92Schema25DiagnosticRemovalNormalization(result) {
  const groups = Array.isArray(result?.evidence?.groups)
    ? result.evidence.groups
        .filter((group) => group?.schema23ExcludedAsComposerControl !== true)
        .map((group) => typeof group?.ariaLabel === "string" ? group.ariaLabel.trim() : "")
        .filter(Boolean)
    : [];
  const buttons = Array.isArray(result?.evidence?.buttons) ? result.evidence.buttons : [];
  const removals = buttons
    .map((button) => typeof button?.ariaLabel === "string" ? button.ariaLabel.trim() : "")
    .filter((label) => /^(remove|delete|discard|удалить)(?:\s+|:\s*)/i.test(label))
    .map((label) => ({
      label,
      basename: _pr92Schema25RemovalControlBasename(label)
    }));
  const singleAttachmentCrossChannelExact =
    groups.length === 1 &&
    removals.length === 1 &&
    removals[0].basename === groups[0];
  return {
    groupBasenames: groups,
    removalControls: removals,
    singleAttachmentCrossChannelExact
  };
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema25Repair(message) {
  const result = await _pr92Schema25PriorExecuteNativeTurn(message);

  if (message?.diagnosePr92ComposerEvidence === true && result && typeof result === "object") {
    return {
      ...result,
      richInputSchemaVersion: PR92_SCHEMA25_REPAIR_SCHEMA,
      schema25RemovalNormalizationProof: _pr92Schema25DiagnosticRemovalNormalization(result)
    };
  }

  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA25_REPAIR_SCHEMA,
    indexedRemovalUiPrefixNormalizationSupported: true,
    indexedRemovalUiPrefixRequiresKnownNounOrdinalAndColon: true,
    indexedRemovalUiPrefixBasenameComparedExactly: true,
    unknownRemovalUiMetadataStillFailsClosed: true,
    removalNormalizationSharedByProductionAndDiagnostic: true
  };
};
