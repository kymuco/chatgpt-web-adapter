// PR10.1: bounded, read-only frontend surface characterization for a generated
// artifact that was already created by a prior product turn. This layer does not
// type, submit, click, download, export DOM/text, or expose locator/attribute values.
// Exact probe-filename matches count as artifact-surface evidence only when the
// containing visible turn proves assistant ownership; user/unknown-role matches are
// counted separately and excluded from evidence.

const PR101_ARTIFACT_SURFACE_SCHEMA = 1;
const PR101_ARTIFACT_SURFACE_PROBE_FILENAME = "cwa_pr10_1_probe.txt";
const _pr101ArtifactSurfacePriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactSurfaceRejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactSurfaceExpression() {
  return `(() => {
    const probeFilename = 'cwa_pr10_1_probe.txt';
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const safeAttributeNames = (element) => {
      if (!(element instanceof Element)) return [];
      return Array.from(element.attributes || [])
        .map((attribute) => String(attribute?.name || '').trim())
        .filter((name) => /^[A-Za-z0-9_.:-]{1,80}$/.test(name))
        .slice(0, 64);
    };
    const addNames = (set, names) => {
      for (const name of names) {
        if (set.size >= 96) break;
        set.add(name);
      }
    };
    const turnRole = (turn) => {
      if (!(turn instanceof Element)) return { role: null, evidence: null };
      const dataTurn = String(turn.getAttribute('data-turn') || '').trim();
      if (dataTurn === 'assistant' || dataTurn === 'user') {
        return { role: dataTurn, evidence: 'data_turn' };
      }
      const directAuthor = String(turn.getAttribute('data-message-author-role') || '').trim();
      if (directAuthor === 'assistant' || directAuthor === 'user') {
        return { role: directAuthor, evidence: 'direct_message_author_role' };
      }
      const roleNode = turn.querySelector(
        '[data-message-author-role="assistant"],[data-message-author-role="user"]'
      );
      const nestedAuthor = String(roleNode?.getAttribute?.('data-message-author-role') || '').trim();
      if (nestedAuthor === 'assistant' || nestedAuthor === 'user') {
        return { role: nestedAuthor, evidence: 'nested_message_author_role' };
      }
      return { role: null, evidence: null };
    };

    const main = document.querySelector('main');
    if (!main) {
      return {
        surfaceReady: false,
        exactFilenameVisible: false,
        exactFilenameMatchCount: 0,
        anyExactFilenameMatchCount: 0,
        userOwnedExactFilenameMatchCount: 0,
        roleUnprovenExactFilenameMatchCount: 0,
        assistantRoleEvidenceKinds: [],
        candidateTagNames: [],
        candidateAttributeNames: [],
        ancestorAttributeNames: [],
        interactiveKinds: [],
        interactiveAttributeNames: [],
        hrefAttributePresent: false,
        downloadAttributePresent: false,
        conversationTurnAncestorPresent: false,
        reactFiberPropertyPresent: false,
        reactPropsPropertyPresent: false
      };
    }

    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    const matches = [];
    const assistantRoleEvidenceKinds = new Set();
    let anyExactFilenameMatchCount = 0;
    let userOwnedExactFilenameMatchCount = 0;
    let roleUnprovenExactFilenameMatchCount = 0;
    let node = null;
    while ((node = walker.nextNode()) && anyExactFilenameMatchCount < 32) {
      if (String(node.nodeValue || '').trim() !== probeFilename) continue;
      const parent = node.parentElement;
      if (!(parent instanceof Element) || !visible(parent)) continue;
      anyExactFilenameMatchCount += 1;
      const turn = parent.closest('[data-testid^="conversation-turn-"],article');
      const ownership = turnRole(turn);
      if (ownership.role === 'user') {
        userOwnedExactFilenameMatchCount += 1;
        continue;
      }
      if (ownership.role !== 'assistant') {
        roleUnprovenExactFilenameMatchCount += 1;
        continue;
      }
      if (ownership.evidence) assistantRoleEvidenceKinds.add(ownership.evidence);
      if (matches.length < 16) matches.push(parent);
    }

    const candidateTagNames = new Set();
    const candidateAttributeNames = new Set();
    const ancestorAttributeNames = new Set();
    const interactiveKinds = new Set();
    const interactiveAttributeNames = new Set();
    let hrefAttributePresent = false;
    let downloadAttributePresent = false;
    let conversationTurnAncestorPresent = false;
    let reactFiberPropertyPresent = false;
    let reactPropsPropertyPresent = false;

    const inspectReactOwnership = (element) => {
      if (!(element instanceof Element)) return;
      let names = [];
      try { names = Object.getOwnPropertyNames(element); } catch {}
      if (names.some((name) => name.startsWith('__reactFiber$'))) reactFiberPropertyPresent = true;
      if (names.some((name) => name.startsWith('__reactProps$'))) reactPropsPropertyPresent = true;
    };

    for (const candidate of matches) {
      candidateTagNames.add(String(candidate.tagName || '').toLowerCase());
      addNames(candidateAttributeNames, safeAttributeNames(candidate));
      inspectReactOwnership(candidate);

      const interactive = candidate.closest('a,button,[role="button"]');
      if (interactive instanceof Element) {
        const tag = String(interactive.tagName || '').toLowerCase();
        const role = interactive.getAttribute('role');
        interactiveKinds.add(role === 'button' ? 'role_button' : tag || 'other');
        addNames(interactiveAttributeNames, safeAttributeNames(interactive));
        hrefAttributePresent = hrefAttributePresent || interactive.hasAttribute('href');
        downloadAttributePresent = downloadAttributePresent || interactive.hasAttribute('download');
        inspectReactOwnership(interactive);
      }

      let ancestor = candidate.parentElement;
      for (let depth = 0; depth < 8 && ancestor; depth += 1, ancestor = ancestor.parentElement) {
        addNames(ancestorAttributeNames, safeAttributeNames(ancestor));
        hrefAttributePresent = hrefAttributePresent || ancestor.hasAttribute('href');
        downloadAttributePresent = downloadAttributePresent || ancestor.hasAttribute('download');
        if (
          ancestor.hasAttribute('data-testid') &&
          String(ancestor.getAttribute('data-testid') || '').startsWith('conversation-turn-')
        ) {
          conversationTurnAncestorPresent = true;
        }
        inspectReactOwnership(ancestor);
      }
    }

    return {
      surfaceReady: true,
      exactFilenameVisible: matches.length > 0,
      exactFilenameMatchCount: matches.length,
      anyExactFilenameMatchCount,
      userOwnedExactFilenameMatchCount,
      roleUnprovenExactFilenameMatchCount,
      assistantRoleEvidenceKinds: Array.from(assistantRoleEvidenceKinds).sort(),
      candidateTagNames: Array.from(candidateTagNames).sort(),
      candidateAttributeNames: Array.from(candidateAttributeNames).sort(),
      ancestorAttributeNames: Array.from(ancestorAttributeNames).sort(),
      interactiveKinds: Array.from(interactiveKinds).sort(),
      interactiveAttributeNames: Array.from(interactiveAttributeNames).sort(),
      hrefAttributePresent,
      downloadAttributePresent,
      conversationTurnAncestorPresent,
      reactFiberPropertyPresent,
      reactPropsPropertyPresent
    };
  })()`;
}

function _pr101ArtifactSurfaceSafeNames(value, maxItems = 96) {
  if (!Array.isArray(value)) return [];
  const names = [];
  for (const item of value) {
    if (typeof item !== "string" || !/^[A-Za-z0-9_.:-]{1,80}$/.test(item)) continue;
    names.push(item);
    if (names.length >= maxItems) break;
  }
  return Array.from(new Set(names)).sort();
}

function _pr101ArtifactSurfaceSafeCount(value, maxValue) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maxValue) : 0;
}

async function _pr101CharacterizeGeneratedArtifactSurface() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_SURFACE_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_SURFACE_PROBE_FILENAME,
      runtimeTabPresent: false,
      surfaceReady: false,
      exactFilenameVisible: false,
      exactFilenameMatchCount: 0,
      anyExactFilenameMatchCount: 0,
      userOwnedExactFilenameMatchCount: 0,
      roleUnprovenExactFilenameMatchCount: 0,
      assistantRoleEvidenceKinds: [],
      candidateTagNames: [],
      candidateAttributeNames: [],
      ancestorAttributeNames: [],
      interactiveKinds: [],
      interactiveAttributeNames: [],
      hrefAttributePresent: false,
      downloadAttributePresent: false,
      conversationTurnAncestorPresent: false,
      reactFiberPropertyPresent: false,
      reactPropsPropertyPresent: false,
      rawDomExported: false,
      rawTextExported: false,
      locatorValuesExported: false,
      attributeValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR10_1_ARTIFACT_SURFACE_RUNTIME_TAB_NOT_CHATGPT");
  }

  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactSurfaceExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_SURFACE_RESULT_MISSING");
    }
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === runtimeTabId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
  }

  return {
    schema: PR101_ARTIFACT_SURFACE_SCHEMA,
    fixedProbeFilename: PR101_ARTIFACT_SURFACE_PROBE_FILENAME,
    runtimeTabPresent: true,
    surfaceReady: value.surfaceReady === true,
    exactFilenameVisible: value.exactFilenameVisible === true,
    exactFilenameMatchCount: _pr101ArtifactSurfaceSafeCount(value.exactFilenameMatchCount, 16),
    anyExactFilenameMatchCount: _pr101ArtifactSurfaceSafeCount(value.anyExactFilenameMatchCount, 32),
    userOwnedExactFilenameMatchCount: _pr101ArtifactSurfaceSafeCount(
      value.userOwnedExactFilenameMatchCount,
      32
    ),
    roleUnprovenExactFilenameMatchCount: _pr101ArtifactSurfaceSafeCount(
      value.roleUnprovenExactFilenameMatchCount,
      32
    ),
    assistantRoleEvidenceKinds: _pr101ArtifactSurfaceSafeNames(
      value.assistantRoleEvidenceKinds,
      8
    ),
    candidateTagNames: _pr101ArtifactSurfaceSafeNames(value.candidateTagNames, 32),
    candidateAttributeNames: _pr101ArtifactSurfaceSafeNames(value.candidateAttributeNames),
    ancestorAttributeNames: _pr101ArtifactSurfaceSafeNames(value.ancestorAttributeNames),
    interactiveKinds: _pr101ArtifactSurfaceSafeNames(value.interactiveKinds, 16),
    interactiveAttributeNames: _pr101ArtifactSurfaceSafeNames(value.interactiveAttributeNames),
    hrefAttributePresent: value.hrefAttributePresent === true,
    downloadAttributePresent: value.downloadAttributePresent === true,
    conversationTurnAncestorPresent: value.conversationTurnAncestorPresent === true,
    reactFiberPropertyPresent: value.reactFiberPropertyPresent === true,
    reactPropsPropertyPresent: value.reactPropsPropertyPresent === true,
    rawDomExported: false,
    rawTextExported: false,
    locatorValuesExported: false,
    attributeValuesExported: false,
    clickPerformed: false,
    downloadAttempted: false,
    writePerformed: false,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactSurfaceProbe(message) {
  if (message?.characterizeGeneratedArtifactSurfaceSupport === true) {
    _pr101ArtifactSurfaceRejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SURFACE_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactSurfaceCharacterizationSupported: true,
      generatedArtifactSurfaceCharacterizationSchemaVersion: PR101_ARTIFACT_SURFACE_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_SURFACE_PROBE_FILENAME,
      assistantOwnershipRequired: true,
      userTurnMatchesExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      locatorValuesExported: false,
      attributeValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false
    };
  }

  if (message?.characterizeGeneratedArtifactSurface === true) {
    _pr101ArtifactSurfaceRejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SURFACE_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactSurface();
  }

  return _pr101ArtifactSurfacePriorExecuteNativeTurn(message);
};
