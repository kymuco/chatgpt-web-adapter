// PR10.1 v9: characterize non-empty artifact-root child key/value shape without exporting raw keys or values.
// Unknown child keys are classified into bounded shape enums only. Only explicitly whitelisted structural key names may leave the page.

const PR101_ARTIFACT_ROOT_KEY_SHAPE_V9_SCHEMA = 9;
const _pr101ArtifactRootKeyShapeV9PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactRootKeyShapeV9RejectWriteBearingMessage(message, code) {
  if (message?.text != null || message?.conversationId != null || message?.attachmentPaths != null || message?.browserAuthorityLeaseId != null) {
    throw new Error(code);
  }
}

function _pr101ArtifactRootKeyShapeV9RouteEvidence(url) {
  try {
    const parsed = new URL(url);
    if (parsed.origin !== CHATGPT_ORIGIN) return { routeKind: "not_chatgpt", conversationIdPresent: false };
    if (conversationIdFromUrl(url || "")) return { routeKind: "conversation", conversationIdPresent: true };
    if (parsed.pathname === "/" || parsed.pathname === "") return { routeKind: "root", conversationIdPresent: false };
    return { routeKind: "chatgpt_other", conversationIdPresent: false };
  } catch {
    return { routeKind: "invalid", conversationIdPresent: false };
  }
}

function _pr101ArtifactRootKeyShapeV9Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const MAX_FIBERS_PER_TURN = 512;
    const MAX_ANCESTOR_FIBERS_PER_TURN = 10;
    const MAX_SOURCE_CONTAINER_DEPTH = 5;
    const MAX_SOURCE_CONTAINERS = 96;
    const MAX_CANDIDATES = 16;
    const MAX_CHILD_SUMMARIES = 8;

    const safeName = (value) => {
      const text = typeof value === 'string' ? value.trim() : '';
      return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
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
      const direct = String(turn.getAttribute('data-message-author-role') || '').trim();
      if (direct === 'assistant' || direct === 'user') return { role: direct, evidence: 'direct_message_author_role' };
      const node = turn.querySelector('[data-message-author-role="assistant"],[data-message-author-role="user"]');
      const nested = String(node?.getAttribute?.('data-message-author-role') || '').trim();
      if (nested === 'assistant' || nested === 'user') return { role: nested, evidence: 'nested_message_author_role' };
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
    const excludedFiberComponent = (name) => ['svg', 'use', 'path'].includes(String(name || '').toLowerCase());
    const structuralArtifactRoot = (name) => {
      const text = String(name || '');
      if (!text || text.includes('.')) return false;
      return new Set(['attachment','attachments','file','files','artifact','artifacts','generatedfile','generatedfiles','generated_file','generated_files']).has(text.toLowerCase());
    };
    const knownStructuralNames = new Set([
      'id','type','kind','items','byId','allIds','data','value','current','payload','state','metadata','records','entities',
      'nodes','edges','list','map','attachment','attachments','file','files','artifact','artifacts','asset','assets','content'
    ]);
    const knownStructuralName = (name) => knownStructuralNames.has(String(name || '')) ? String(name) : null;
    const valueKind = (value) => {
      if (value === null) return 'null';
      if (Array.isArray(value)) return 'array';
      const kind = typeof value;
      if (['undefined','string','number','boolean','bigint','symbol','function'].includes(kind)) return kind;
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
    const keyLengthBucket = (name) => {
      const count = typeof name === 'string' ? name.length : 0;
      if (count <= 8) return 'up_to_8';
      if (count <= 16) return 'nine_to_sixteen';
      if (count <= 32) return 'seventeen_to_thirty_two';
      if (count <= 64) return 'thirty_three_to_sixty_four';
      return 'over_sixty_four';
    };
    const keyShape = (name) => {
      const text = String(name || '');
      if (knownStructuralName(text)) return 'known_structural';
      if (/^[0-9]{1,20}$/.test(text)) return 'numeric';
      if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(text)) return 'uuid_like';
      if (/^file[-_][A-Za-z0-9_-]{6,128}$/.test(text)) return 'file_prefixed_token';
      if (/^artifact[-_][A-Za-z0-9_-]{6,128}$/.test(text)) return 'artifact_prefixed_token';
      if (/^[0-9a-f]{16,64}$/i.test(text)) return 'hex_like';
      if (/^[A-Za-z0-9_-]{16,128}$/.test(text)) return 'opaque_token';
      if (/^[A-Za-z_$][A-Za-z0-9_$-]{0,63}$/.test(text)) return 'semantic_identifier';
      return 'other';
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
        if (rawName === 'length' && Array.isArray(value)) continue;
        if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) continue;
        entries.push([String(rawName), descriptor.value]);
      }
      return entries;
    };
    const shouldDescendKey = (name) => !['stateNode','return','child','sibling','alternate','_owner','_debugOwner','_debugSource','ref','refs'].includes(name);
    const plainObjectKind = (value) => {
      if (Array.isArray(value)) return 'array';
      if (!value || typeof value !== 'object') return 'not_object';
      let proto = null;
      try { proto = Object.getPrototypeOf(value); } catch { return 'other_object'; }
      if (proto === null) return 'null_prototype';
      if (proto === Object.prototype) return 'plain_object';
      return 'other_object';
    };
    const childCardinalityBucket = (value) => {
      if (Array.isArray(value)) return cardinalityBucket(value.length);
      if (isTraversableObject(value)) return cardinalityBucket(ownDataEntries(value).length);
      return 'not_applicable';
    };
    const blankShapeCounts = () => ({
      known_structural:0,numeric:0,uuid_like:0,file_prefixed_token:0,artifact_prefixed_token:0,hex_like:0,opaque_token:0,semantic_identifier:0,other:0
    });
    const blankValueCounts = () => ({
      null:0,undefined:0,array:0,object:0,string:0,number:0,boolean:0,bigint:0,symbol:0,function:0,other:0
    });

    const main = document.querySelector('main');
    const empty = {
      surfaceReady:false,selectorKind:'none',visibleTurnCount:0,userProbeMarkerTurnCount:0,assistantCompletionMarkerTurnCount:0,
      orderedProbeTurnPairPresent:false,probePlacementProven:false,placementRoleEvidenceKinds:[],fiberRootCount:0,scannedFiberCount:0,
      scannedSourceContainerCount:0,nonemptyArtifactRootCount:0,nonemptyAttachmentRootCount:0,objectRootCount:0,arrayRootCount:0,
      identityAsKeyCandidateCount:0,knownStructuralKeyHitCount:0,recordLikeIdentityKeyChildCount:0,candidateSummaries:[]
    };
    if (!main) return empty;
    let selectorKind = 'conversation_testid';
    let turns = Array.from(main.querySelectorAll('[data-testid^="conversation-turn-"]'));
    if (turns.length === 0) { selectorKind = 'article_fallback'; turns = Array.from(main.querySelectorAll('article')); }
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
        if (firstUserProbeIndex >= 0 && index > firstUserProbeIndex && firstAssistantCompletionAfterUserIndex < 0) firstAssistantCompletionAfterUserIndex = index;
      }
    }
    const orderedProbeTurnPairPresent = firstUserProbeIndex >= 0 && firstAssistantCompletionAfterUserIndex > firstUserProbeIndex;
    const probePlacementProven = orderedProbeTurnPairPresent && userProbeMarkerTurnCount >= 1 && assistantCompletionMarkerTurnCount >= 1;

    const candidates = [];
    let fiberRootCount = 0, scannedFiberCount = 0, scannedSourceContainerCount = 0;
    let nonemptyArtifactRootCount = 0, nonemptyAttachmentRootCount = 0, objectRootCount = 0, arrayRootCount = 0;
    let identityAsKeyCandidateCount = 0, knownStructuralKeyHitCount = 0, recordLikeIdentityKeyChildCount = 0;

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
        seen.add(value); scannedForSource += 1; scannedSourceContainerCount += 1;
        const entries = ownDataEntries(value);
        for (const [rootKey, childValue] of entries.filter(([name]) => structuralArtifactRoot(name))) {
          if (!isTraversableObject(childValue)) continue;
          const childEntries = ownDataEntries(childValue);
          if (childEntries.length === 0) continue;
          nonemptyArtifactRootCount += 1;
          if (String(rootKey).toLowerCase().startsWith('attachment')) nonemptyAttachmentRootCount += 1;
          if (Array.isArray(childValue)) arrayRootCount += 1; else objectRootCount += 1;
          const keyShapeCounts = blankShapeCounts();
          const childValueKindCounts = blankValueCounts();
          const knownStructuralChildKeyNames = new Set();
          const childSummaries = [];
          let traversableChildCount = 0;
          for (const [rawChildKey, grandchild] of childEntries) {
            const shape = keyShape(rawChildKey);
            keyShapeCounts[shape] += 1;
            const kind = valueKind(grandchild);
            childValueKindCounts[kind] += 1;
            const whitelisted = knownStructuralName(rawChildKey);
            if (whitelisted) { knownStructuralChildKeyNames.add(whitelisted); knownStructuralKeyHitCount += 1; }
            const identityAsKey = ['uuid_like','file_prefixed_token','artifact_prefixed_token','hex_like','opaque_token'].includes(shape);
            if (identityAsKey) identityAsKeyCandidateCount += 1;
            if (isTraversableObject(grandchild)) {
              traversableChildCount += 1;
              if (identityAsKey && kind === 'object') recordLikeIdentityKeyChildCount += 1;
            }
            if (childSummaries.length < MAX_CHILD_SUMMARIES) {
              childSummaries.push({
                keyShape: shape,
                keyLengthBucket: keyLengthBucket(rawChildKey),
                knownStructuralKeyName: whitelisted,
                childValueKind: kind,
                childCardinalityBucket: childCardinalityBucket(grandchild),
                childPlainObjectKind: plainObjectKind(grandchild)
              });
            }
          }
          candidates.push({
            relationKind, fiberDepth, componentName: safeName(fiberName) || 'unknown', sourceKind, sourceNestedDepth: nestedDepth,
            sourceContainerKind: Array.isArray(value) ? 'array' : 'object', artifactRootKeyName: safeName(rootKey) || 'unknown',
            rootValueKind: Array.isArray(childValue) ? 'array' : 'object', rootCardinalityBucket: cardinalityBucket(childEntries.length),
            rootPlainObjectKind: plainObjectKind(childValue), knownStructuralChildKeyNames: Array.from(knownStructuralChildKeyNames).sort(),
            keyShapeCounts, childValueKindCounts, traversableChildCountBucket: cardinalityBucket(traversableChildCount), childSummaries
          });
        }
        for (const [name, childValue] of entries) {
          if (nestedDepth < MAX_SOURCE_CONTAINER_DEPTH && shouldDescendKey(name) && isTraversableObject(childValue)) queue.push({ value: childValue, depth: nestedDepth + 1 });
        }
      }
    };
    const inspectFiber = (fiber, relationKind, fiberDepth) => {
      if (!fiber || typeof fiber !== 'object') return;
      scannedFiberCount += 1;
      const name = componentName(fiber);
      if (excludedFiberComponent(name)) return;
      scanSource(fiber.memoizedProps,'memoized_props',relationKind,fiberDepth,name);
      scanSource(fiber.pendingProps,'pending_props',relationKind,fiberDepth,name);
      scanSource(fiber.memoizedState,'memoized_state',relationKind,fiberDepth,name);
      scanSource(fiber.updateQueue,'update_queue',relationKind,fiberDepth,name);
      scanSource(fiber.dependencies,'dependencies',relationKind,fiberDepth,name);
    };

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0,4)) {
        const rootFiber = ownFiber(targetTurn);
        if (!rootFiber) continue;
        fiberRootCount += 1; inspectFiber(rootFiber,'turn_root',0);
        let ancestor = rootFiber.return;
        for (let depth=1; depth<=MAX_ANCESTOR_FIBERS_PER_TURN && ancestor; depth+=1) { inspectFiber(ancestor,'turn_ancestor',depth); ancestor=ancestor.return; }
        const stack = []; if (rootFiber.child) stack.push({fiber:rootFiber.child,depth:1});
        let descendantCount=0;
        while (stack.length && descendantCount<MAX_FIBERS_PER_TURN) {
          const current=stack.pop(); const fiber=current?.fiber; const depth=current?.depth;
          if (!fiber || typeof fiber !== 'object') continue;
          descendantCount += 1; inspectFiber(fiber,'turn_descendant',depth);
          if (fiber.sibling) stack.push({fiber:fiber.sibling,depth});
          if (fiber.child) stack.push({fiber:fiber.child,depth:Math.min(depth+1,64)});
        }
      }
    }

    return {
      surfaceReady:true, selectorKind, visibleTurnCount:turns.length, userProbeMarkerTurnCount, assistantCompletionMarkerTurnCount,
      orderedProbeTurnPairPresent, probePlacementProven, placementRoleEvidenceKinds:Array.from(placementRoleEvidenceKinds).sort(),
      fiberRootCount, scannedFiberCount, scannedSourceContainerCount, nonemptyArtifactRootCount, nonemptyAttachmentRootCount,
      objectRootCount, arrayRootCount, identityAsKeyCandidateCount, knownStructuralKeyHitCount, recordLikeIdentityKeyChildCount,
      candidateSummaries:candidates.slice(0,MAX_CANDIDATES).map((summary,index)=>({index,...summary}))
    };
  })()`;
}

function _pr101ArtifactRootKeyShapeV9SafeName(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}
function _pr101ArtifactRootKeyShapeV9SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}
function _pr101ArtifactRootKeyShapeV9SafeNameList(value, maxItems = 32) {
  if (!Array.isArray(value)) return [];
  return Array.from(new Set(value.map(_pr101ArtifactRootKeyShapeV9SafeName).filter(Boolean))).sort().slice(0,maxItems);
}
function _pr101ArtifactRootKeyShapeV9SafeFixedCounts(value, keys, maximum = 4096) {
  const output = {};
  for (const key of keys) output[key] = _pr101ArtifactRootKeyShapeV9SafeCount(value?.[key], maximum);
  return output;
}
function _pr101ArtifactRootKeyShapeV9SafeChild(value) {
  if (!value || typeof value !== "object") return null;
  const keyShape = ["known_structural","numeric","uuid_like","file_prefixed_token","artifact_prefixed_token","hex_like","opaque_token","semantic_identifier","other"].includes(value.keyShape) ? value.keyShape : "other";
  const keyLengthBucket = ["up_to_8","nine_to_sixteen","seventeen_to_thirty_two","thirty_three_to_sixty_four","over_sixty_four"].includes(value.keyLengthBucket) ? value.keyLengthBucket : "over_sixty_four";
  const childValueKind = ["null","undefined","array","object","string","number","boolean","bigint","symbol","function","other"].includes(value.childValueKind) ? value.childValueKind : "other";
  const childCardinalityBucket = ["zero","one","two_to_four","five_to_sixteen","over_sixteen","not_applicable","unknown"].includes(value.childCardinalityBucket) ? value.childCardinalityBucket : "unknown";
  const childPlainObjectKind = ["array","not_object","null_prototype","plain_object","other_object"].includes(value.childPlainObjectKind) ? value.childPlainObjectKind : "other_object";
  return { key_shape:keyShape, key_length_bucket:keyLengthBucket, known_structural_key_name:_pr101ArtifactRootKeyShapeV9SafeName(value.knownStructuralKeyName), child_value_kind:childValueKind, child_cardinality_bucket:childCardinalityBucket, child_plain_object_kind:childPlainObjectKind };
}
function _pr101ArtifactRootKeyShapeV9SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const relationKind = ["turn_root","turn_ancestor","turn_descendant"].includes(value.relationKind) ? value.relationKind : "turn_descendant";
  const sourceKind = ["memoized_props","pending_props","memoized_state","update_queue","dependencies"].includes(value.sourceKind) ? value.sourceKind : "memoized_state";
  const sourceContainerKind = ["object","array"].includes(value.sourceContainerKind) ? value.sourceContainerKind : "object";
  const rootValueKind = ["object","array"].includes(value.rootValueKind) ? value.rootValueKind : "object";
  const rootCardinalityBucket = ["zero","one","two_to_four","five_to_sixteen","over_sixteen","unknown"].includes(value.rootCardinalityBucket) ? value.rootCardinalityBucket : "unknown";
  const rootPlainObjectKind = ["array","null_prototype","plain_object","other_object"].includes(value.rootPlainObjectKind) ? value.rootPlainObjectKind : "other_object";
  const keyShapeCounts = _pr101ArtifactRootKeyShapeV9SafeFixedCounts(value.keyShapeCounts,["known_structural","numeric","uuid_like","file_prefixed_token","artifact_prefixed_token","hex_like","opaque_token","semantic_identifier","other"]);
  const childValueKindCounts = _pr101ArtifactRootKeyShapeV9SafeFixedCounts(value.childValueKindCounts,["null","undefined","array","object","string","number","boolean","bigint","symbol","function","other"]);
  const traversableChildCountBucket = ["zero","one","two_to_four","five_to_sixteen","over_sixteen","unknown"].includes(value.traversableChildCountBucket) ? value.traversableChildCountBucket : "unknown";
  const childSummaries = Array.isArray(value.childSummaries) ? value.childSummaries.map(_pr101ArtifactRootKeyShapeV9SafeChild).filter(Boolean).slice(0,8) : [];
  return { index:_pr101ArtifactRootKeyShapeV9SafeCount(value.index,16), relationKind, fiberDepth:_pr101ArtifactRootKeyShapeV9SafeCount(value.fiberDepth,64), componentName:_pr101ArtifactRootKeyShapeV9SafeName(value.componentName)||"unknown", sourceKind, sourceNestedDepth:_pr101ArtifactRootKeyShapeV9SafeCount(value.sourceNestedDepth,5), sourceContainerKind, artifactRootKeyName:_pr101ArtifactRootKeyShapeV9SafeName(value.artifactRootKeyName)||"unknown", rootValueKind, rootCardinalityBucket, rootPlainObjectKind, knownStructuralChildKeyNames:_pr101ArtifactRootKeyShapeV9SafeNameList(value.knownStructuralChildKeyNames,24), keyShapeCounts, childValueKindCounts, traversableChildCountBucket, childSummaries };
}

async function _pr101CharacterizeGeneratedArtifactRootKeyShapeV9() {
  const runtimeTabId = await storedRuntimeTabId();
  const commonSafety = {
    fiberGraphBounded:true, structuralArtifactRootsOnly:true, nonemptyRootsOnly:true, dottedLocalizationKeysExcluded:true,
    svgUseFibersExcluded:true, accessorPropertiesSkipped:true, domStateNodeValuesExcluded:true, keyShapeClassificationOnly:true,
    knownStructuralKeyWhitelistOnly:true, rawRootKeysExported:false, rawRootValuesExported:false, childValuesExported:false,
    rawDomExported:false, rawTextExported:false, attributeValuesExported:false, reactPropValuesExported:false,
    reactStateValuesExported:false, locatorValuesExported:false, clickPerformed:false, downloadAttempted:false, writePerformed:false
  };
  const empty = { schema:PR101_ARTIFACT_ROOT_KEY_SHAPE_V9_SCHEMA, runtimeTabPresent:false, runtimeRouteKind:"absent", runtimeConversationIdPresent:false, surfaceReady:false, selectorKind:"none", visibleTurnCount:0, userProbeMarkerTurnCount:0, assistantCompletionMarkerTurnCount:0, orderedProbeTurnPairPresent:false, probePlacementProven:false, placementRoleEvidenceKinds:[], fiberRootCount:0, scannedFiberCount:0, scannedSourceContainerCount:0, nonemptyArtifactRootCount:0, nonemptyAttachmentRootCount:0, objectRootCount:0, arrayRootCount:0, identityAsKeyCandidateCount:0, knownStructuralKeyHitCount:0, recordLikeIdentityKeyChildCount:0, candidateSummaries:[], ...commonSafety, debuggerAttachedAfter:null };
  if (!Number.isInteger(runtimeTabId)) return empty;
  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) throw new Error("PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_RUNTIME_TAB_NOT_CHATGPT");
  const route = _pr101ArtifactRootKeyShapeV9RouteEvidence(tab.url || "");
  const debuggee = { tabId:runtimeTabId };
  let attached=false, debuggerAttachedAfter=null, value=null;
  try {
    await chrome.debugger.attach(debuggee,CDP_PROTOCOL_VERSION); attached=true;
    await chrome.debugger.sendCommand(debuggee,"Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee,"Runtime.evaluate",{ expression:_pr101ArtifactRootKeyShapeV9Expression(), returnByValue:true, awaitPromise:true });
    value=result?.result?.value;
    if (!value || typeof value !== "object") throw new Error("PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_RESULT_MISSING");
  } finally {
    if (attached) { try { await chrome.debugger.detach(debuggee); } catch {} }
    try { const targets=await chrome.debugger.getTargets(); debuggerAttachedAfter=Boolean(targets.find((target)=>target.tabId===runtimeTabId)?.attached); } catch { debuggerAttachedAfter=null; }
  }
  const summaries = Array.isArray(value.candidateSummaries) ? value.candidateSummaries.map(_pr101ArtifactRootKeyShapeV9SafeCandidate).filter(Boolean).slice(0,16) : [];
  return {
    schema:PR101_ARTIFACT_ROOT_KEY_SHAPE_V9_SCHEMA, runtimeTabPresent:true, runtimeRouteKind:route.routeKind, runtimeConversationIdPresent:route.conversationIdPresent,
    surfaceReady:value.surfaceReady===true, selectorKind:_pr101ArtifactRootKeyShapeV9SafeName(value.selectorKind)||"none",
    visibleTurnCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.visibleTurnCount,64), userProbeMarkerTurnCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.userProbeMarkerTurnCount,64), assistantCompletionMarkerTurnCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.assistantCompletionMarkerTurnCount,64), orderedProbeTurnPairPresent:value.orderedProbeTurnPairPresent===true, probePlacementProven:value.probePlacementProven===true,
    placementRoleEvidenceKinds:_pr101ArtifactRootKeyShapeV9SafeNameList(value.placementRoleEvidenceKinds,8), fiberRootCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.fiberRootCount,4), scannedFiberCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.scannedFiberCount,4096), scannedSourceContainerCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.scannedSourceContainerCount,200000), nonemptyArtifactRootCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.nonemptyArtifactRootCount,4096), nonemptyAttachmentRootCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.nonemptyAttachmentRootCount,4096), objectRootCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.objectRootCount,4096), arrayRootCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.arrayRootCount,4096), identityAsKeyCandidateCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.identityAsKeyCandidateCount,4096), knownStructuralKeyHitCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.knownStructuralKeyHitCount,4096), recordLikeIdentityKeyChildCount:_pr101ArtifactRootKeyShapeV9SafeCount(value.recordLikeIdentityKeyChildCount,4096), candidateSummaries:summaries,
    ...commonSafety, debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactRootKeyShapeV9(message) {
  if (message?.characterizeGeneratedArtifactRootKeyShapeV9Support === true) {
    _pr101ArtifactRootKeyShapeV9RejectWriteBearingMessage(message,"PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_SUPPORT_PROBE_MUST_BE_NO_WRITE");
    return { generatedArtifactRootKeyShapeV9CharacterizationSupported:true, generatedArtifactRootKeyShapeV9CharacterizationSchemaVersion:PR101_ARTIFACT_ROOT_KEY_SHAPE_V9_SCHEMA, orderedProbePairRequired:true, assistantTurnAnchorRequired:true, fiberGraphBounded:true, structuralArtifactRootsOnly:true, nonemptyRootsOnly:true, dottedLocalizationKeysExcluded:true, svgUseFibersExcluded:true, accessorPropertiesSkipped:true, domStateNodeValuesExcluded:true, keyShapeClassificationOnly:true, knownStructuralKeyWhitelistOnly:true, rawRootKeysExported:false, rawRootValuesExported:false, childValuesExported:false, rawDomExported:false, rawTextExported:false, attributeValuesExported:false, reactPropValuesExported:false, reactStateValuesExported:false, locatorValuesExported:false, clickPerformed:false, downloadAttempted:false, writePerformed:false };
  }
  if (message?.characterizeGeneratedArtifactRootKeyShapeV9 === true) {
    _pr101ArtifactRootKeyShapeV9RejectWriteBearingMessage(message,"PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_PROBE_MUST_BE_NO_WRITE");
    return _pr101CharacterizeGeneratedArtifactRootKeyShapeV9();
  }
  return _pr101ArtifactRootKeyShapeV9PriorExecuteNativeTurn(message);
};
