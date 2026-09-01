// PR10.1 v7: targeted artifact-subtree co-occurrence characterization.
// Anchored to the already-proven assistant probe turn. Generic dotted localization
// keys and SVG/use fibers are excluded. Only structural key names, component names,
// source/relation kinds, counts, depths, and booleans are exported; no values,
// locators, DOM text, clicks, downloads, or writes are exported.

const PR101_ARTIFACT_SUBTREE_V7_SCHEMA = 7;
const _pr101ArtifactSubtreeV7PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactSubtreeV7RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactSubtreeV7RouteEvidence(url) {
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

function _pr101ArtifactSubtreeV7Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const MAX_FIBERS_PER_TURN = 512;
    const MAX_ANCESTOR_FIBERS_PER_TURN = 10;
    const MAX_SOURCE_CONTAINER_DEPTH = 5;
    const MAX_SOURCE_CONTAINERS = 96;
    const MAX_ARTIFACT_SUBTREE_DEPTH = 4;
    const MAX_ARTIFACT_SUBTREE_CONTAINERS = 64;
    const MAX_CANDIDATES = 32;

    const safeName = (value) => {
      const text = typeof value === 'string' ? value.trim() : '';
      return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
    };
    const safeNames = (values, limit = 64) => {
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
    const structuralArtifactRoot = (name) => {
      const text = String(name || '');
      if (!text || text.includes('.')) return false;
      const lower = text.toLowerCase();
      return new Set([
        'attachment', 'attachments', 'file', 'files', 'artifact', 'artifacts',
        'generatedfile', 'generatedfiles', 'generated_file', 'generated_files'
      ]).has(lower);
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
    const excludedFiberComponent = (name) => ['svg', 'use', 'path'].includes(String(name || '').toLowerCase());

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
      scannedSourceContainerCount: 0,
      artifactRootHitCount: 0,
      attachmentRootHitCount: 0,
      artifactSubtreeIdentityHitCount: 0,
      artifactSubtreeLocatorHitCount: 0,
      sameContainerIdentityHitCount: 0,
      sameContainerLocatorHitCount: 0,
      strongCandidateCount: 0,
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

    const strongCandidates = [];
    const weakCandidates = [];
    let fiberRootCount = 0;
    let scannedFiberCount = 0;
    let scannedSourceContainerCount = 0;
    let artifactRootHitCount = 0;
    let attachmentRootHitCount = 0;
    let artifactSubtreeIdentityHitCount = 0;
    let artifactSubtreeLocatorHitCount = 0;
    let sameContainerIdentityHitCount = 0;
    let sameContainerLocatorHitCount = 0;

    const scanArtifactSubtree = (root) => {
      if (!isTraversableObject(root)) {
        return {
          scannedContainerCount: 0,
          identityLikeKeyNames: [],
          locatorLikeKeyNames: [],
          structuralArtifactKeyNames: [],
          identityMinDepth: null,
          locatorMinDepth: null
        };
      }
      const queue = [{ value: root, depth: 0 }];
      const seen = new WeakSet();
      const identityNames = new Set();
      const locatorNames = new Set();
      const structuralNames = new Set();
      let scannedContainerCount = 0;
      let identityMinDepth = null;
      let locatorMinDepth = null;
      while (queue.length && scannedContainerCount < MAX_ARTIFACT_SUBTREE_CONTAINERS) {
        const current = queue.shift();
        const value = current?.value;
        const depth = current?.depth;
        if (!isTraversableObject(value) || seen.has(value)) continue;
        seen.add(value);
        scannedContainerCount += 1;
        const entries = ownDataEntries(value);
        for (const [name, childValue] of entries) {
          if (identityLike(name)) {
            identityNames.add(name);
            if (identityMinDepth === null || depth < identityMinDepth) identityMinDepth = depth;
          }
          if (locatorLike(name)) {
            locatorNames.add(name);
            if (locatorMinDepth === null || depth < locatorMinDepth) locatorMinDepth = depth;
          }
          if (structuralArtifactRoot(name)) structuralNames.add(name);
          if (
            depth < MAX_ARTIFACT_SUBTREE_DEPTH &&
            shouldDescendKey(name) &&
            isTraversableObject(childValue)
          ) {
            queue.push({ value: childValue, depth: depth + 1 });
          }
        }
      }
      return {
        scannedContainerCount,
        identityLikeKeyNames: safeNames(Array.from(identityNames), 24),
        locatorLikeKeyNames: safeNames(Array.from(locatorNames), 24),
        structuralArtifactKeyNames: safeNames(Array.from(structuralNames), 24),
        identityMinDepth,
        locatorMinDepth
      };
    };

    const scanSource = (root, sourceKind, relationKind, fiberDepth, fiberName) => {
      if (!isTraversableObject(root) || excludedFiberComponent(fiberName)) return;
      const queue = [{ value: root, depth: 0 }];
      const seen = new WeakSet();
      let scannedForSource = 0;
      while (queue.length && scannedForSource < MAX_SOURCE_CONTAINERS) {
        const current = queue.shift();
        const value = current?.value;
        const nestedDepth = current?.depth;
        if (!isTraversableObject(value) || seen.has(value)) continue;
        seen.add(value);
        scannedForSource += 1;
        scannedSourceContainerCount += 1;
        const entries = ownDataEntries(value);
        const rootEntries = entries.filter(([name]) => structuralArtifactRoot(name));
        const sameIdentity = safeNames(entries.map(([name]) => name).filter(identityLike), 24);
        const sameLocator = safeNames(entries.map(([name]) => name).filter(locatorLike), 24);
        if (sameIdentity.length) sameContainerIdentityHitCount += 1;
        if (sameLocator.length && rootEntries.length) sameContainerLocatorHitCount += 1;

        for (const [rootKey, childValue] of rootEntries) {
          artifactRootHitCount += 1;
          if (String(rootKey).toLowerCase().startsWith('attachment')) attachmentRootHitCount += 1;
          const subtree = scanArtifactSubtree(childValue);
          if (subtree.identityLikeKeyNames.length) artifactSubtreeIdentityHitCount += 1;
          if (subtree.locatorLikeKeyNames.length) artifactSubtreeLocatorHitCount += 1;
          const strong = Boolean(
            sameIdentity.length || sameLocator.length ||
            subtree.identityLikeKeyNames.length || subtree.locatorLikeKeyNames.length
          );
          const summary = {
            relationKind,
            fiberDepth,
            componentName: safeName(fiberName) || 'unknown',
            sourceKind,
            sourceNestedDepth: nestedDepth,
            sourceContainerKind: containerKind(value),
            artifactRootKeyNames: [rootKey],
            sameContainerIdentityLikeKeyNames: sameIdentity,
            sameContainerLocatorLikeKeyNames: sameLocator,
            subtreeContainerCount: subtree.scannedContainerCount,
            subtreeIdentityLikeKeyNames: subtree.identityLikeKeyNames,
            subtreeLocatorLikeKeyNames: subtree.locatorLikeKeyNames,
            subtreeStructuralArtifactKeyNames: subtree.structuralArtifactKeyNames,
            subtreeIdentityMinDepth: subtree.identityMinDepth,
            subtreeLocatorMinDepth: subtree.locatorMinDepth,
            strongCandidate: strong
          };
          if (strong) strongCandidates.push(summary);
          else weakCandidates.push(summary);
        }

        for (const [name, childValue] of entries) {
          if (
            nestedDepth < MAX_SOURCE_CONTAINER_DEPTH &&
            shouldDescendKey(name) &&
            isTraversableObject(childValue)
          ) {
            queue.push({ value: childValue, depth: nestedDepth + 1 });
          }
        }
      }
    };

    const inspectFiber = (fiber, relationKind, fiberDepth) => {
      if (!fiber || typeof fiber !== 'object') return;
      scannedFiberCount += 1;
      const name = componentName(fiber);
      if (excludedFiberComponent(name)) return;
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

    const candidateSummaries = [...strongCandidates, ...weakCandidates]
      .slice(0, MAX_CANDIDATES)
      .map((summary, index) => ({ index, ...summary }));

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
      scannedSourceContainerCount,
      artifactRootHitCount,
      attachmentRootHitCount,
      artifactSubtreeIdentityHitCount,
      artifactSubtreeLocatorHitCount,
      sameContainerIdentityHitCount,
      sameContainerLocatorHitCount,
      strongCandidateCount: strongCandidates.length,
      candidateSummaries
    };
  })()`;
}

function _pr101ArtifactSubtreeV7SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactSubtreeV7SafeNames(value, maxItems = 64) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactSubtreeV7SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactSubtreeV7SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactSubtreeV7SafeDepth(value, maximum) {
  return Number.isInteger(value) && value >= 0 && value <= maximum ? value : null;
}

function _pr101ArtifactSubtreeV7SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const relationKind = ["turn_root", "turn_ancestor", "turn_descendant"].includes(value.relationKind)
    ? value.relationKind
    : "turn_descendant";
  const sourceKind = ["memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"].includes(value.sourceKind)
    ? value.sourceKind
    : "memoized_state";
  const sourceContainerKind = ["object", "array"].includes(value.sourceContainerKind)
    ? value.sourceContainerKind
    : "object";
  return {
    index: _pr101ArtifactSubtreeV7SafeCount(value.index, 32),
    relationKind,
    fiberDepth: _pr101ArtifactSubtreeV7SafeCount(value.fiberDepth, 64),
    componentName: _pr101ArtifactSubtreeV7SafeName(value.componentName) || "unknown",
    sourceKind,
    sourceNestedDepth: _pr101ArtifactSubtreeV7SafeCount(value.sourceNestedDepth, 5),
    sourceContainerKind,
    artifactRootKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.artifactRootKeyNames, 8),
    sameContainerIdentityLikeKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.sameContainerIdentityLikeKeyNames, 24),
    sameContainerLocatorLikeKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.sameContainerLocatorLikeKeyNames, 24),
    subtreeContainerCount: _pr101ArtifactSubtreeV7SafeCount(value.subtreeContainerCount, 64),
    subtreeIdentityLikeKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.subtreeIdentityLikeKeyNames, 24),
    subtreeLocatorLikeKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.subtreeLocatorLikeKeyNames, 24),
    subtreeStructuralArtifactKeyNames: _pr101ArtifactSubtreeV7SafeNames(value.subtreeStructuralArtifactKeyNames, 24),
    subtreeIdentityMinDepth: _pr101ArtifactSubtreeV7SafeDepth(value.subtreeIdentityMinDepth, 4),
    subtreeLocatorMinDepth: _pr101ArtifactSubtreeV7SafeDepth(value.subtreeLocatorMinDepth, 4),
    strongCandidate: value.strongCandidate === true
  };
}

async function _pr101CharacterizeGeneratedArtifactSubtreeV7() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_SUBTREE_V7_SCHEMA,
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
      scannedSourceContainerCount: 0,
      artifactRootHitCount: 0,
      attachmentRootHitCount: 0,
      artifactSubtreeIdentityHitCount: 0,
      artifactSubtreeLocatorHitCount: 0,
      sameContainerIdentityHitCount: 0,
      sameContainerLocatorHitCount: 0,
      strongCandidateCount: 0,
      candidateSummaries: [],
      fiberGraphBounded: true,
      structuralArtifactRootsOnly: true,
      dottedLocalizationKeysExcluded: true,
      svgUseFibersExcluded: true,
      accessorPropertiesSkipped: true,
      domStateNodeValuesExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      reactStateValuesExported: false,
      artifactSubtreeValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) {
    throw new Error("PR10_1_ARTIFACT_SUBTREE_V7_RUNTIME_TAB_NOT_CHATGPT");
  }
  const route = _pr101ArtifactSubtreeV7RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactSubtreeV7Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("PR10_1_ARTIFACT_SUBTREE_V7_RESULT_MISSING");
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
    ? value.candidateSummaries.map(_pr101ArtifactSubtreeV7SafeCandidate).filter(Boolean).slice(0, 32)
    : [];

  return {
    schema: PR101_ARTIFACT_SUBTREE_V7_SCHEMA,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactSubtreeV7SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactSubtreeV7SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactSubtreeV7SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactSubtreeV7SafeCount(value.assistantCompletionMarkerTurnCount, 64),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactSubtreeV7SafeNames(value.placementRoleEvidenceKinds, 8),
    fiberRootCount: _pr101ArtifactSubtreeV7SafeCount(value.fiberRootCount, 4),
    scannedFiberCount: _pr101ArtifactSubtreeV7SafeCount(value.scannedFiberCount, 4096),
    scannedSourceContainerCount: _pr101ArtifactSubtreeV7SafeCount(value.scannedSourceContainerCount, 200000),
    artifactRootHitCount: _pr101ArtifactSubtreeV7SafeCount(value.artifactRootHitCount, 4096),
    attachmentRootHitCount: _pr101ArtifactSubtreeV7SafeCount(value.attachmentRootHitCount, 4096),
    artifactSubtreeIdentityHitCount: _pr101ArtifactSubtreeV7SafeCount(value.artifactSubtreeIdentityHitCount, 4096),
    artifactSubtreeLocatorHitCount: _pr101ArtifactSubtreeV7SafeCount(value.artifactSubtreeLocatorHitCount, 4096),
    sameContainerIdentityHitCount: _pr101ArtifactSubtreeV7SafeCount(value.sameContainerIdentityHitCount, 4096),
    sameContainerLocatorHitCount: _pr101ArtifactSubtreeV7SafeCount(value.sameContainerLocatorHitCount, 4096),
    strongCandidateCount: _pr101ArtifactSubtreeV7SafeCount(value.strongCandidateCount, 4096),
    candidateSummaries: summaries,
    fiberGraphBounded: true,
    structuralArtifactRootsOnly: true,
    dottedLocalizationKeysExcluded: true,
    svgUseFibersExcluded: true,
    accessorPropertiesSkipped: true,
    domStateNodeValuesExcluded: true,
    rawDomExported: false,
    rawTextExported: false,
    attributeValuesExported: false,
    reactPropValuesExported: false,
    reactStateValuesExported: false,
    artifactSubtreeValuesExported: false,
    locatorValuesExported: false,
    clickPerformed: false,
    downloadAttempted: false,
    writePerformed: false,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactSubtreeV7(message) {
  if (message?.characterizeGeneratedArtifactSubtreeV7Support === true) {
    _pr101ArtifactSubtreeV7RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SUBTREE_V7_SUPPORT_PROBE_MUST_BE_NO_WRITE"
    );
    return {
      generatedArtifactSubtreeV7CharacterizationSupported: true,
      generatedArtifactSubtreeV7CharacterizationSchemaVersion: PR101_ARTIFACT_SUBTREE_V7_SCHEMA,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      fiberGraphBounded: true,
      structuralArtifactRootsOnly: true,
      dottedLocalizationKeysExcluded: true,
      svgUseFibersExcluded: true,
      accessorPropertiesSkipped: true,
      domStateNodeValuesExcluded: true,
      rawDomExported: false,
      rawTextExported: false,
      attributeValuesExported: false,
      reactPropValuesExported: false,
      reactStateValuesExported: false,
      artifactSubtreeValuesExported: false,
      locatorValuesExported: false,
      clickPerformed: false,
      downloadAttempted: false,
      writePerformed: false
    };
  }

  if (message?.characterizeGeneratedArtifactSubtreeV7 === true) {
    _pr101ArtifactSubtreeV7RejectWriteBearingMessage(
      message,
      "PR10_1_ARTIFACT_SUBTREE_V7_PROBE_MUST_BE_NO_WRITE"
    );
    return _pr101CharacterizeGeneratedArtifactSubtreeV7();
  }

  return _pr101ArtifactSubtreeV7PriorExecuteNativeTurn(message);
};