// PR10.1 v3: bounded, read-only structural topology characterization for
// filename-bearing elements inside the already-proven assistant probe turn.
// This layer exports only structural names/counts/booleans. It never exports
// DOM text, attribute values, React prop values, locator values, or clicks.

const PR101_ARTIFACT_TOPOLOGY_V3_SCHEMA = 3;
const PR101_ARTIFACT_TOPOLOGY_V3_FILENAME = "cwa_pr10_1_probe.txt";
const PR101_ARTIFACT_TOPOLOGY_V3_USER_MARKER = "CWA_PR10_1_ARTIFACT_PROBE";
const PR101_ARTIFACT_TOPOLOGY_V3_ASSISTANT_MARKER = "ARTIFACT_PROBE_CREATED";
const _pr101ArtifactTopologyV3PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactTopologyV3RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactTopologyV3RouteEvidence(url) {
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

function _pr101ArtifactTopologyV3Expression() {
  return `(() => {
    const probeFilename = 'cwa_pr10_1_probe.txt';
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const safeName = (value) => {
      const text = typeof value === 'string' ? value.trim() : '';
      return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
    };
    const safeNames = (values, limit = 96) => {
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
      if (!(element instanceof Element)) return { props: null, fiber: null };
      let ownNames = [];
      try { ownNames = Object.getOwnPropertyNames(element); } catch {}
      const propsHandle = ownNames.find((name) => name.startsWith('__reactProps$')) || null;
      const fiberHandle = ownNames.find((name) => name.startsWith('__reactFiber$')) || null;
      let props = null;
      let fiber = null;
      try { props = propsHandle ? element[propsHandle] : null; } catch {}
      try { fiber = fiberHandle ? element[fiberHandle] : null; } catch {}
      return { props, fiber };
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
      return safeNames(names, 96);
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
    const interactiveKind = (element) => {
      if (!(element instanceof Element)) return null;
      const tag = String(element.tagName || '').toLowerCase();
      const role = String(element.getAttribute('role') || '').trim();
      if (role === 'button') return 'role_button';
      if (role === 'link') return 'role_link';
      if (tag === 'a' || tag === 'button') return tag;
      return 'other';
    };

    const main = document.querySelector('main');
    if (!main) {
      return {
        surfaceReady: false,
        selectorKind: 'none',
        visibleTurnCount: 0,
        userProbeMarkerTurnCount: 0,
        assistantCompletionMarkerTurnCount: 0,
        orderedProbeTurnPairPresent: false,
        probePlacementProven: false,
        placementRoleEvidenceKinds: [],
        filenameCandidateCount: 0,
        candidateSummaries: []
      };
    }

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

    const candidates = [];
    const seenCandidates = new Set();
    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 8)) {
        const walker = document.createTreeWalker(targetTurn, NodeFilter.SHOW_TEXT);
        let node = null;
        while ((node = walker.nextNode()) && candidates.length < 12) {
          const value = String(node.nodeValue || '');
          if (!value.includes(probeFilename)) continue;
          const parent = node.parentElement;
          if (!(parent instanceof Element) || !visible(parent) || seenCandidates.has(parent)) continue;
          seenCandidates.add(parent);
          candidates.push({ element: parent, turn: targetTurn });
        }
      }
    }

    const candidateSummaries = [];
    for (let index = 0; index < candidates.length && candidateSummaries.length < 8; index += 1) {
      const candidate = candidates[index].element;
      const targetTurn = candidates[index].turn;
      const candidateAttrs = attributeNames(candidate);
      const candidateReactProps = reactPropNames(candidate);
      const ancestorTagPath = [];
      const ancestorAttrs = new Set();
      const ancestorReactProps = new Set();
      let ancestor = candidate.parentElement;
      let ancestorDepthToTurn = null;
      let nearestInteractiveContainerDepth = null;
      let nearbyInteractiveCount = 0;
      const nearbyInteractiveKinds = new Set();
      const nearbyInteractiveAttributeNames = new Set();
      const nearbyInteractiveReactProps = new Set();
      let nearbyHrefAttributePresent = false;
      let nearbyDownloadAttributePresent = false;
      let insidePre = false;
      let insideCode = false;
      let insideBlockquote = false;
      let insideTable = false;
      let directInteractiveAncestorPresent = false;
      let reactFiberPropertyPresent = false;
      let reactPropsPropertyPresent = false;

      const inspectReactPresence = (element) => {
        if (!(element instanceof Element)) return;
        let names = [];
        try { names = Object.getOwnPropertyNames(element); } catch {}
        if (names.some((name) => name.startsWith('__reactFiber$'))) reactFiberPropertyPresent = true;
        if (names.some((name) => name.startsWith('__reactProps$'))) reactPropsPropertyPresent = true;
      };

      inspectReactPresence(candidate);
      const directInteractive = candidate.closest('a,button,[role="button"],[role="link"]');
      if (directInteractive instanceof Element && targetTurn.contains(directInteractive)) {
        directInteractiveAncestorPresent = true;
      }

      for (let depth = 1; depth <= 12 && ancestor && targetTurn.contains(ancestor); depth += 1) {
        const tag = safeName(String(ancestor.tagName || '').toLowerCase());
        if (tag) ancestorTagPath.push(tag);
        for (const name of attributeNames(ancestor)) ancestorAttrs.add(name);
        for (const name of reactPropNames(ancestor)) ancestorReactProps.add(name);
        inspectReactPresence(ancestor);

        const tagLower = String(ancestor.tagName || '').toLowerCase();
        if (tagLower === 'pre') insidePre = true;
        if (tagLower === 'code') insideCode = true;
        if (tagLower === 'blockquote') insideBlockquote = true;
        if (tagLower === 'table') insideTable = true;

        if (ancestor === targetTurn) {
          ancestorDepthToTurn = depth;
          break;
        }

        if (nearestInteractiveContainerDepth === null && depth <= 8) {
          const interactives = Array.from(
            ancestor.querySelectorAll('a,button,[role="button"],[role="link"]')
          ).filter((element) => visible(element)).slice(0, 32);
          if (interactives.length > 0) {
            nearestInteractiveContainerDepth = depth;
            nearbyInteractiveCount = interactives.length;
            for (const interactive of interactives) {
              const kind = interactiveKind(interactive);
              if (kind) nearbyInteractiveKinds.add(kind);
              for (const name of attributeNames(interactive)) nearbyInteractiveAttributeNames.add(name);
              for (const name of reactPropNames(interactive)) nearbyInteractiveReactProps.add(name);
              nearbyHrefAttributePresent = nearbyHrefAttributePresent || interactive.hasAttribute('href');
              nearbyDownloadAttributePresent = nearbyDownloadAttributePresent || interactive.hasAttribute('download');
              inspectReactPresence(interactive);
            }
          }
        }
        ancestor = ancestor.parentElement;
      }

      const allReactProps = safeNames([
        ...candidateReactProps,
        ...Array.from(ancestorReactProps),
        ...Array.from(nearbyInteractiveReactProps)
      ], 160);

      candidateSummaries.push({
        index,
        tagName: safeName(String(candidate.tagName || '').toLowerCase()) || 'unknown',
        candidateAttributeNames: candidateAttrs,
        ancestorTagPath: safeNames(ancestorTagPath, 16),
        ancestorAttributeNames: safeNames(Array.from(ancestorAttrs), 96),
        ancestorDepthToTurn: Number.isInteger(ancestorDepthToTurn) ? ancestorDepthToTurn : null,
        insidePre,
        insideCode,
        insideBlockquote,
        insideTable,
        directInteractiveAncestorPresent,
        nearestInteractiveContainerDepth,
        nearbyInteractiveCount,
        nearbyInteractiveKinds: safeNames(Array.from(nearbyInteractiveKinds), 16),
        nearbyInteractiveAttributeNames: safeNames(Array.from(nearbyInteractiveAttributeNames), 96),
        nearbyHrefAttributePresent,
        nearbyDownloadAttributePresent,
        reactFiberPropertyPresent,
        reactPropsPropertyPresent,
        reactPropNames: allReactProps,
        identityLikeReactPropNames: identityLike(allReactProps),
        locatorLikeReactPropNames: locatorLike(allReactProps)
      });
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
      filenameCandidateCount: candidates.length,
      candidateSummaries
    };
  })()`;
}

function _pr101ArtifactTopologyV3SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactTopologyV3SafeNames(value, maxItems = 160) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactTopologyV3SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactTopologyV3SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactTopologyV3SafeNullableDepth(value) {
  return Number.isInteger(value) && value >= 0 && value <= 16 ? value : null;
}

function _pr101ArtifactTopologyV3SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  return {
    index: _pr101ArtifactTopologyV3SafeCount(value.index, 16),
    tagName: _pr101ArtifactTopologyV3SafeName(value.tagName) || "unknown",
    candidateAttributeNames: _pr101ArtifactTopologyV3SafeNames(value.candidateAttributeNames, 64),
    ancestorTagPath: _pr101ArtifactTopologyV3SafeNames(value.ancestorTagPath, 16),
    ancestorAttributeNames: _pr101ArtifactTopologyV3SafeNames(value.ancestorAttributeNames, 96),
    ancestorDepthToTurn: _pr101ArtifactTopologyV3SafeNullableDepth(value.ancestorDepthToTurn),
    insidePre: value.insidePre === true,
    insideCode: value.insideCode === true,
    insideBlockquote: value.insideBlockquote === true,
    insideTable: value.insideTable === true,
    directInteractiveAncestorPresent: value.directInteractiveAncestorPresent === true,
    nearestInteractiveContainerDepth: _pr101ArtifactTopologyV3SafeNullableDepth(
      value.nearestInteractiveContainerDepth
    ),
    nearbyInteractiveCount: _pr101ArtifactTopologyV3SafeCount(value.nearbyInteractiveCount, 32),
    nearbyInteractiveKinds: _pr101ArtifactTopologyV3SafeNames(value.nearbyInteractiveKinds, 16),
    nearbyInteractiveAttributeNames: _pr101ArtifactTopologyV3SafeNames(
      value.nearbyInteractiveAttributeNames,
      96
    ),
    nearbyHrefAttributePresent: value.nearbyHrefAttributePresent === true,
    nearbyDownloadAttributePresent: value.nearbyDownloadAttributePresent === true,
    reactFiberPropertyPresent: value.reactFiberPropertyPresent === true,
    reactPropsPropertyPresent: value.reactPropsPropertyPresent === true,
    reactPropNames: _pr101ArtifactTopologyV3SafeNames(value.reactPropNames, 160),
    identityLikeReactPropNames: _pr101ArtifactTopologyV3SafeNames(
      value.identityLikeReactPropNames,
      32
    ),
    locatorLikeReactPropNames: _pr101ArtifactTopologyV3SafeNames(
      value.locatorLikeReactPropNames,
      32
    )
  };
}

async function _pr101CharacterizeGeneratedArtifactTopologyV3() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_TOPOLOGY_V3_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_TOPOLOGY_V3_FILENAME,
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
      filenameCandidateCount: 0,
      candidateSummaries: [],
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
    throw new Error("PR10_1_ARTIFACT_TOPOLOGY_V3_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactTopologyV3RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactTopologyV3Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_TOPOLOGY_V3_RESULT_MISSING");
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
    ? value.candidateSummaries.map(_pr101ArtifactTopologyV3SafeCandidate).filter(Boolean).slice(0, 8)
    : [];

  return {
    schema: PR101_ARTIFACT_TOPOLOGY_V3_SCHEMA,
    fixedProbeFilename: PR101_ARTIFACT_TOPOLOGY_V3_FILENAME,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactTopologyV3SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactTopologyV3SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactTopologyV3SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactTopologyV3SafeCount(
      value.assistantCompletionMarkerTurnCount,
      64
    ),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactTopologyV3SafeNames(
      value.placementRoleEvidenceKinds,
      8
    ),
    filenameCandidateCount: _pr101ArtifactTopologyV3SafeCount(value.filenameCandidateCount, 12),
    candidateSummaries: summaries,
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

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactTopologyV3(message) {
  if (message?.characterizeGeneratedArtifactTopologyV3Support === true) {
    _pr101ArtifactTopologyV3RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_TOPOLOGY_V3_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactTopologyV3CharacterizationSupported: true,
      generatedArtifactTopologyV3CharacterizationSchemaVersion: PR101_ARTIFACT_TOPOLOGY_V3_SCHEMA,
      fixedProbeFilename: PR101_ARTIFACT_TOPOLOGY_V3_FILENAME,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      perCandidateStructuralOnly: true,
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

  if (message?.characterizeGeneratedArtifactTopologyV3 === true) {
    _pr101ArtifactTopologyV3RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_TOPOLOGY_V3_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactTopologyV3();
  }

  return _pr101ArtifactTopologyV3PriorExecuteNativeTurn(message);
};
