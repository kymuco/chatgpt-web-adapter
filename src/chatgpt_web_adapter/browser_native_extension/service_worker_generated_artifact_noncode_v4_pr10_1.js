// PR10.1 v4: bounded, read-only structural characterization of the already-proven
// assistant probe turn outside PRE/CODE surfaces. This diagnostic exports only
// structural names/counts/booleans. It never exports DOM text, attribute values,
// React prop values, locator values, clicks, downloads, or writes.

const PR101_ARTIFACT_NONCODE_V4_SCHEMA = 4;
const PR101_ARTIFACT_NONCODE_V4_USER_MARKER = "CWA_PR10_1_ARTIFACT_PROBE";
const PR101_ARTIFACT_NONCODE_V4_ASSISTANT_MARKER = "ARTIFACT_PROBE_CREATED";
const _pr101ArtifactNonCodeV4PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactNonCodeV4RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactNonCodeV4RouteEvidence(url) {
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

function _pr101ArtifactNonCodeV4Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const safeName = (value) => {
      const text = typeof value === 'string' ? value.trim() : '';
      return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
    };
    const safeNames = (values, limit = 160) => {
      const output = new Set();
      for (const value of values || []) {
        const name = safeName(value);
        if (!name) continue;
        output.add(name);
        if (output.size >= limit) break;
      }
      return Array.from(output).sort();
    };
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const normalizedText = (element) => {
      if (!(element instanceof Element)) return '';
      const value = typeof element.innerText === 'string' ? element.innerText : element.textContent;
      return typeof value === 'string' ? value.replace(/\\s+/g, ' ').trim() : '';
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
    const attributeNames = (element) => {
      if (!(element instanceof Element)) return [];
      return safeNames(
        Array.from(element.attributes || []).map((attribute) => attribute?.name),
        64
      );
    };
    const ownReactHandles = (element) => {
      if (!(element instanceof Element)) return { props: null, fiber: null, fiberPresent: false, propsPresent: false };
      let ownNames = [];
      try { ownNames = Object.getOwnPropertyNames(element); } catch {}
      const propsHandle = ownNames.find((name) => name.startsWith('__reactProps$')) || null;
      const fiberHandle = ownNames.find((name) => name.startsWith('__reactFiber$')) || null;
      let props = null;
      let fiber = null;
      try { props = propsHandle ? element[propsHandle] : null; } catch {}
      try { fiber = fiberHandle ? element[fiberHandle] : null; } catch {}
      return {
        props,
        fiber,
        fiberPresent: Boolean(fiberHandle),
        propsPresent: Boolean(propsHandle)
      };
    };
    const reactPropNames = (element) => {
      const handles = ownReactHandles(element);
      const names = [];
      if (handles.props && typeof handles.props === 'object') {
        try { names.push(...Object.keys(handles.props)); } catch {}
      }
      const memoized = handles.fiber?.memoizedProps;
      if (memoized && typeof memoized === 'object') {
        try { names.push(...Object.keys(memoized)); } catch {}
      }
      return safeNames(names, 160);
    };
    const reactComponentNames = (element) => {
      const handles = ownReactHandles(element);
      const names = [];
      let fiber = handles.fiber;
      for (let depth = 0; depth < 6 && fiber; depth += 1, fiber = fiber.return) {
        const type = fiber.elementType || fiber.type;
        if (typeof type === 'function') {
          const displayName = safeName(type.displayName);
          const functionName = safeName(type.name);
          if (displayName) names.push(displayName);
          if (functionName) names.push(functionName);
        } else if (type && typeof type === 'object') {
          const displayName = safeName(type.displayName);
          const objectName = safeName(type.name);
          if (displayName) names.push(displayName);
          if (objectName) names.push(objectName);
        }
      }
      return safeNames(names, 48);
    };
    const identityLike = (names) => safeNames((names || []).filter((name) => {
      const lower = String(name).toLowerCase();
      return lower === 'fileid' || lower === 'file_id' ||
        lower === 'artifactid' || lower === 'artifact_id' ||
        lower === 'assetid' || lower === 'asset_id' ||
        lower === 'attachmentid' || lower === 'attachment_id' ||
        lower === 'generatedfileid' || lower === 'generated_file_id' ||
        lower.includes('fileid') || lower.includes('artifactid') ||
        lower.includes('assetid') || lower.includes('attachmentid');
    }), 32);
    const locatorLike = (names) => safeNames((names || []).filter((name) => {
      const lower = String(name).toLowerCase();
      return lower === 'href' || lower === 'url' || lower === 'uri' ||
        lower === 'downloadurl' || lower === 'download_url' ||
        lower === 'downloaduri' || lower === 'download_uri' ||
        lower === 'signedurl' || lower === 'signed_url' ||
        lower === 'assetpointer' || lower === 'asset_pointer';
    }), 32);
    const artifactLike = (names) => safeNames((names || []).filter((name) => {
      const lower = String(name).toLowerCase();
      if (lower === 'file' || lower === 'files') return true;
      if (lower.startsWith('file_') || lower.startsWith('file-')) return true;
      return [
        'filename', 'fileid', 'filesize', 'filetype', 'fileurl', 'fileuri', 'filepointer',
        'generatedfile', 'uploadedfile', 'artifact', 'attachment', 'download',
        'assetid', 'asseturl', 'asseturi', 'assetpointer'
      ].some((token) => lower.includes(token));
    }), 64);
    const interactiveKind = (element) => {
      if (!(element instanceof Element)) return 'none';
      const tag = String(element.tagName || '').toLowerCase();
      const role = String(element.getAttribute('role') || '').trim();
      if (role === 'button') return 'role_button';
      if (role === 'link') return 'role_link';
      if (tag === 'a' || tag === 'button') return tag;
      return 'none';
    };
    const depthToTurn = (element, turn) => {
      let current = element;
      for (let depth = 0; depth <= 16 && current; depth += 1, current = current.parentElement) {
        if (current === turn) return depth;
      }
      return null;
    };

    const empty = {
      surfaceReady: false,
      selectorKind: 'none',
      visibleTurnCount: 0,
      userProbeMarkerTurnCount: 0,
      assistantCompletionMarkerTurnCount: 0,
      orderedProbeTurnPairPresent: false,
      probePlacementProven: false,
      placementRoleEvidenceKinds: [],
      scannedNonCodeElementCount: 0,
      structuralCandidateCount: 0,
      identityCandidateCount: 0,
      artifactKeywordCandidateCount: 0,
      locatorOnlyCandidateCount: 0,
      candidateSummaries: []
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

    let firstUserProbeIndex = -1;
    let firstAssistantCompletionAfterUserIndex = -1;
    let userProbeMarkerTurnCount = 0;
    let assistantCompletionMarkerTurnCount = 0;
    const placementRoleEvidenceKinds = new Set();
    const targetAssistantTurns = [];

    for (let index = 0; index < turns.length; index += 1) {
      const turn = turns[index];
      const ownership = turnRole(turn);
      const text = normalizedText(turn);
      if (ownership.role === 'user' && text.includes(userMarker)) {
        userProbeMarkerTurnCount += 1;
        if (firstUserProbeIndex < 0) firstUserProbeIndex = index;
        if (ownership.evidence) placementRoleEvidenceKinds.add(ownership.evidence);
      }
      if (ownership.role === 'assistant' && text.includes(assistantMarker)) {
        assistantCompletionMarkerTurnCount += 1;
        targetAssistantTurns.push(turn);
        if (ownership.evidence) placementRoleEvidenceKinds.add(ownership.evidence);
        if (
          firstUserProbeIndex >= 0 && index > firstUserProbeIndex &&
          firstAssistantCompletionAfterUserIndex < 0
        ) {
          firstAssistantCompletionAfterUserIndex = index;
        }
      }
    }

    const orderedProbeTurnPairPresent = (
      firstUserProbeIndex >= 0 && firstAssistantCompletionAfterUserIndex > firstUserProbeIndex
    );
    const probePlacementProven = Boolean(
      orderedProbeTurnPairPresent &&
      userProbeMarkerTurnCount >= 1 &&
      assistantCompletionMarkerTurnCount >= 1
    );

    let scannedNonCodeElementCount = 0;
    const summaries = [];
    let identityCandidateCount = 0;
    let artifactKeywordCandidateCount = 0;
    let locatorOnlyCandidateCount = 0;

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 8)) {
        const elements = Array.from(targetTurn.querySelectorAll('*')).slice(0, 2048);
        for (const element of elements) {
          if (summaries.length >= 24) break;
          if (!(element instanceof Element) || !visible(element)) continue;
          const codeAncestor = element.closest('pre,code');
          if (codeAncestor instanceof Element && targetTurn.contains(codeAncestor)) continue;
          scannedNonCodeElementCount += 1;

          const attrs = attributeNames(element);
          const props = reactPropNames(element);
          const components = reactComponentNames(element);
          const identityNames = identityLike(props);
          const locatorNames = locatorLike(props);
          const artifactPropNames = artifactLike(props);
          const artifactAttrNames = artifactLike(attrs);
          const artifactComponentNames = artifactLike(components);
          const hrefPresent = element.hasAttribute('href');
          const downloadPresent = element.hasAttribute('download');
          const reasons = [];
          if (identityNames.length) reasons.push('identity_react_key');
          if (artifactPropNames.length) reasons.push('artifact_react_key');
          if (artifactAttrNames.length) reasons.push('artifact_dom_attribute_name');
          if (artifactComponentNames.length) reasons.push('artifact_react_component_name');
          if (locatorNames.length) reasons.push('locator_react_key');
          if (hrefPresent) reasons.push('href_attribute_present');
          if (downloadPresent) reasons.push('download_attribute_present');
          if (!reasons.length) continue;

          const structuralArtifactEvidence = Boolean(
            identityNames.length || artifactPropNames.length || artifactAttrNames.length ||
            artifactComponentNames.length || downloadPresent
          );
          if (identityNames.length) identityCandidateCount += 1;
          if (structuralArtifactEvidence) artifactKeywordCandidateCount += 1;
          if (!structuralArtifactEvidence && (locatorNames.length || hrefPresent)) {
            locatorOnlyCandidateCount += 1;
          }
          const handles = ownReactHandles(element);

          summaries.push({
            index: summaries.length,
            tagName: safeName(String(element.tagName || '').toLowerCase()) || 'unknown',
            depthToTurn: depthToTurn(element, targetTurn),
            interactiveKind: interactiveKind(element),
            hrefAttributePresent: hrefPresent,
            downloadAttributePresent: downloadPresent,
            attributeNames: attrs,
            artifactLikeAttributeNames: artifactAttrNames,
            reactFiberPropertyPresent: handles.fiberPresent,
            reactPropsPropertyPresent: handles.propsPresent,
            reactPropNames: props,
            identityLikeReactPropNames: identityNames,
            locatorLikeReactPropNames: locatorNames,
            artifactLikeReactPropNames: artifactPropNames,
            reactComponentNames: components,
            artifactLikeReactComponentNames: artifactComponentNames,
            candidateReasonKinds: safeNames(reasons, 16)
          });
        }
      }
    }

    return {
      surfaceReady: true,
      selectorKind,
      visibleTurnCount: turns.length,
      userProbeMarkerTurnCount,
      assistantCompletionMarkerTurnCount,
      orderedProbeTurnPairPresent,
      probePlacementProven,
      placementRoleEvidenceKinds: Array.from(placementRoleEvidenceKinds).sort(),
      scannedNonCodeElementCount,
      structuralCandidateCount: summaries.length,
      identityCandidateCount,
      artifactKeywordCandidateCount,
      locatorOnlyCandidateCount,
      candidateSummaries: summaries
    };
  })()`;
}

function _pr101ArtifactNonCodeV4SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactNonCodeV4SafeNames(value, maxItems = 160) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactNonCodeV4SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactNonCodeV4SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactNonCodeV4SafeNullableDepth(value) {
  return Number.isInteger(value) && value >= 0 && value <= 16 ? value : null;
}

function _pr101ArtifactNonCodeV4SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const interactiveKind = ["none", "a", "button", "role_button", "role_link"].includes(value.interactiveKind)
    ? value.interactiveKind
    : "none";
  return {
    index: _pr101ArtifactNonCodeV4SafeCount(value.index, 24),
    tagName: _pr101ArtifactNonCodeV4SafeName(value.tagName) || "unknown",
    depthToTurn: _pr101ArtifactNonCodeV4SafeNullableDepth(value.depthToTurn),
    interactiveKind,
    hrefAttributePresent: value.hrefAttributePresent === true,
    downloadAttributePresent: value.downloadAttributePresent === true,
    attributeNames: _pr101ArtifactNonCodeV4SafeNames(value.attributeNames, 64),
    artifactLikeAttributeNames: _pr101ArtifactNonCodeV4SafeNames(value.artifactLikeAttributeNames, 64),
    reactFiberPropertyPresent: value.reactFiberPropertyPresent === true,
    reactPropsPropertyPresent: value.reactPropsPropertyPresent === true,
    reactPropNames: _pr101ArtifactNonCodeV4SafeNames(value.reactPropNames, 160),
    identityLikeReactPropNames: _pr101ArtifactNonCodeV4SafeNames(value.identityLikeReactPropNames, 32),
    locatorLikeReactPropNames: _pr101ArtifactNonCodeV4SafeNames(value.locatorLikeReactPropNames, 32),
    artifactLikeReactPropNames: _pr101ArtifactNonCodeV4SafeNames(value.artifactLikeReactPropNames, 64),
    reactComponentNames: _pr101ArtifactNonCodeV4SafeNames(value.reactComponentNames, 48),
    artifactLikeReactComponentNames: _pr101ArtifactNonCodeV4SafeNames(
      value.artifactLikeReactComponentNames,
      48
    ),
    candidateReasonKinds: _pr101ArtifactNonCodeV4SafeNames(value.candidateReasonKinds, 16)
  };
}

async function _pr101CharacterizeGeneratedArtifactNonCodeV4() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_NONCODE_V4_SCHEMA,
      runtimeTabPresent: false,
      runtimeRouteKind: "absent",
      runtimeConversationIdPresent: false,
      surfaceReady: false,
      selectorKind: "none",
      visibleTurnCount: 0,
      userProbeMarkerTurnCount: 0,
      assistantCompletionMarkerTurnCount: 0,
      orderedProbeTurnPairPresent: false,
      probePlacementProven: false,
      placementRoleEvidenceKinds: [],
      scannedNonCodeElementCount: 0,
      structuralCandidateCount: 0,
      identityCandidateCount: 0,
      artifactKeywordCandidateCount: 0,
      locatorOnlyCandidateCount: 0,
      candidateSummaries: [],
      preCodeExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR10_1_ARTIFACT_NONCODE_V4_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactNonCodeV4RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactNonCodeV4Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_NONCODE_V4_RESULT_MISSING");
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

  const summaries = Array.isArray(value.candidateSummaries)
    ? value.candidateSummaries.map(_pr101ArtifactNonCodeV4SafeCandidate).filter(Boolean).slice(0, 24)
    : [];

  return {
    schema: PR101_ARTIFACT_NONCODE_V4_SCHEMA,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactNonCodeV4SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactNonCodeV4SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactNonCodeV4SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactNonCodeV4SafeCount(
      value.assistantCompletionMarkerTurnCount,
      64
    ),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactNonCodeV4SafeNames(value.placementRoleEvidenceKinds, 8),
    scannedNonCodeElementCount: _pr101ArtifactNonCodeV4SafeCount(value.scannedNonCodeElementCount, 2048),
    structuralCandidateCount: _pr101ArtifactNonCodeV4SafeCount(value.structuralCandidateCount, 24),
    identityCandidateCount: _pr101ArtifactNonCodeV4SafeCount(value.identityCandidateCount, 24),
    artifactKeywordCandidateCount: _pr101ArtifactNonCodeV4SafeCount(value.artifactKeywordCandidateCount, 24),
    locatorOnlyCandidateCount: _pr101ArtifactNonCodeV4SafeCount(value.locatorOnlyCandidateCount, 24),
    candidateSummaries: summaries,
    preCodeExcluded: true,
    rawDomExported: false,
    rawTextExported: false,
    attributeValuesExported: false,
    reactPropValuesExported: false,
    locatorValuesExported: false,
    clickPerformed: false,
    downloadAttempted: false,
    writePerformed: false,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactNonCodeV4(message) {
  if (message?.characterizeGeneratedArtifactNonCodeV4Support === true) {
    _pr101ArtifactNonCodeV4RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_NONCODE_V4_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactNonCodeV4CharacterizationSupported: true,
      generatedArtifactNonCodeV4CharacterizationSchemaVersion: PR101_ARTIFACT_NONCODE_V4_SCHEMA,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      preCodeExcluded: true,
      structuralKeyNamesOnly: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false
    };
  }

  if (message?.characterizeGeneratedArtifactNonCodeV4 === true) {
    _pr101ArtifactNonCodeV4RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_NONCODE_V4_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactNonCodeV4();
  }

  return _pr101ArtifactNonCodeV4PriorExecuteNativeTurn(message);
};