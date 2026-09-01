// PR10.1 v2: bounded, read-only frontend placement + artifact-surface
// characterization for an already-created fixed probe artifact. This diagnostic
// does not type, submit, click, download, export DOM/text, or expose locator or
// attribute values. Probe placement is proven independently from artifact evidence.

const PR101_ARTIFACT_SURFACE_V2_SCHEMA = 2;
const PR101_ARTIFACT_SURFACE_V2_FILENAME = "cwa_pr10_1_probe.txt";
const PR101_ARTIFACT_SURFACE_V2_USER_MARKER = "CWA_PR10_1_ARTIFACT_PROBE";
const PR101_ARTIFACT_SURFACE_V2_ASSISTANT_MARKER = "ARTIFACT_PROBE_CREATED";
const _pr101ArtifactSurfaceV2PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactSurfaceV2RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactSurfaceV2RouteEvidence(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) {
      return { routeKind: "not_chatgpt", conversationIdPresent: false };
    }
    if (conversationIdFromUrl(url || "")) {
      return { routeKind: "conversation", conversationIdPresent: true };
    }
    if (parsed.pathname === "/" || parsed.pathname === "") {
      return { routeKind: "root", conversationIdPresent: false };
    }
    return { routeKind: "chatgpt_other", conversationIdPresent: false };
  } catch {
    return { routeKind: "invalid", conversationIdPresent: false };
  }
}

function _pr101ArtifactSurfaceV2Expression() {
  return `(() => {
    const probeFilename = 'cwa_pr10_1_probe.txt';
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const normalize = (value) => typeof value === 'string'
      ? value.trim().replace(/\\s+/g, ' ')
      : '';
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
    const inspectReactOwnership = (element, state) => {
      if (!(element instanceof Element)) return;
      let names = [];
      try { names = Object.getOwnPropertyNames(element); } catch {}
      if (names.some((name) => name.startsWith('__reactFiber$'))) state.reactFiber = true;
      if (names.some((name) => name.startsWith('__reactProps$'))) state.reactProps = true;
    };
    const interactiveKind = (element) => {
      if (!(element instanceof Element)) return null;
      const tag = String(element.tagName || '').toLowerCase();
      const role = String(element.getAttribute('role') || '').trim();
      if (role === 'button') return 'role_button';
      if (tag === 'a' || tag === 'button') return tag;
      return 'other';
    };
    const valueContainsFilename = (element, attributeName) => {
      if (!(element instanceof Element)) return false;
      const value = String(element.getAttribute(attributeName) || '');
      return value.includes(probeFilename);
    };

    const empty = {
      surfaceReady: false,
      selectorKind: 'none',
      visibleTurnCount: 0,
      userTurnCount: 0,
      assistantTurnCount: 0,
      roleUnprovenTurnCount: 0,
      userProbeMarkerTurnCount: 0,
      assistantCompletionMarkerTurnCount: 0,
      orderedProbeTurnPairPresent: false,
      probePlacementProven: false,
      placementRoleEvidenceKinds: [],
      assistantFilenameSubstringMatchCount: 0,
      assistantInteractiveFilenameMatchCount: 0,
      assistantNonInteractiveFilenameMatchCount: 0,
      filenameMatchSurfaces: [],
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

    const main = document.querySelector('main');
    if (!main) return empty;

    let selectorKind = 'conversation_testid';
    let turns = Array.from(main.querySelectorAll('[data-testid^="conversation-turn-"]'));
    if (turns.length === 0) {
      selectorKind = 'article_fallback';
      turns = Array.from(main.querySelectorAll('article'));
    }
    turns = Array.from(new Set(turns)).filter((turn) => visible(turn)).slice(0, 64);

    let userTurnCount = 0;
    let assistantTurnCount = 0;
    let roleUnprovenTurnCount = 0;
    let userProbeMarkerTurnCount = 0;
    let assistantCompletionMarkerTurnCount = 0;
    let firstUserProbeIndex = -1;
    let firstAssistantCompletionAfterUserIndex = -1;
    const targetAssistantTurns = [];
    const placementRoleEvidenceKinds = new Set();

    for (let index = 0; index < turns.length; index += 1) {
      const turn = turns[index];
      const ownership = turnRole(turn);
      const text = normalize(turn.innerText || turn.textContent || '');
      if (ownership.role === 'user') {
        userTurnCount += 1;
        if (text.includes(userMarker)) {
          userProbeMarkerTurnCount += 1;
          if (firstUserProbeIndex < 0) firstUserProbeIndex = index;
          if (ownership.evidence) placementRoleEvidenceKinds.add(ownership.evidence);
        }
        continue;
      }
      if (ownership.role === 'assistant') {
        assistantTurnCount += 1;
        if (text.includes(assistantMarker)) {
          assistantCompletionMarkerTurnCount += 1;
          targetAssistantTurns.push(turn);
          if (ownership.evidence) placementRoleEvidenceKinds.add(ownership.evidence);
          if (firstUserProbeIndex >= 0 && index > firstUserProbeIndex && firstAssistantCompletionAfterUserIndex < 0) {
            firstAssistantCompletionAfterUserIndex = index;
          }
        }
        continue;
      }
      roleUnprovenTurnCount += 1;
    }

    const orderedProbeTurnPairPresent = (
      firstUserProbeIndex >= 0 && firstAssistantCompletionAfterUserIndex > firstUserProbeIndex
    );
    const probePlacementProven = Boolean(
      orderedProbeTurnPairPresent &&
      userProbeMarkerTurnCount >= 1 &&
      assistantCompletionMarkerTurnCount >= 1
    );

    const candidateTagNames = new Set();
    const candidateAttributeNames = new Set();
    const ancestorAttributeNames = new Set();
    const interactiveKinds = new Set();
    const interactiveAttributeNames = new Set();
    const filenameMatchSurfaces = new Set();
    const matchedInteractiveElements = new Set();
    const matchedNonInteractiveElements = new Set();
    const reactState = { reactFiber: false, reactProps: false };
    let hrefAttributePresent = false;
    let downloadAttributePresent = false;
    let conversationTurnAncestorPresent = false;
    let assistantFilenameSubstringMatchCount = 0;

    const inspectCandidate = (candidate, targetTurn) => {
      if (!(candidate instanceof Element) || !visible(candidate)) return;
      candidateTagNames.add(String(candidate.tagName || '').toLowerCase());
      addNames(candidateAttributeNames, safeAttributeNames(candidate));
      inspectReactOwnership(candidate, reactState);

      const interactive = candidate.closest('a,button,[role="button"]');
      if (interactive instanceof Element && targetTurn.contains(interactive)) {
        matchedInteractiveElements.add(interactive);
        const kind = interactiveKind(interactive);
        if (kind) interactiveKinds.add(kind);
        addNames(interactiveAttributeNames, safeAttributeNames(interactive));
        hrefAttributePresent = hrefAttributePresent || interactive.hasAttribute('href');
        downloadAttributePresent = downloadAttributePresent || interactive.hasAttribute('download');
        inspectReactOwnership(interactive, reactState);
      } else {
        matchedNonInteractiveElements.add(candidate);
      }

      let ancestor = candidate.parentElement;
      for (let depth = 0; depth < 8 && ancestor && targetTurn.contains(ancestor); depth += 1, ancestor = ancestor.parentElement) {
        addNames(ancestorAttributeNames, safeAttributeNames(ancestor));
        hrefAttributePresent = hrefAttributePresent || ancestor.hasAttribute('href');
        downloadAttributePresent = downloadAttributePresent || ancestor.hasAttribute('download');
        if (
          ancestor.hasAttribute('data-testid') &&
          String(ancestor.getAttribute('data-testid') || '').startsWith('conversation-turn-')
        ) {
          conversationTurnAncestorPresent = true;
        }
        inspectReactOwnership(ancestor, reactState);
      }
    };

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 8)) {
        const walker = document.createTreeWalker(targetTurn, NodeFilter.SHOW_TEXT);
        let node = null;
        let perTurnTextMatches = 0;
        while ((node = walker.nextNode()) && perTurnTextMatches < 16 && assistantFilenameSubstringMatchCount < 32) {
          const value = String(node.nodeValue || '');
          if (!value.includes(probeFilename)) continue;
          const parent = node.parentElement;
          if (!(parent instanceof Element) || !visible(parent)) continue;
          assistantFilenameSubstringMatchCount += 1;
          perTurnTextMatches += 1;
          filenameMatchSurfaces.add('text_node_substring');
          inspectCandidate(parent, targetTurn);
        }

        const interactives = Array.from(targetTurn.querySelectorAll('a,button,[role="button"]')).slice(0, 256);
        for (const interactive of interactives) {
          if (!(interactive instanceof Element) || !visible(interactive)) continue;
          let matched = false;
          const interactiveText = normalize(interactive.innerText || interactive.textContent || '');
          if (interactiveText.includes(probeFilename)) {
            matched = true;
            filenameMatchSurfaces.add('interactive_text_substring');
          }
          for (const attributeName of ['aria-label', 'title', 'download']) {
            if (!valueContainsFilename(interactive, attributeName)) continue;
            matched = true;
            filenameMatchSurfaces.add(
              attributeName === 'aria-label' ? 'aria_label' : attributeName + '_attribute'
            );
          }
          if (!matched) continue;
          matchedInteractiveElements.add(interactive);
          const kind = interactiveKind(interactive);
          if (kind) interactiveKinds.add(kind);
          addNames(interactiveAttributeNames, safeAttributeNames(interactive));
          hrefAttributePresent = hrefAttributePresent || interactive.hasAttribute('href');
          downloadAttributePresent = downloadAttributePresent || interactive.hasAttribute('download');
          inspectReactOwnership(interactive, reactState);
        }
      }
    }

    return {
      surfaceReady: true,
      selectorKind,
      visibleTurnCount: turns.length,
      userTurnCount,
      assistantTurnCount,
      roleUnprovenTurnCount,
      userProbeMarkerTurnCount,
      assistantCompletionMarkerTurnCount,
      orderedProbeTurnPairPresent,
      probePlacementProven,
      placementRoleEvidenceKinds: Array.from(placementRoleEvidenceKinds).sort(),
      assistantFilenameSubstringMatchCount,
      assistantInteractiveFilenameMatchCount: matchedInteractiveElements.size,
      assistantNonInteractiveFilenameMatchCount: matchedNonInteractiveElements.size,
      filenameMatchSurfaces: Array.from(filenameMatchSurfaces).sort(),
      candidateTagNames: Array.from(candidateTagNames).sort(),
      candidateAttributeNames: Array.from(candidateAttributeNames).sort(),
      ancestorAttributeNames: Array.from(ancestorAttributeNames).sort(),
      interactiveKinds: Array.from(interactiveKinds).sort(),
      interactiveAttributeNames: Array.from(interactiveAttributeNames).sort(),
      hrefAttributePresent,
      downloadAttributePresent,
      conversationTurnAncestorPresent,
      reactFiberPropertyPresent: reactState.reactFiber,
      reactPropsPropertyPresent: reactState.reactProps
    };
  })()`;
}

function _pr101ArtifactSurfaceV2SafeNames(value, maxItems = 96) {
  if (!Array.isArray(value)) return [];
  const names = [];
  for (const item of value) {
    if (typeof item !== "string" || !/^[A-Za-z0-9_.:-]{1,80}$/.test(item)) continue;
    names.push(item);
    if (names.length >= maxItems) break;
  }
  return Array.from(new Set(names)).sort();
}

function _pr101ArtifactSurfaceV2SafeCount(value, maxValue) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maxValue) : 0;
}

async function _pr101CharacterizeGeneratedArtifactSurfaceV2() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_SURFACE_V2_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_SURFACE_V2_FILENAME,
      runtimeTabPresent: false,
      runtimeRouteKind: "absent",
      runtimeConversationIdPresent: false,
      surfaceReady: false,
      selectorKind: "none",
      visibleTurnCount: 0,
      userTurnCount: 0,
      assistantTurnCount: 0,
      roleUnprovenTurnCount: 0,
      userProbeMarkerTurnCount: 0,
      assistantCompletionMarkerTurnCount: 0,
      orderedProbeTurnPairPresent: false,
      probePlacementProven: false,
      placementRoleEvidenceKinds: [],
      assistantFilenameSubstringMatchCount: 0,
      assistantInteractiveFilenameMatchCount: 0,
      assistantNonInteractiveFilenameMatchCount: 0,
      filenameMatchSurfaces: [],
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
    throw new Error("PR10_1_ARTIFACT_SURFACE_V2_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactSurfaceV2RouteEvidence(tab?.url || "");

  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactSurfaceV2Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_SURFACE_V2_RESULT_MISSING");
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
    schema: PR101_ARTIFACT_SURFACE_V2_SCHEMA,
    fixedProbeFilename: PR101_ARTIFACT_SURFACE_V2_FILENAME,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: typeof value.selectorKind === "string" ? value.selectorKind : "none",
    visibleTurnCount: _pr101ArtifactSurfaceV2SafeCount(value.visibleTurnCount, 64),
    userTurnCount: _pr101ArtifactSurfaceV2SafeCount(value.userTurnCount, 64),
    assistantTurnCount: _pr101ArtifactSurfaceV2SafeCount(value.assistantTurnCount, 64),
    roleUnprovenTurnCount: _pr101ArtifactSurfaceV2SafeCount(value.roleUnprovenTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactSurfaceV2SafeCount(value.userProbeMarkerTurnCount, 32),
    assistantCompletionMarkerTurnCount: _pr101ArtifactSurfaceV2SafeCount(
      value.assistantCompletionMarkerTurnCount,
      32
    ),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactSurfaceV2SafeNames(
      value.placementRoleEvidenceKinds,
      8
    ),
    assistantFilenameSubstringMatchCount: _pr101ArtifactSurfaceV2SafeCount(
      value.assistantFilenameSubstringMatchCount,
      32
    ),
    assistantInteractiveFilenameMatchCount: _pr101ArtifactSurfaceV2SafeCount(
      value.assistantInteractiveFilenameMatchCount,
      64
    ),
    assistantNonInteractiveFilenameMatchCount: _pr101ArtifactSurfaceV2SafeCount(
      value.assistantNonInteractiveFilenameMatchCount,
      32
    ),
    filenameMatchSurfaces: _pr101ArtifactSurfaceV2SafeNames(value.filenameMatchSurfaces, 16),
    candidateTagNames: _pr101ArtifactSurfaceV2SafeNames(value.candidateTagNames, 32),
    candidateAttributeNames: _pr101ArtifactSurfaceV2SafeNames(value.candidateAttributeNames),
    ancestorAttributeNames: _pr101ArtifactSurfaceV2SafeNames(value.ancestorAttributeNames),
    interactiveKinds: _pr101ArtifactSurfaceV2SafeNames(value.interactiveKinds, 16),
    interactiveAttributeNames: _pr101ArtifactSurfaceV2SafeNames(value.interactiveAttributeNames),
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

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactSurfaceV2(message) {
  if (message?.characterizeGeneratedArtifactSurfaceV2Support === true) {
    _pr101ArtifactSurfaceV2RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SURFACE_V2_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactSurfaceV2CharacterizationSupported: true,
      generatedArtifactSurfaceV2CharacterizationSchemaVersion: PR101_ARTIFACT_SURFACE_V2_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_SURFACE_V2_FILENAME,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      userPromptCannotBecomeArtifactEvidence: true,
      rawDomExported: false,
      rawTextExported: false,
      locatorValuesExported: false,
      attributeValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false
    };
  }

  if (message?.characterizeGeneratedArtifactSurfaceV2 === true) {
    _pr101ArtifactSurfaceV2RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SURFACE_V2_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactSurfaceV2();
  }

  return _pr101ArtifactSurfaceV2PriorExecuteNativeTurn(message);
};
