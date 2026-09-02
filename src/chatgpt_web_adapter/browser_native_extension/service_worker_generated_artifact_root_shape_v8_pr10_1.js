// PR10.1 v8: targeted artifact-root value-shape characterization.
// Anchored to the already-proven assistant probe turn and limited to exact structural
// artifact roots. Only type enums, empty/non-empty shape, cardinality buckets,
// component/source metadata, counts, depths, and booleans are exported. Root values,
// child values, locators, DOM text, clicks, downloads, and writes are never exported.

const PR101_ARTIFACT_ROOT_SHAPE_V8_SCHEMA = 8;
const _pr101ArtifactRootShapeV8PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactRootShapeV8RejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr101ArtifactRootShapeV8RouteEvidence(url) {
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

function _pr101ArtifactRootShapeV8Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const MAX_FIBERS_PER_TURN = 512;
    const MAX_ANCESTOR_FIBERS_PER_TURN = 10;
    const MAX_SOURCE_CONTAINER_DEPTH = 5;
    const MAX_SOURCE_CONTAINERS = 96;
    const MAX_CANDIDATES = 32;
    const MAX_ELEMENT_KIND_INSPECTION = 16;

    const safeName = (value) => {
      const text = typeof value === 'string' ? value.trim() : '';
      return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
    };
    const safeNames = (values, limit = 32) => {
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
      if (dataTurn === 'assistant' || dataTurn === 'user') return { role: dataTurn, evidence: 'data_turn' };
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
      if (typeof type === 'function') return safeName(type.displayName) || safeName(type.name) || 'anonymous';
      if (type && typeof type === 'object') return safeName(type.displayName) || safeName(type.name) || 'anonymous';
      return 'unknown';
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
    const valueKind = (value) => {
      if (value === null) return 'null';
      if (Array.isArray(value)) return 'array';
      const kind = typeof value;
      if (kind === 'undefined' || kind === 'string' || kind === 'number' || kind === 'boolean' ||
          kind === 'bigint' || kind === 'symbol' || kind === 'function') return kind;
      if (kind === 'object') return 'object';
      return 'other';
    };
    const cardinalityBucket = (count) => {
      if (!Number.isInteger(count) || count < 0) return 'unknown';
      if (count === 0) return 'zero';
      if (count === 1) return 'one';
      if (count <= 4) return 'two_to_four';
      if (count <= 16) return 'five_to_sixteen';
      return 'over_sixteen';
    };
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
    const rootShape = (value) => {
      const kind = valueKind(value);
      if (kind === 'array') {
        const elementKinds = [];
        const inspected = Math.min(value.length, MAX_ELEMENT_KIND_INSPECTION);
        for (let index = 0; index < inspected; index += 1) {
          let descriptor = null;
          try { descriptor = Object.getOwnPropertyDescriptor(value, String(index)); } catch {}
          if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) continue;
          elementKinds.push(valueKind(descriptor.value));
        }
        return {
          rootValueKind: 'array',
          rootEmpty: value.length === 0,
          rootCardinalityBucket: cardinalityBucket(value.length),
          rootElementValueKinds: safeNames(elementKinds, 12)
        };
      }
      if (kind === 'object') {
        const entries = ownDataEntries(value);
        return {
          rootValueKind: 'object',
          rootEmpty: entries.length === 0,
          rootCardinalityBucket: cardinalityBucket(entries.length),
          rootElementValueKinds: []
        };
      }
      return {
        rootValueKind: kind,
        rootEmpty: kind === 'null' || kind === 'undefined',
        rootCardinalityBucket: 'not_applicable',
        rootElementValueKinds: []
      };
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
      fiberRootCount: 0,
      scannedFiberCount: 0,
      scannedSourceContainerCount: 0,
      artifactRootHitCount: 0,
      attachmentRootHitCount: 0,
      nullOrUndefinedRootCount: 0,
      emptyArrayRootCount: 0,
      nonemptyArrayRootCount: 0,
      emptyObjectRootCount: 0,
      nonemptyObjectRootCount: 0,
      scalarOrFunctionRootCount: 0,
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
    const orderedProbeTurnPairPresent = firstUserProbeIndex >= 0 && firstAssistantCompletionAfterUserIndex > firstUserProbeIndex;
    const probePlacementProven = Boolean(
      orderedProbeTurnPairPresent && userProbeMarkerTurnCount >= 1 && assistantCompletionMarkerTurnCount >= 1
    );

    const candidates = [];
    let fiberRootCount = 0;
    let scannedFiberCount = 0;
    let scannedSourceContainerCount = 0;
    let artifactRootHitCount = 0;
    let attachmentRootHitCount = 0;
    let nullOrUndefinedRootCount = 0;
    let emptyArrayRootCount = 0;
    let nonemptyArrayRootCount = 0;
    let emptyObjectRootCount = 0;
    let nonemptyObjectRootCount = 0;
    let scalarOrFunctionRootCount = 0;

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
        for (const [rootKey, childValue] of entries.filter(([name]) => structuralArtifactRoot(name))) {
          artifactRootHitCount += 1;
          if (String(rootKey).toLowerCase().startsWith('attachment')) attachmentRootHitCount += 1;
          const shape = rootShape(childValue);
          if (shape.rootValueKind === 'null' || shape.rootValueKind === 'undefined') nullOrUndefinedRootCount += 1;
          else if (shape.rootValueKind === 'array' && shape.rootEmpty) emptyArrayRootCount += 1;
          else if (shape.rootValueKind === 'array') nonemptyArrayRootCount += 1;
          else if (shape.rootValueKind === 'object' && shape.rootEmpty) emptyObjectRootCount += 1;
          else if (shape.rootValueKind === 'object') nonemptyObjectRootCount += 1;
          else scalarOrFunctionRootCount += 1;
          candidates.push({
            relationKind,
            fiberDepth,
            componentName: safeName(fiberName) || 'unknown',
            sourceKind,
            sourceNestedDepth: nestedDepth,
            sourceContainerKind: Array.isArray(value) ? 'array' : 'object',
            artifactRootKeyName: rootKey,
            rootValueKind: shape.rootValueKind,
            rootEmpty: shape.rootEmpty,
            rootCardinalityBucket: shape.rootCardinalityBucket,
            rootElementValueKinds: shape.rootElementValueKinds
          });
        }
        for (const [name, childValue] of entries) {
          if (nestedDepth < MAX_SOURCE_CONTAINER_DEPTH && shouldDescendKey(name) && isTraversableObject(childValue)) {
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

    const candidateSummaries = candidates.slice(0, MAX_CANDIDATES).map((summary, index) => ({ index, ...summary }));
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
      nullOrUndefinedRootCount,
      emptyArrayRootCount,
      nonemptyArrayRootCount,
      emptyObjectRootCount,
      nonemptyObjectRootCount,
      scalarOrFunctionRootCount,
      candidateSummaries
    };
  })()`;
}

function _pr101ArtifactRootShapeV8SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}

function _pr101ArtifactRootShapeV8SafeNames(value, maxItems = 32) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactRootShapeV8SafeName(item);
    if (!name) continue;
    output.push(name);
    if (output.length >= maxItems) break;
  }
  return Array.from(new Set(output)).sort();
}

function _pr101ArtifactRootShapeV8SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}

function _pr101ArtifactRootShapeV8SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const relationKind = ["turn_root", "turn_ancestor", "turn_descendant"].includes(value.relationKind)
    ? value.relationKind : "turn_descendant";
  const sourceKind = ["memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"].includes(value.sourceKind)
    ? value.sourceKind : "memoized_state";
  const sourceContainerKind = ["object", "array"].includes(value.sourceContainerKind)
    ? value.sourceContainerKind : "object";
  const rootValueKind = ["null", "undefined", "array", "object", "string", "number", "boolean", "bigint", "symbol", "function", "other"].includes(value.rootValueKind)
    ? value.rootValueKind : "other";
  const rootCardinalityBucket = ["zero", "one", "two_to_four", "five_to_sixteen", "over_sixteen", "not_applicable", "unknown"].includes(value.rootCardinalityBucket)
    ? value.rootCardinalityBucket : "unknown";
  return {
    index: _pr101ArtifactRootShapeV8SafeCount(value.index, 32),
    relationKind,
    fiberDepth: _pr101ArtifactRootShapeV8SafeCount(value.fiberDepth, 64),
    componentName: _pr101ArtifactRootShapeV8SafeName(value.componentName) || "unknown",
    sourceKind,
    sourceNestedDepth: _pr101ArtifactRootShapeV8SafeCount(value.sourceNestedDepth, 5),
    sourceContainerKind,
    artifactRootKeyName: _pr101ArtifactRootShapeV8SafeName(value.artifactRootKeyName) || "unknown",
    rootValueKind,
    rootEmpty: value.rootEmpty === true,
    rootCardinalityBucket,
    rootElementValueKinds: _pr101ArtifactRootShapeV8SafeNames(value.rootElementValueKinds, 12)
  };
}

async function _pr101CharacterizeGeneratedArtifactRootShapeV8() {
  const runtimeTabId = await storedRuntimeTabId();
  const commonSafety = {
    fiberGraphBounded: true,
    structuralArtifactRootsOnly: true,
    dottedLocalizationKeysExcluded: true,
    svgUseFibersExcluded: true,
    accessorPropertiesSkipped: true,
    domStateNodeValuesExcluded: true,
    rootValueTypesOnly: true,
    rootCardinalityBucketOnly: true,
    rootValuesExported: false,
    childValuesExported: false,
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
  if (!Number.isInteger(runtimeTabId)) {
    return {
      schema: PR101_ARTIFACT_ROOT_SHAPE_V8_SCHEMA,
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
      nullOrUndefinedRootCount: 0,
      emptyArrayRootCount: 0,
      nonemptyArrayRootCount: 0,
      emptyObjectRootCount: 0,
      nonemptyObjectRootCount: 0,
      scalarOrFunctionRootCount: 0,
      candidateSummaries: [],
      ...commonSafety,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) throw new Error("PR10_1_ARTIFACT_ROOT_SHAPE_V8_RUNTIME_TAB_NOT_CHATGPT");
  const route = _pr101ArtifactRootShapeV8RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let debuggerAttachedAfter = null;
  let value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression: _pr101ArtifactRootShapeV8Expression(),
      returnByValue: true,
      awaitPromise: true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") throw new Error("PR10_1_ARTIFACT_ROOT_SHAPE_V8_RESULT_MISSING");
  } finally {
    if (attached) { try { await chrome.debugger.detach(debuggee); } catch {} }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(targets.find((target) => target.tabId === runtimeTabId)?.attached);
    } catch { debuggerAttachedAfter = null; }
  }

  const summaries = Array.isArray(value.candidateSummaries)
    ? value.candidateSummaries.map(_pr101ArtifactRootShapeV8SafeCandidate).filter(Boolean).slice(0, 32)
    : [];
  return {
    schema: PR101_ARTIFACT_ROOT_SHAPE_V8_SCHEMA,
    runtimeTabPresent: true,
    runtimeRouteKind: route.routeKind,
    runtimeConversationIdPresent: route.conversationIdPresent,
    surfaceReady: value.surfaceReady === true,
    selectorKind: _pr101ArtifactRootShapeV8SafeName(value.selectorKind) || "none",
    visibleTurnCount: _pr101ArtifactRootShapeV8SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount: _pr101ArtifactRootShapeV8SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount: _pr101ArtifactRootShapeV8SafeCount(value.assistantCompletionMarkerTurnCount, 64),
    orderedProbeTurnPairPresent: value.orderedProbeTurnPairPresent === true,
    probePlacementProven: value.probePlacementProven === true,
    placementRoleEvidenceKinds: _pr101ArtifactRootShapeV8SafeNames(value.placementRoleEvidenceKinds, 8),
    fiberRootCount: _pr101ArtifactRootShapeV8SafeCount(value.fiberRootCount, 4),
    scannedFiberCount: _pr101ArtifactRootShapeV8SafeCount(value.scannedFiberCount, 4096),
    scannedSourceContainerCount: _pr101ArtifactRootShapeV8SafeCount(value.scannedSourceContainerCount, 200000),
    artifactRootHitCount: _pr101ArtifactRootShapeV8SafeCount(value.artifactRootHitCount, 4096),
    attachmentRootHitCount: _pr101ArtifactRootShapeV8SafeCount(value.attachmentRootHitCount, 4096),
    nullOrUndefinedRootCount: _pr101ArtifactRootShapeV8SafeCount(value.nullOrUndefinedRootCount, 4096),
    emptyArrayRootCount: _pr101ArtifactRootShapeV8SafeCount(value.emptyArrayRootCount, 4096),
    nonemptyArrayRootCount: _pr101ArtifactRootShapeV8SafeCount(value.nonemptyArrayRootCount, 4096),
    emptyObjectRootCount: _pr101ArtifactRootShapeV8SafeCount(value.emptyObjectRootCount, 4096),
    nonemptyObjectRootCount: _pr101ArtifactRootShapeV8SafeCount(value.nonemptyObjectRootCount, 4096),
    scalarOrFunctionRootCount: _pr101ArtifactRootShapeV8SafeCount(value.scalarOrFunctionRootCount, 4096),
    candidateSummaries: summaries,
    ...commonSafety,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactRootShapeV8(message) {
  if (message?.characterizeGeneratedArtifactRootShapeV8Support === true) {
    _pr101ArtifactRootShapeV8RejectWriteBearingMessage(message, "PR10_1_ARTIFACT_ROOT_SHAPE_V8_SUPPORT_PROBE_MUST_BE_NO_WRITE");
    return {
      generatedArtifactRootShapeV8CharacterizationSupported: true,
      generatedArtifactRootShapeV8CharacterizationSchemaVersion: PR101_ARTIFACT_ROOT_SHAPE_V8_SCHEMA,
      orderedProbePairRequired: true,
      assistantTurnAnchorRequired: true,
      fiberGraphBounded: true,
      structuralArtifactRootsOnly: true,
      dottedLocalizationKeysExcluded: true,
      svgUseFibersExcluded: true,
      accessorPropertiesSkipped: true,
      domStateNodeValuesExcluded: true,
      rootValueTypesOnly: true,
      rootCardinalityBucketOnly: true,
      rootValuesExported: false,
      childValuesExported: false,
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
  if (message?.characterizeGeneratedArtifactRootShapeV8 === true) {
    _pr101ArtifactRootShapeV8RejectWriteBearingMessage(message, "PR10_1_ARTIFACT_ROOT_SHAPE_V8_PROBE_MUST_BE_NO_WRITE");
    return _pr101CharacterizeGeneratedArtifactRootShapeV8();
  }
  return _pr101ArtifactRootShapeV8PriorExecuteNativeTurn(message);
};