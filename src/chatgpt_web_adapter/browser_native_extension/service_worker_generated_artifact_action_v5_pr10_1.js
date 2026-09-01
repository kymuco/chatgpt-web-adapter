// PR10.1 v5: bounded, read-only characterization of real HTML action hosts
// inside the already-proven assistant probe turn. PRE/CODE/SVG surfaces are
// excluded. Only structural names/counts/booleans are exported; no attribute,
// React prop, locator, DOM text, click, download, or write values are exported.

const PR101_ARTIFACT_ACTION_V5_SCHEMA = 5;
const PR101_ARTIFACT_ACTION_V5_USER_MARKER = "CWA_PR10_1_ARTIFACT_PROBE";
const PR101_ARTIFACT_ACTION_V5_ASSISTANT_MARKER = "ARTIFACT_PROBE_CREATED";
const _pr101ArtifactActionV5PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactActionV5RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactActionV5RouteEvidence(url) {
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

function _pr101ArtifactActionV5Expression() {
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
      const roleNode = turn.querySelector('[data-message-author-role="assistant"],[data-message-author-role="user"]');
      const nestedAuthor = String(roleNode?.getAttribute?.('data-message-author-role') || '').trim();
      if (nestedAuthor === 'assistant' || nestedAuthor === 'user') {
        return { role: nestedAuthor, evidence: 'nested_message_author_role' };
      }
      return { role: null, evidence: null };
    };
    const attributeNames = (element) => {
      if (!(element instanceof Element)) return [];
      return safeNames(Array.from(element.attributes || []).map((attribute) => attribute?.name), 64);
    };
    const ownReactHandles = (element) => {
      if (!(element instanceof Element)) {
        return { props: null, fiber: null, fiberPresent: false, propsPresent: false };
      }
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
      for (let depth = 0; depth < 8 && fiber; depth += 1, fiber = fiber.return) {
        const type = fiber.elementType || fiber.type;
        if (typeof type === 'string') {
          const host = safeName(type);
          if (host) names.push(host);
        } else if (typeof type === 'function') {
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
      return safeNames(names, 64);
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
      if (lower.startsWith('file') || lower.startsWith('artifact') ||
          lower.startsWith('attachment') || lower.startsWith('download')) return true;
      return ['generatedfile', 'uploadedfile', 'assetid', 'asseturl', 'asseturi', 'assetpointer']
        .some((token) => lower.includes(token));
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
      actionHostCount: 0,
      hrefActionHostCount: 0,
      downloadActionHostCount: 0,
      identitySignalActionCount: 0,
      artifactSignalActionCount: 0,
      locatorSignalActionCount: 0,
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
        if (firstUserProbeIndex >= 0 && index > firstUserProbeIndex && firstAssistantCompletionAfterUserIndex < 0) {
          firstAssistantCompletionAfterUserIndex = index;
        }
      }
    }
    const orderedProbeTurnPairPresent = (
      firstUserProbeIndex >= 0 && firstAssistantCompletionAfterUserIndex > firstUserProbeIndex
    );
    const probePlacementProven = Boolean(
      orderedProbeTurnPairPresent && userProbeMarkerTurnCount >= 1 && assistantCompletionMarkerTurnCount >= 1
    );

    const summaries = [];
    let actionHostCount = 0;
    let hrefActionHostCount = 0;
    let downloadActionHostCount = 0;
    let identitySignalActionCount = 0;
    let artifactSignalActionCount = 0;
    let locatorSignalActionCount = 0;

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 8)) {
        const hosts = Array.from(
          targetTurn.querySelectorAll('a,button,[role="button"],[role="link"]')
        ).filter((element) => {
          if (!(element instanceof Element) || !visible(element)) return false;
          const excluded = element.closest('pre,code,svg');
          return !(excluded instanceof Element && targetTurn.contains(excluded));
        }).slice(0, 64);
        actionHostCount += hosts.length;

        for (const host of hosts) {
          if (summaries.length >= 32) break;
          const attrs = attributeNames(host);
          const ownProps = reactPropNames(host);
          const ownComponents = reactComponentNames(host);
          const ancestorAttrs = new Set();
          const ancestorProps = new Set();
          const ancestorComponents = new Set();
          let current = host.parentElement;
          for (let depth = 1; depth <= 6 && current && targetTurn.contains(current); depth += 1) {
            const excluded = current.closest('svg');
            if (!(excluded instanceof Element && targetTurn.contains(excluded))) {
              for (const name of attributeNames(current)) ancestorAttrs.add(name);
              for (const name of reactPropNames(current)) ancestorProps.add(name);
              for (const name of reactComponentNames(current)) ancestorComponents.add(name);
            }
            if (current === targetTurn) break;
            current = current.parentElement;
          }
          const allAttrs = safeNames([...attrs, ...Array.from(ancestorAttrs)], 128);
          const allProps = safeNames([...ownProps, ...Array.from(ancestorProps)], 192);
          const allComponents = safeNames([...ownComponents, ...Array.from(ancestorComponents)], 96);
          const identityNames = identityLike(allProps);
          const locatorNames = locatorLike(allProps);
          const artifactPropNames = artifactLike(allProps);
          const artifactAttrNames = artifactLike(allAttrs);
          const artifactComponentNames = artifactLike(allComponents);
          const hrefPresent = host.hasAttribute('href');
          const downloadPresent = host.hasAttribute('download');
          if (hrefPresent) hrefActionHostCount += 1;
          if (downloadPresent) downloadActionHostCount += 1;
          const identitySignal = identityNames.length > 0;
          const artifactSignal = Boolean(
            artifactPropNames.length || artifactAttrNames.length || artifactComponentNames.length || downloadPresent
          );
          const locatorSignal = Boolean(locatorNames.length || hrefPresent);
          if (identitySignal) identitySignalActionCount += 1;
          if (artifactSignal) artifactSignalActionCount += 1;
          if (locatorSignal) locatorSignalActionCount += 1;
          const handles = ownReactHandles(host);
          summaries.push({
            index: summaries.length,
            tagName: safeName(String(host.tagName || '').toLowerCase()) || 'unknown',
            depthToTurn: depthToTurn(host, targetTurn),
            interactiveKind: interactiveKind(host),
            hrefAttributePresent: hrefPresent,
            downloadAttributePresent: downloadPresent,
            hostAttributeNames: attrs,
            boundedAttributeNames: allAttrs,
            reactFiberPropertyPresent: handles.fiberPresent,
            reactPropsPropertyPresent: handles.propsPresent,
            hostReactPropNames: ownProps,
            boundedReactPropNames: allProps,
            identityLikeReactPropNames: identityNames,
            locatorLikeReactPropNames: locatorNames,
            artifactLikeReactPropNames: artifactPropNames,
            boundedReactComponentNames: allComponents,
            artifactLikeReactComponentNames: artifactComponentNames,
            artifactLikeAttributeNames: artifactAttrNames,
            identitySignal,
            artifactSignal,
            locatorSignal
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
      actionHostCount,
      hrefActionHostCount,
      downloadActionHostCount,
      identitySignalActionCount,
      artifactSignalActionCount,
      locatorSignalActionCount,
      candidateSummaries: summaries
    };
  })()`;
}

function _pr101ArtifactActionV5SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactActionV5SafeNames(value, maxItems = 192) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactActionV5SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactActionV5SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactActionV5SafeNullableDepth(value) {
  return Number.isInteger(value) && value >= 0 && value <= 16 ? value : null;
}

function _pr101ArtifactActionV5SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const interactiveKind = ["none", "a", "button", "role_button", "role_link"].includes(value.interactiveKind)
    ? value.interactiveKind
    : "none";
  return {
    index: _pr101ArtifactActionV5SafeCount(value.index, 32),
    tagName: _pr101ArtifactActionV5SafeName(value.tagName) || "unknown",
    depthToTurn: _pr101ArtifactActionV5SafeNullableDepth(value.depthToTurn),
    interactiveKind,
    hrefAttributePresent: value.hrefAttributePresent === true,
    downloadAttributePresent: value.downloadAttributePresent === true,
    hostAttributeNames: _pr101ArtifactActionV5SafeNames(value.hostAttributeNames, 64),
    boundedAttributeNames: _pr101ArtifactActionV5SafeNames(value.boundedAttributeNames, 128),
    reactFiberPropertyPresent: value.reactFiberPropertyPresent === true,
    reactPropsPropertyPresent: value.reactPropsPropertyPresent === true,
    hostReactPropNames: _pr101ArtifactActionV5SafeNames(value.hostReactPropNames, 160),
    boundedReactPropNames: _pr101ArtifactActionV5SafeNames(value.boundedReactPropNames, 192),
    identityLikeReactPropNames: _pr101ArtifactActionV5SafeNames(value.identityLikeReactPropNames, 32),
    locatorLikeReactPropNames: _pr101ArtifactActionV5SafeNames(value.locatorLikeReactPropNames, 32),
    artifactLikeReactPropNames: _pr101ArtifactActionV5SafeNames(value.artifactLikeReactPropNames, 64),
    boundedReactComponentNames: _pr101ArtifactActionV5SafeNames(value.boundedReactComponentNames, 96),
    artifactLikeReactComponentNames: _pr101ArtifactActionV5SafeNames(value.artifactLikeReactComponentNames, 64),
    artifactLikeAttributeNames: _pr101ArtifactActionV5SafeNames(value.artifactLikeAttributeNames, 64),
    identitySignal: value.identitySignal === true,
    artifactSignal: value.artifactSignal === true,
    locatorSignal: value.locatorSignal === true
  };
}

async function _pr101CharacterizeGeneratedArtifactActionV5() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_ACTION_V5_SCHEMA,
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
      actionHostCount: 0,
      hrefActionHostCount: 0,
      downloadActionHostCount: 0,
      identitySignalActionCount: 0,
      artifactSignalActionCount: 0,
      locatorSignalActionCount: 0,
      candidateSummaries: [],
      preCodeSvgExcluded: true,
      hostActionOnly: true,
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
    throw new Error("PR10_1_ARTIFACT_ACTION_V5_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactActionV5RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactActionV5Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_ACTION_V5_RESULT_MISSING");
    }
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(targets.find((target) => target.tabId === runtimeTabId)?.attached);
    } catch {
      debuggerAttachedAfter = null;
    }
  }

  const summaries = Array.isArray(value.candidateSummaries)
    ? value.candidateSummaries.map(_pr101ArtifactActionV5SafeCandidate).filter(Boolean).slice(0, 32)
    : [];

  return {
    schema: PR101_ARTIFACT_ACTION_V5_SCHEMA,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactActionV5SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactActionV5SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactActionV5SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactActionV5SafeCount(value.assistantCompletionMarkerTurnCount, 64),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactActionV5SafeNames(value.placementRoleEvidenceKinds, 8),
    actionHostCount: _pr101ArtifactActionV5SafeCount(value.actionHostCount, 64),
    hrefActionHostCount: _pr101ArtifactActionV5SafeCount(value.hrefActionHostCount, 64),
    downloadActionHostCount: _pr101ArtifactActionV5SafeCount(value.downloadActionHostCount, 64),
    identitySignalActionCount: _pr101ArtifactActionV5SafeCount(value.identitySignalActionCount, 64),
    artifactSignalActionCount: _pr101ArtifactActionV5SafeCount(value.artifactSignalActionCount, 64),
    locatorSignalActionCount: _pr101ArtifactActionV5SafeCount(value.locatorSignalActionCount, 64),
    candidateSummaries: summaries,
    preCodeSvgExcluded: true,
    hostActionOnly: true,
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

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactActionV5(message) {
  if (message?.characterizeGeneratedArtifactActionV5Support === true) {
    _pr101ArtifactActionV5RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_ACTION_V5_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactActionV5CharacterizationSupported: true,
      generatedArtifactActionV5CharacterizationSchemaVersion: PR101_ARTIFACT_ACTION_V5_SCHEMA,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      preCodeSvgExcluded: true,
      hostActionOnly: true,
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

  if (message?.characterizeGeneratedArtifactActionV5 === true) {
    _pr101ArtifactActionV5RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_ACTION_V5_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactActionV5();
  }

  return _pr101ArtifactActionV5PriorExecuteNativeTurn(message);
};
