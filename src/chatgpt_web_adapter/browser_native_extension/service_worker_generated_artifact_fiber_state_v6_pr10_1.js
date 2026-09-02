// PR10.1 v6: bounded, read-only React fiber/application-state shape characterization
// anchored to the already-proven assistant probe turn. Only artifact-relevant
// key names, component names, source kinds, counts, depths, and booleans are
// exported. No DOM text, attribute values, React prop/state values, locators,
// clicks, downloads, writes, DOM stateNode values, or accessor values are read/exported.

const PR101_ARTIFACT_FIBER_STATE_V6_SCHEMA = 6;
const _pr101ArtifactFiberStateV6PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactFiberStateV6RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactFiberStateV6RouteEvidence(url) {
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

function _pr101ArtifactFiberStateV6Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const MAX_FIBERS_PER_TURN = 512;
    const MAX_ANCESTOR_FIBERS_PER_TURN = 10;
    const MAX_CONTAINER_DEPTH = 5;
    const MAX_CONTAINERS_PER_SOURCE = 96;
    const MAX_HIT_SUMMARIES = 48;

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
      const roleNode = turn.querySelector('[data-message-author-role="assistant"],[data-message-author-role="user"]');
      const nestedAuthor = String(roleNode?.getAttribute?.('data-message-author-role') || '').trim();
      if (nestedAuthor === 'assistant' || nestedAuthor === 'user') {
        return { role: nestedAuthor, evidence: 'nested_message_author_role' };
      }
      return { role: null, evidence: null };
    };
    const ownFiber = (element) => {
      if (!(element instanceof Element)) return null;
      let names = [];
      try { names = Object.getOwnPropertyNames(element); } catch {}
      const handle = names.find((name) => name.startsWith('__reactFiber$')) || null;
      if (!handle) return null;
      try { return element[handle] || null; } catch { return null; }
    };
    const componentName = (fiber) => {
      if (!fiber || typeof fiber !== 'object') return 'unknown';
      const type = fiber.elementType || fiber.type;
      if (typeof type === 'string') return safeName(type) || 'unknown';
      if (typeof type === 'function') {
        return safeName(type.displayName) || safeName(type.name) || 'anonymous';
      }
      if (type && typeof type === 'object') {
        return safeName(type.displayName) || safeName(type.name) || 'anonymous';
      }
      return 'unknown';
    };
    const identityLike = (name) => {
      const lower = String(name || '').toLowerCase();
      return lower === 'fileid' || lower === 'file_id' ||
        lower === 'artifactid' || lower === 'artifact_id' ||
        lower === 'assetid' || lower === 'asset_id' ||
        lower === 'attachmentid' || lower === 'attachment_id' ||
        lower === 'generatedfileid' || lower === 'generated_file_id' ||
        lower.includes('fileid') || lower.includes('artifactid') ||
        lower.includes('assetid') || lower.includes('attachmentid');
    };
    const locatorLike = (name) => {
      const lower = String(name || '').toLowerCase();
      return lower === 'href' || lower === 'url' || lower === 'uri' ||
        lower === 'downloadurl' || lower === 'download_url' ||
        lower === 'downloaduri' || lower === 'download_uri' ||
        lower === 'signedurl' || lower === 'signed_url' ||
        lower === 'assetpointer' || lower === 'asset_pointer';
    };
    const artifactLike = (name) => {
      const lower = String(name || '').toLowerCase();
      if (!lower) return false;
      if (identityLike(lower)) return true;
      if (lower === 'file' || lower === 'files') return true;
      if (lower.startsWith('file') || lower.startsWith('artifact') ||
          lower.startsWith('attachment') || lower.startsWith('download')) return true;
      return ['generatedfile', 'uploadedfile', 'asseturl', 'asseturi', 'assetpointer']
        .some((token) => lower.includes(token));
    };
    const containerKind = (value) => Array.isArray(value) ? 'array' : 'object';
    const isTraversableObject = (value) => {
      if (!value || typeof value !== 'object') return false;
      if (typeof Node !== 'undefined' && value instanceof Node) return false;
      if (typeof Window !== 'undefined' && value instanceof Window) return false;
      if (value instanceof Map || value instanceof Set || value instanceof WeakMap || value instanceof WeakSet) return false;
      if (value instanceof ArrayBuffer || ArrayBuffer.isView(value)) return false;
      if (value instanceof Date || value instanceof RegExp || value instanceof Error) return false;
      return true;
    };
    const ownDataEntries = (value) => {
      if (!isTraversableObject(value)) return [];
      let descriptors = null;
      try { descriptors = Object.getOwnPropertyDescriptors(value); } catch { return []; }
      const entries = [];
      for (const [rawName, descriptor] of Object.entries(descriptors || {})) {
        const name = safeName(rawName);
        if (!name || !descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) continue;
        entries.push([name, descriptor.value]);
      }
      return entries;
    };
    const shouldDescendKey = (name) => ![
      'stateNode', 'return', 'child', 'sibling', 'alternate', '_owner', '_debugOwner',
      '_debugSource', 'ref', 'refs'
    ].includes(name);

    const empty = {
      surfaceReady: false,
      selectorKind: 'none',
      visibleTurnCount: 0,
      userProbeMarkerTurnCount: 0,
      assistantCompletionMarkerTurnCount: 0,
      orderedProbeTurnPairPresent: false,
      probePlacementProven: false,
      placementRoleEvidenceKinds: [],
      fiberRootCount: 0,
      scannedFiberCount: 0,
      scannedContainerCount: 0,
      identityKeyHitCount: 0,
      artifactKeyHitCount: 0,
      locatorKeyHitCount: 0,
      artifactContextLocatorHitCount: 0,
      artifactComponentFiberCount: 0,
      artifactComponentNames: [],
      hitSummaries: []
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

    const hitSummaries = [];
    const artifactComponentNames = new Set();
    let fiberRootCount = 0;
    let scannedFiberCount = 0;
    let scannedContainerCount = 0;
    let identityKeyHitCount = 0;
    let artifactKeyHitCount = 0;
    let locatorKeyHitCount = 0;
    let artifactContextLocatorHitCount = 0;
    let artifactComponentFiberCount = 0;

    const scanSource = (root, sourceKind, relationKind, fiberDepth, fiberName) => {
      if (!isTraversableObject(root)) return;
      const queue = [{ value: root, depth: 0 }];
      const seen = new WeakSet();
      let scannedForSource = 0;
      while (queue.length && scannedForSource < MAX_CONTAINERS_PER_SOURCE) {
        const current = queue.shift();
        const value = current?.value;
        const nestedDepth = current?.depth;
        if (!isTraversableObject(value) || seen.has(value)) continue;
        seen.add(value);
        scannedForSource += 1;
        scannedContainerCount += 1;
        const entries = ownDataEntries(value);
        const identityNames = [];
        const artifactNames = [];
        const locatorNames = [];
        for (const [name, childValue] of entries) {
          if (identityLike(name)) identityNames.push(name);
          if (artifactLike(name)) artifactNames.push(name);
          if (locatorLike(name)) locatorNames.push(name);
          if (
            nestedDepth < MAX_CONTAINER_DEPTH &&
            shouldDescendKey(name) &&
            isTraversableObject(childValue)
          ) {
            queue.push({ value: childValue, depth: nestedDepth + 1 });
          }
        }
        const identityKeys = safeNames(identityNames, 24);
        const artifactKeys = safeNames(artifactNames, 32);
        const locatorKeys = safeNames(locatorNames, 24);
        if (!identityKeys.length && !artifactKeys.length && !locatorKeys.length) continue;
        if (identityKeys.length) identityKeyHitCount += 1;
        if (artifactKeys.length) artifactKeyHitCount += 1;
        if (locatorKeys.length) locatorKeyHitCount += 1;
        const componentArtifactLike = artifactLike(fiberName);
        const artifactContext = Boolean(identityKeys.length || artifactKeys.length || componentArtifactLike);
        if (artifactContext && locatorKeys.length) artifactContextLocatorHitCount += 1;
        if (hitSummaries.length < MAX_HIT_SUMMARIES) {
          hitSummaries.push({
            index: hitSummaries.length,
            relationKind,
            fiberDepth,
            componentName: safeName(fiberName) || 'unknown',
            sourceKind,
            nestedDepth,
            containerKind: containerKind(value),
            identityLikeKeyNames: identityKeys,
            artifactLikeKeyNames: artifactKeys,
            locatorLikeKeyNames: locatorKeys,
            artifactContext,
            artifactContextLocator: Boolean(artifactContext && locatorKeys.length)
          });
        }
      }
    };

    const inspectFiber = (fiber, relationKind, fiberDepth) => {
      if (!fiber || typeof fiber !== 'object') return;
      scannedFiberCount += 1;
      const name = componentName(fiber);
      if (artifactLike(name)) {
        artifactComponentFiberCount += 1;
        artifactComponentNames.add(name);
      }
      scanSource(fiber.memoizedProps, 'memoized_props', relationKind, fiberDepth, name);
      scanSource(fiber.pendingProps, 'pending_props', relationKind, fiberDepth, name);
      scanSource(fiber.memoizedState, 'memoized_state', relationKind, fiberDepth, name);
      scanSource(fiber.updateQueue, 'update_queue', relationKind, fiberDepth, name);
      scanSource(fiber.dependencies, 'dependencies', relationKind, fiberDepth, name);
    };

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 4)) {
        const rootFiber = ownFiber(targetTurn);
        if (!rootFiber) continue;
        fiberRootCount += 1;
        inspectFiber(rootFiber, 'turn_root', 0);

        let ancestor = rootFiber.return;
        for (let depth = 1; depth <= MAX_ANCESTOR_FIBERS_PER_TURN && ancestor; depth += 1) {
          inspectFiber(ancestor, 'turn_ancestor', depth);
          ancestor = ancestor.return;
        }

        const stack = [];
        if (rootFiber.child) stack.push({ fiber: rootFiber.child, depth: 1 });
        let descendantCount = 0;
        while (stack.length && descendantCount < MAX_FIBERS_PER_TURN) {
          const current = stack.pop();
          const fiber = current?.fiber;
          const depth = current?.depth;
          if (!fiber || typeof fiber !== 'object') continue;
          descendantCount += 1;
          inspectFiber(fiber, 'turn_descendant', depth);
          if (fiber.sibling) stack.push({ fiber: fiber.sibling, depth });
          if (fiber.child) stack.push({ fiber: fiber.child, depth: Math.min(depth + 1, 64) });
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
      fiberRootCount,
      scannedFiberCount,
      scannedContainerCount,
      identityKeyHitCount,
      artifactKeyHitCount,
      locatorKeyHitCount,
      artifactContextLocatorHitCount,
      artifactComponentFiberCount,
      artifactComponentNames: Array.from(artifactComponentNames).sort().slice(0, 32),
      hitSummaries
    };
  })()`;
}

function _pr101ArtifactFiberStateV6SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactFiberStateV6SafeNames(value, maxItems = 96) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactFiberStateV6SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactFiberStateV6SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactFiberStateV6SafeDepth(value, maximum) {
  return Number.isInteger(value) && value >= 0 && value <= maximum ? value : 0;
}

function _pr101ArtifactFiberStateV6SafeHit(value) {
  if (!value || typeof value !== "object") return null;
  const relationKind = ["turn_root", "turn_ancestor", "turn_descendant"].includes(value.relationKind)
    ? value.relationKind
    : "turn_descendant";
  const sourceKind = ["memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"].includes(value.sourceKind)
    ? value.sourceKind
    : "memoized_state";
  const kind = value.containerKind === "array" ? "array" : "object";
  return {
    index: _pr101ArtifactFiberStateV6SafeCount(value.index, 48),
    relationKind,
    fiberDepth: _pr101ArtifactFiberStateV6SafeDepth(value.fiberDepth, 64),
    componentName: _pr101ArtifactFiberStateV6SafeName(value.componentName) || "unknown",
    sourceKind,
    nestedDepth: _pr101ArtifactFiberStateV6SafeDepth(value.nestedDepth, 5),
    containerKind: kind,
    identityLikeKeyNames: _pr101ArtifactFiberStateV6SafeNames(value.identityLikeKeyNames, 24),
    artifactLikeKeyNames: _pr101ArtifactFiberStateV6SafeNames(value.artifactLikeKeyNames, 32),
    locatorLikeKeyNames: _pr101ArtifactFiberStateV6SafeNames(value.locatorLikeKeyNames, 24),
    artifactContext: value.artifactContext === true,
    artifactContextLocator: value.artifactContextLocator === true
  };
}

async function _pr101CharacterizeGeneratedArtifactFiberStateV6() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_FIBER_STATE_V6_SCHEMA,
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
      fiberRootCount: 0,
      scannedFiberCount: 0,
      scannedContainerCount: 0,
      identityKeyHitCount: 0,
      artifactKeyHitCount: 0,
      locatorKeyHitCount: 0,
      artifactContextLocatorHitCount: 0,
      artifactComponentFiberCount: 0,
      artifactComponentNames: [],
      hitSummaries: [],
      fiberGraphBounded: true,
      artifactRelevantKeysOnly: true,
      accessorPropertiesSkipped: true,
      domStateNodeValuesExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      reactStateValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR10_1_ARTIFACT_FIBER_STATE_V6_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactFiberStateV6RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactFiberStateV6Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_FIBER_STATE_V6_RESULT_MISSING");
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

  const hitSummaries = Array.isArray(value.hitSummaries)
    ? value.hitSummaries.map(_pr101ArtifactFiberStateV6SafeHit).filter(Boolean).slice(0, 48)
    : [];

  return {
    schema: PR101_ARTIFACT_FIBER_STATE_V6_SCHEMA,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactFiberStateV6SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactFiberStateV6SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactFiberStateV6SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactFiberStateV6SafeCount(value.assistantCompletionMarkerTurnCount, 64),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactFiberStateV6SafeNames(value.placementRoleEvidenceKinds, 8),
    fiberRootCount: _pr101ArtifactFiberStateV6SafeCount(value.fiberRootCount, 4),
    scannedFiberCount: _pr101ArtifactFiberStateV6SafeCount(value.scannedFiberCount, 4096),
    scannedContainerCount: _pr101ArtifactFiberStateV6SafeCount(value.scannedContainerCount, 200000),
    identityKeyHitCount: _pr101ArtifactFiberStateV6SafeCount(value.identityKeyHitCount, 4096),
    artifactKeyHitCount: _pr101ArtifactFiberStateV6SafeCount(value.artifactKeyHitCount, 4096),
    locatorKeyHitCount: _pr101ArtifactFiberStateV6SafeCount(value.locatorKeyHitCount, 4096),
    artifactContextLocatorHitCount: _pr101ArtifactFiberStateV6SafeCount(value.artifactContextLocatorHitCount, 4096),
    artifactComponentFiberCount: _pr101ArtifactFiberStateV6SafeCount(value.artifactComponentFiberCount, 4096),
    artifactComponentNames: _pr101ArtifactFiberStateV6SafeNames(value.artifactComponentNames, 32),
    hitSummaries,
    fiberGraphBounded: true,
    artifactRelevantKeysOnly: true,
    accessorPropertiesSkipped: true,
    domStateNodeValuesExcluded: true,
    rawDomExported: false,
    rawTextExported: false,
    attributeValuesExported: false,
    reactPropValuesExported: false,
    reactStateValuesExported: false,
    locatorValuesExported: false,
    clickPerformed: false,
    downloadAttempted: false,
    writePerformed: false,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactFiberStateV6(message) {
  if (message?.characterizeGeneratedArtifactFiberStateV6Support === true) {
    _pr101ArtifactFiberStateV6RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_FIBER_STATE_V6_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactFiberStateV6CharacterizationSupported: true,
      generatedArtifactFiberStateV6CharacterizationSchemaVersion: PR101_ARTIFACT_FIBER_STATE_V6_SCHEMA,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      fiberGraphBounded: true,
      artifactRelevantKeysOnly: true,
      accessorPropertiesSkipped: true,
      domStateNodeValuesExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      reactStateValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false
    };
  }

  if (message?.characterizeGeneratedArtifactFiberStateV6 === true) {
    _pr101ArtifactFiberStateV6RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_FIBER_STATE_V6_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactFiberStateV6();
  }

  return _pr101ArtifactFiberStateV6PriorExecuteNativeTurn(message);
};
