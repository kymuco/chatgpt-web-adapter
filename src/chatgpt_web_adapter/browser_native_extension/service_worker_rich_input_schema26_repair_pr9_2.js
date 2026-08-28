// PR9.2 schema-26 ambiguity-safe indexed removal-label repair.
//
// Loaded after schema 25. Schema 25 correctly recognized the current localized UI
// form `Удалить файл 1: <basename>`, but it stripped the indexed noun/ordinal prefix
// unconditionally. That is ambiguous because a legitimate filename may itself be
// `file 1: report.txt`. Schema 26 therefore restores literal post-action payload
// semantics first and permits indexed-prefix interpretation only when an independent
// filename role-group corroborates the derived basename exactly.
//
// Consequences:
//   * `Remove file 1: report.txt` still proves the literal filename
//     `file 1: report.txt` in a removal-only layout;
//   * the same label may prove `report.txt` only when an independent visible
//     filename group is exactly `report.txt`;
//   * ambiguous indexed removal-only evidence for `report.txt` fails closed;
//   * exact-set, cross-channel, staging, deadline, fence, request-correlation and
//     protected-submit authority are otherwise unchanged.

const _pr92Schema26PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA26_REPAIR_SCHEMA = 26;

function _pr92Schema26RemovalPostActionPayload(label) {
  const normalize = (value) => typeof value === "string" ? value.trim() : "";
  const value = normalize(label);
  const action = value.match(/^(?:remove|delete|discard|удалить)(?:\s+|:\s*)/i);
  if (!action) return "";
  return normalize(value.slice(action[0].length));
}

function _pr92Schema26IndexedRemovalCandidate(payload) {
  const normalize = (value) => typeof value === "string" ? value.trim() : "";
  const value = normalize(payload);
  const indexedUiPrefix = value.match(
    /^(?:file|image|attachment|document|файл|изображение|вложение|документ)\s+\d+\s*:\s*(.+)$/i
  );
  return indexedUiPrefix ? normalize(indexedUiPrefix[1]) : "";
}

function _pr92Schema26AttachmentEvidenceExpression(expectedNames) {
  const encodedNames = JSON.stringify(expectedNames);
  const payloadParser = _pr92Schema26RemovalPostActionPayload.toString();
  const indexedParser = _pr92Schema26IndexedRemovalCandidate.toString();
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
        indexedRemovalUiPrefixRequiresIndependentFilenameGroup: true,
        removalOnlyIndexedUiPrefixNormalizationAllowed: false,
        literalPostActionRemovalBasenamePreserved: true,
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
    const removalPostActionPayload = ${payloadParser};
    const indexedRemovalCandidate = ${indexedParser};
    const exactRemovalBasename = (label, name) => {
      const payload = removalPostActionPayload(label);
      if (payload === name) return true;
      const candidate = indexedRemovalCandidate(payload);
      return candidate === name && groupLabels.includes(candidate);
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
      indexedRemovalUiPrefixRequiresIndependentFilenameGroup: true,
      removalOnlyIndexedUiPrefixNormalizationAllowed: false,
      literalPostActionRemovalBasenamePreserved: true,
      evidenceKind: groups.exact && removals.exact ? 'exact-both-evidence-channels' :
        (groups.exact && removalLabels.length === 0 ? 'exact-independent-role-group-channel' :
          (removals.exact && groupLabels.length === 0 ? 'exact-structured-remove-control-channel' : 'not-ready'))
    };
  })()`;
}

// All authority boundaries resolve this binding dynamically: pre-stage clean,
// post-stage stable evidence, pre-submit revalidation, and the atomic click task.
_pr92ClosureAttachmentEvidenceExpression = _pr92Schema26AttachmentEvidenceExpression;

function _pr92Schema26DiagnosticRemovalNormalization(result) {
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
    .map((label) => {
      const literalBasename = _pr92Schema26RemovalPostActionPayload(label);
      const indexedCandidate = _pr92Schema26IndexedRemovalCandidate(literalBasename);
      const corroboratedIndexedBasename =
        indexedCandidate && groups.includes(indexedCandidate) ? indexedCandidate : null;
      return {
        label,
        literalBasename,
        indexedCandidate: indexedCandidate || null,
        corroboratedIndexedBasename
      };
    });
  const singleAttachmentCrossChannelExact = groups.length === 1 && removals.length === 1 && (
    removals[0].literalBasename === groups[0] ||
    removals[0].corroboratedIndexedBasename === groups[0]
  );
  return {
    groupBasenames: groups,
    removalControls: removals,
    singleAttachmentCrossChannelExact
  };
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema26Repair(message) {
  const result = await _pr92Schema26PriorExecuteNativeTurn(message);

  if (message?.diagnosePr92ComposerEvidence === true && result && typeof result === "object") {
    return {
      ...result,
      richInputSchemaVersion: PR92_SCHEMA26_REPAIR_SCHEMA,
      schema26RemovalNormalizationProof: _pr92Schema26DiagnosticRemovalNormalization(result)
    };
  }

  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA26_REPAIR_SCHEMA,
    indexedRemovalUiPrefixRequiresIndependentFilenameGroup: true,
    removalOnlyIndexedUiPrefixNormalizationAllowed: false,
    literalPostActionRemovalBasenamePreserved: true,
    ambiguousIndexedRemovalLabelFailsClosedWithoutFilenameGroup: true,
    indexedRemovalCandidateStillComparedExactly: true
  };
};
