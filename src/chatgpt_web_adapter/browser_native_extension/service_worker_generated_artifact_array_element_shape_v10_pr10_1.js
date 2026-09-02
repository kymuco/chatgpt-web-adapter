// PR10.1 v10: characterize element shape inside opaque-token array children of non-empty attachment roots.
// Raw attachment child keys, array element values, string values, locator values, and React state values never leave the page.

const PR101_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SCHEMA = 10;
const _pr101ArtifactArrayElementShapeV10PriorExecuteNativeTurn = executeNativeTurn;

function _pr101ArtifactArrayElementShapeV10RejectWriteBearingMessage(message, code) {
  if (message?.text != null || message?.conversationId != null || message?.attachmentPaths != null || message?.browserAuthorityLeaseId != null) {
    throw new Error(code);
  }
}

function _pr101ArtifactArrayElementShapeV10RouteEvidence(url) {
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

function _pr101ArtifactArrayElementShapeV10Expression() {
  return `(() => {
    const userMarker = 'CWA_PR10_1_ARTIFACT_PROBE';
    const assistantMarker = 'ARTIFACT_PROBE_CREATED';
    const MAX_FIBERS_PER_TURN = 512;
    const MAX_ANCESTOR_FIBERS_PER_TURN = 10;
    const MAX_SOURCE_CONTAINER_DEPTH = 5;
    const MAX_SOURCE_CONTAINERS = 96;
    const MAX_ARRAY_CANDIDATES = 8;
    const MAX_ARRAY_ELEMENTS_SCANNED = 64;

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
    const attachmentRoot = (name) => {
      const text = String(name || '');
      if (!text || text.includes('.')) return false;
      return new Set(['attachment','attachments']).has(text.toLowerCase());
    };
    const knownStructuralNames = new Set([
      'id','type','kind','name','filename','fileName','mimeType','mediaType','size','sizeBytes','status',
      'items','byId','allIds','data','value','current','payload','state','metadata','records','entities',
      'nodes','edges','list','map','attachment','attachments','file','files','artifact','artifacts',
      'asset','assets','content'
    ]);
    const knownStructuralName = (name) => knownStructuralNames.has(String(name || '')) ? String(name) : null;
    const identityNames = new Set([
      'id','fileId','file_id','artifactId','artifact_id','assetId','asset_id','attachmentId','attachment_id',
      'generatedFileId','generated_file_id'
    ]);
    const locatorNames = new Set([
      'href','url','uri','download','downloadUrl','download_url','downloadUri','download_uri',
      'signedUrl','signed_url','assetPointer','asset_pointer'
    ]);
    const identityName = (name) => identityNames.has(String(name || '')) ? String(name) : null;
    const locatorName = (name) => locatorNames.has(String(name || '')) ? String(name) : null;
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
    const stringShape = (value) => {
      const text = typeof value === 'string' ? value : '';
      if (text.length === 0) return 'empty';
      if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(text)) return 'uuid_like';
      if (/^file[-_][A-Za-z0-9_-]{6,128}$/.test(text)) return 'file_prefixed_token';
      if (/^artifact[-_][A-Za-z0-9_-]{6,128}$/.test(text)) return 'artifact_prefixed_token';
      if (/^[0-9a-f]{16,64}$/i.test(text)) return 'hex_like';
      if (/^[A-Za-z0-9_-]{16,128}$/.test(text)) return 'opaque_token';
      if (/^[A-Za-z_$][A-Za-z0-9_$-]{0,63}$/.test(text)) return 'semantic_identifier';
      return 'other';
    };
    const stringLengthBucket = (value) => {
      const count = typeof value === 'string' ? value.length : 0;
      if (count === 0) return 'zero';
      if (count <= 8) return 'up_to_8';
      if (count <= 16) return 'nine_to_sixteen';
      if (count <= 32) return 'seventeen_to_thirty_two';
      if (count <= 64) return 'thirty_three_to_sixty_four';
      return 'over_sixty_four';
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
    const blankValueCounts = () => ({
      null:0,undefined:0,array:0,object:0,string:0,number:0,boolean:0,bigint:0,symbol:0,function:0,other:0
    });
    const blankStringShapeCounts = () => ({
      empty:0,uuid_like:0,file_prefixed_token:0,artifact_prefixed_token:0,hex_like:0,opaque_token:0,semantic_identifier:0,other:0
    });
    const blankStringLengthCounts = () => ({
      zero:0,up_to_8:0,nine_to_sixteen:0,seventeen_to_thirty_two:0,thirty_three_to_sixty_four:0,over_sixty_four:0
    });

    const summarizeArray = (arrayValue, rawChildKey) => {
      const elementValueKindCounts = blankValueCounts();
      const stringElementShapeCounts = blankStringShapeCounts();
      const stringElementLengthBucketCounts = blankStringLengthCounts();
      const knownStructuralElementKeyNames = new Set();
      const identityLikeElementKeyNames = new Set();
      const locatorLikeElementKeyNames = new Set();
      let plainObjectElementCount = 0;
      let traversableObjectElementCount = 0;
      const scanCount = Math.min(arrayValue.length, MAX_ARRAY_ELEMENTS_SCANNED);
      for (let index = 0; index < scanCount; index += 1) {
        let element;
        try { element = arrayValue[index]; } catch { continue; }
        const kind = valueKind(element);
        elementValueKindCounts[kind] += 1;
        if (kind === 'string') {
          stringElementShapeCounts[stringShape(element)] += 1;
          stringElementLengthBucketCounts[stringLengthBucket(element)] += 1;
        }
        if (isTraversableObject(element)) {
          traversableObjectElementCount += 1;
          if (plainObjectKind(element) === 'plain_object') plainObjectElementCount += 1;
          if (!Array.isArray(element)) {
            for (const [rawElementKey] of ownDataEntries(element)) {
              const structural = knownStructuralName(rawElementKey);
              const identity = identityName(rawElementKey);
              const locator = locatorName(rawElementKey);
              if (structural) knownStructuralElementKeyNames.add(structural);
              if (identity) identityLikeElementKeyNames.add(identity);
              if (locator) locatorLikeElementKeyNames.add(locator);
            }
          }
        }
      }
      return {
        childKeyShape: keyShape(rawChildKey),
        childKeyLengthBucket: keyLengthBucket(rawChildKey),
        arrayCardinalityBucket: cardinalityBucket(arrayValue.length),
        elementsScannedCount: scanCount,
        elementValueKindCounts,
        stringElementShapeCounts,
        stringElementLengthBucketCounts,
        traversableObjectElementCount,
        plainObjectElementCount,
        knownStructuralElementKeyNames: Array.from(knownStructuralElementKeyNames).sort(),
        identityLikeElementKeyNames: Array.from(identityLikeElementKeyNames).sort(),
        locatorLikeElementKeyNames: Array.from(locatorLikeElementKeyNames).sort()
      };
    };

    const main = document.querySelector('main');
    const empty = {
      surfaceReady:false,selectorKind:'none',visibleTurnCount:0,userProbeMarkerTurnCount:0,assistantCompletionMarkerTurnCount:0,
      orderedProbeTurnPairPresent:false,probePlacementProven:false,placementRoleEvidenceKinds:[],fiberRootCount:0,scannedFiberCount:0,
      scannedSourceContainerCount:0,nonemptyAttachmentRootCount:0,opaqueArrayChildCount:0,totalArrayElementsScannedCount:0,
      arrayWithObjectElementCount:0,arrayWithTokenStringElementCount:0,arrayWithIdentityKeySchemaCount:0,arrayWithLocatorKeySchemaCount:0,
      arrayCandidateSummaries:[]
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
    let nonemptyAttachmentRootCount = 0, opaqueArrayChildCount = 0, totalArrayElementsScannedCount = 0;
    let arrayWithObjectElementCount = 0, arrayWithTokenStringElementCount = 0, arrayWithIdentityKeySchemaCount = 0, arrayWithLocatorKeySchemaCount = 0;

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
        for (const [rootKey, attachmentValue] of entries.filter(([name]) => attachmentRoot(name))) {
          if (!isTraversableObject(attachmentValue)) continue;
          const attachmentEntries = ownDataEntries(attachmentValue);
          if (attachmentEntries.length === 0) continue;
          nonemptyAttachmentRootCount += 1;
          for (const [rawChildKey, childValue] of attachmentEntries) {
            if (keyShape(rawChildKey) !== 'opaque_token' || !Array.isArray(childValue) || childValue.length === 0) continue;
            opaqueArrayChildCount += 1;
            const summary = summarizeArray(childValue, rawChildKey);
            totalArrayElementsScannedCount += summary.elementsScannedCount;
            if ((summary.elementValueKindCounts.object || 0) > 0) arrayWithObjectElementCount += 1;
            const tokenStrings =
              (summary.stringElementShapeCounts.uuid_like || 0) +
              (summary.stringElementShapeCounts.file_prefixed_token || 0) +
              (summary.stringElementShapeCounts.artifact_prefixed_token || 0) +
              (summary.stringElementShapeCounts.hex_like || 0) +
              (summary.stringElementShapeCounts.opaque_token || 0);
            if (tokenStrings > 0) arrayWithTokenStringElementCount += 1;
            if (summary.identityLikeElementKeyNames.length > 0) arrayWithIdentityKeySchemaCount += 1;
            if (summary.locatorLikeElementKeyNames.length > 0) arrayWithLocatorKeySchemaCount += 1;
            if (candidates.length < MAX_ARRAY_CANDIDATES) {
              candidates.push({
                relationKind, fiberDepth, componentName: safeName(fiberName) || 'unknown', sourceKind, sourceNestedDepth: nestedDepth,
                sourceContainerKind: Array.isArray(value) ? 'array' : 'object', artifactRootKeyName: safeName(rootKey) || 'attachments',
                ...summary
              });
            }
          }
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
      scanSource(fiber.memoizedProps,'memoized_props',relationKind,fiberDepth,name);
      scanSource(fiber.pendingProps,'pending_props',relationKind,fiberDepth,name);
      scanSource(fiber.memoizedState,'memoized_state',relationKind,fiberDepth,name);
      scanSource(fiber.updateQueue,'update_queue',relationKind,fiberDepth,name);
      scanSource(fiber.dependencies,'dependencies',relationKind,fiberDepth,name);
    };

    if (probePlacementProven) {
      for (const targetTurn of targetAssistantTurns.slice(0, 4)) {
        const rootFiber = ownFiber(targetTurn);
        if (!rootFiber) continue;
        fiberRootCount += 1; inspectFiber(rootFiber,'turn_root',0);
        let ancestor = rootFiber.return;
        for (let depth = 1; depth <= MAX_ANCESTOR_FIBERS_PER_TURN && ancestor; depth += 1) {
          inspectFiber(ancestor,'turn_ancestor',depth); ancestor = ancestor.return;
        }
        const stack = []; if (rootFiber.child) stack.push({ fiber: rootFiber.child, depth: 1 });
        let descendantCount = 0;
        while (stack.length && descendantCount < MAX_FIBERS_PER_TURN) {
          const current = stack.pop(); const fiber = current?.fiber; const depth = current?.depth;
          if (!fiber || typeof fiber !== 'object') continue;
          descendantCount += 1; inspectFiber(fiber,'turn_descendant',depth);
          if (fiber.sibling) stack.push({ fiber: fiber.sibling, depth });
          if (fiber.child) stack.push({ fiber: fiber.child, depth: Math.min(depth + 1, 64) });
        }
      }
    }

    return {
      surfaceReady:true, selectorKind, visibleTurnCount:turns.length, userProbeMarkerTurnCount, assistantCompletionMarkerTurnCount,
      orderedProbeTurnPairPresent, probePlacementProven, placementRoleEvidenceKinds:Array.from(placementRoleEvidenceKinds).sort(),
      fiberRootCount, scannedFiberCount, scannedSourceContainerCount, nonemptyAttachmentRootCount, opaqueArrayChildCount,
      totalArrayElementsScannedCount, arrayWithObjectElementCount, arrayWithTokenStringElementCount,
      arrayWithIdentityKeySchemaCount, arrayWithLocatorKeySchemaCount, arrayCandidateSummaries:candidates
    };
  })()`;
}

function _pr101ArtifactArrayElementShapeV10SafeName(value) {
  const text = typeof value === "string" ? value.trim() : "";
  return /^[A-Za-z0-9_.:-]{1,80}$/.test(text) ? text : null;
}
function _pr101ArtifactArrayElementShapeV10SafeCount(value, maximum) {
  return Number.isInteger(value) && value >= 0 ? Math.min(value, maximum) : 0;
}
function _pr101ArtifactArrayElementShapeV10SafeNameList(value, allowed, maximum) {
  if (!Array.isArray(value)) return [];
  const output = [];
  for (const item of value) {
    const name = _pr101ArtifactArrayElementShapeV10SafeName(item);
    if (!name || !allowed.has(name)) continue;
    output.push(name);
    if (output.length >= maximum) break;
  }
  return Array.from(new Set(output)).sort();
}
function _pr101ArtifactArrayElementShapeV10SafeFixedCounts(value, keys, maximum) {
  const source = value && typeof value === "object" ? value : {};
  const output = {};
  for (const key of keys) output[key] = _pr101ArtifactArrayElementShapeV10SafeCount(source[key], maximum);
  return output;
}
function _pr101ArtifactArrayElementShapeV10SafeCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const valueKinds = ["null","undefined","array","object","string","number","boolean","bigint","symbol","function","other"];
  const stringShapes = ["empty","uuid_like","file_prefixed_token","artifact_prefixed_token","hex_like","opaque_token","semantic_identifier","other"];
  const stringLengths = ["zero","up_to_8","nine_to_sixteen","seventeen_to_thirty_two","thirty_three_to_sixty_four","over_sixty_four"];
  const keyShapes = ["opaque_token"];
  const keyLengths = ["up_to_8","nine_to_sixteen","seventeen_to_thirty_two","thirty_three_to_sixty_four","over_sixty_four"];
  const buckets = ["zero","one","two_to_four","five_to_sixteen","over_sixteen","unknown"];
  const relationKinds = ["turn_root","turn_ancestor","turn_descendant"];
  const sourceKinds = ["memoized_props","pending_props","memoized_state","update_queue","dependencies"];
  const sourceContainers = ["object","array"];
  const structuralNames = new Set([
    "id","type","kind","name","filename","fileName","mimeType","mediaType","size","sizeBytes","status",
    "items","byId","allIds","data","value","current","payload","state","metadata","records","entities",
    "nodes","edges","list","map","attachment","attachments","file","files","artifact","artifacts","asset","assets","content"
  ]);
  const identityNames = new Set(["id","fileId","file_id","artifactId","artifact_id","assetId","asset_id","attachmentId","attachment_id","generatedFileId","generated_file_id"]);
  const locatorNames = new Set(["href","url","uri","download","downloadUrl","download_url","downloadUri","download_uri","signedUrl","signed_url","assetPointer","asset_pointer"]);
  const childKeyShape = keyShapes.includes(value.childKeyShape) ? value.childKeyShape : "opaque_token";
  const childKeyLengthBucket = keyLengths.includes(value.childKeyLengthBucket) ? value.childKeyLengthBucket : "over_sixty_four";
  const arrayCardinalityBucket = buckets.includes(value.arrayCardinalityBucket) ? value.arrayCardinalityBucket : "unknown";
  return {
    relationKind: relationKinds.includes(value.relationKind) ? value.relationKind : "turn_descendant",
    fiberDepth: _pr101ArtifactArrayElementShapeV10SafeCount(value.fiberDepth, 64),
    componentName: _pr101ArtifactArrayElementShapeV10SafeName(value.componentName) || "unknown",
    sourceKind: sourceKinds.includes(value.sourceKind) ? value.sourceKind : "memoized_state",
    sourceNestedDepth: _pr101ArtifactArrayElementShapeV10SafeCount(value.sourceNestedDepth, 5),
    sourceContainerKind: sourceContainers.includes(value.sourceContainerKind) ? value.sourceContainerKind : "object",
    artifactRootKeyName: ["attachment","attachments"].includes(value.artifactRootKeyName) ? value.artifactRootKeyName : "attachments",
    childKeyShape,
    childKeyLengthBucket,
    arrayCardinalityBucket,
    elementsScannedCount: _pr101ArtifactArrayElementShapeV10SafeCount(value.elementsScannedCount, 64),
    elementValueKindCounts: _pr101ArtifactArrayElementShapeV10SafeFixedCounts(value.elementValueKindCounts, valueKinds, 64),
    stringElementShapeCounts: _pr101ArtifactArrayElementShapeV10SafeFixedCounts(value.stringElementShapeCounts, stringShapes, 64),
    stringElementLengthBucketCounts: _pr101ArtifactArrayElementShapeV10SafeFixedCounts(value.stringElementLengthBucketCounts, stringLengths, 64),
    traversableObjectElementCount: _pr101ArtifactArrayElementShapeV10SafeCount(value.traversableObjectElementCount, 64),
    plainObjectElementCount: _pr101ArtifactArrayElementShapeV10SafeCount(value.plainObjectElementCount, 64),
    knownStructuralElementKeyNames: _pr101ArtifactArrayElementShapeV10SafeNameList(value.knownStructuralElementKeyNames, structuralNames, 32),
    identityLikeElementKeyNames: _pr101ArtifactArrayElementShapeV10SafeNameList(value.identityLikeElementKeyNames, identityNames, 16),
    locatorLikeElementKeyNames: _pr101ArtifactArrayElementShapeV10SafeNameList(value.locatorLikeElementKeyNames, locatorNames, 16)
  };
}

async function _pr101CharacterizeGeneratedArtifactArrayElementShapeV10() {
  const runtimeTabId = await storedRuntimeTabId();
  const commonSafety = {
    fiberGraphBounded:true, attachmentRootsOnly:true, nonemptyAttachmentRootsOnly:true, opaqueArrayChildrenOnly:true,
    arrayElementsBounded:true, elementValueTypesOnly:true, stringElementShapeClassificationOnly:true,
    knownStructuralKeyWhitelistOnly:true, accessorPropertiesSkipped:true, domStateNodeValuesExcluded:true,
    rawAttachmentChildKeysExported:false, rawArrayElementValuesExported:false, rawStringValuesExported:false,
    rawRootValuesExported:false, rawDomExported:false, rawTextExported:false, attributeValuesExported:false,
    reactPropValuesExported:false, reactStateValuesExported:false, locatorValuesExported:false,
    clickPerformed:false, downloadAttempted:false, writePerformed:false
  };
  const empty = {
    schema:PR101_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SCHEMA, runtimeTabPresent:false, runtimeRouteKind:"absent",
    runtimeConversationIdPresent:false, surfaceReady:false, selectorKind:"none", visibleTurnCount:0,
    userProbeMarkerTurnCount:0, assistantCompletionMarkerTurnCount:0, orderedProbeTurnPairPresent:false,
    probePlacementProven:false, placementRoleEvidenceKinds:[], fiberRootCount:0, scannedFiberCount:0,
    scannedSourceContainerCount:0, nonemptyAttachmentRootCount:0, opaqueArrayChildCount:0,
    totalArrayElementsScannedCount:0, arrayWithObjectElementCount:0, arrayWithTokenStringElementCount:0,
    arrayWithIdentityKeySchemaCount:0, arrayWithLocatorKeySchemaCount:0, arrayCandidateSummaries:[],
    ...commonSafety, debuggerAttachedAfter:null
  };
  if (!Number.isInteger(runtimeTabId)) return empty;
  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || "")) throw new Error("PR10_1_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_RUNTIME_TAB_NOT_CHATGPT");
  const route = _pr101ArtifactArrayElementShapeV10RouteEvidence(tab.url || "");
  const debuggee = { tabId: runtimeTabId };
  let attached = false, debuggerAttachedAfter = null, value = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION); attached = true;
    await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression:_pr101ArtifactArrayElementShapeV10Expression(), returnByValue:true, awaitPromise:true
    });
    value = result?.result?.value;
    if (!value || typeof value !== "object") throw new Error("PR10_1_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_RESULT_MISSING");
  } finally {
    if (attached) { try { await chrome.debugger.detach(debuggee); } catch {} }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(targets.find((target) => target.tabId === runtimeTabId)?.attached);
    } catch { debuggerAttachedAfter = null; }
  }
  const summaries = Array.isArray(value.arrayCandidateSummaries)
    ? value.arrayCandidateSummaries.map(_pr101ArtifactArrayElementShapeV10SafeCandidate).filter(Boolean).slice(0, 8)
    : [];
  return {
    schema:PR101_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SCHEMA, runtimeTabPresent:true,
    runtimeRouteKind:route.routeKind, runtimeConversationIdPresent:route.conversationIdPresent,
    surfaceReady:value.surfaceReady === true,
    selectorKind:_pr101ArtifactArrayElementShapeV10SafeName(value.selectorKind) || "none",
    visibleTurnCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.visibleTurnCount, 64),
    userProbeMarkerTurnCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.userProbeMarkerTurnCount, 64),
    assistantCompletionMarkerTurnCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.assistantCompletionMarkerTurnCount, 64),
    orderedProbeTurnPairPresent:value.orderedProbeTurnPairPresent === true,
    probePlacementProven:value.probePlacementProven === true,
    placementRoleEvidenceKinds:Array.isArray(value.placementRoleEvidenceKinds)
      ? value.placementRoleEvidenceKinds.map(_pr101ArtifactArrayElementShapeV10SafeName).filter(Boolean).slice(0, 8)
      : [],
    fiberRootCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.fiberRootCount, 4),
    scannedFiberCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.scannedFiberCount, 4096),
    scannedSourceContainerCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.scannedSourceContainerCount, 200000),
    nonemptyAttachmentRootCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.nonemptyAttachmentRootCount, 4096),
    opaqueArrayChildCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.opaqueArrayChildCount, 4096),
    totalArrayElementsScannedCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.totalArrayElementsScannedCount, 512),
    arrayWithObjectElementCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.arrayWithObjectElementCount, 4096),
    arrayWithTokenStringElementCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.arrayWithTokenStringElementCount, 4096),
    arrayWithIdentityKeySchemaCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.arrayWithIdentityKeySchemaCount, 4096),
    arrayWithLocatorKeySchemaCount:_pr101ArtifactArrayElementShapeV10SafeCount(value.arrayWithLocatorKeySchemaCount, 4096),
    arrayCandidateSummaries:summaries, ...commonSafety, debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr101ExecuteNativeTurnWithArtifactArrayElementShapeV10(message) {
  if (message?.characterizeGeneratedArtifactArrayElementShapeV10Support === true) {
    _pr101ArtifactArrayElementShapeV10RejectWriteBearingMessage(message, "PR10_1_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SUPPORT_PROBE_MUST_BE_NO_WRITE");
    return {
      generatedArtifactArrayElementShapeV10CharacterizationSupported:true,
      generatedArtifactArrayElementShapeV10CharacterizationSchemaVersion:PR101_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SCHEMA,
      orderedProbePairRequired:true, assistantTurnAnchorRequired:true, fiberGraphBounded:true, attachmentRootsOnly:true,
      nonemptyAttachmentRootsOnly:true, opaqueArrayChildrenOnly:true, arrayElementsBounded:true, elementValueTypesOnly:true,
      stringElementShapeClassificationOnly:true, knownStructuralKeyWhitelistOnly:true, accessorPropertiesSkipped:true,
      domStateNodeValuesExcluded:true, rawAttachmentChildKeysExported:false, rawArrayElementValuesExported:false,
      rawStringValuesExported:false, rawRootValuesExported:false, rawDomExported:false, rawTextExported:false,
      attributeValuesExported:false, reactPropValuesExported:false, reactStateValuesExported:false,
      locatorValuesExported:false, clickPerformed:false, downloadAttempted:false, writePerformed:false
    };
  }
  if (message?.characterizeGeneratedArtifactArrayElementShapeV10 === true) {
    _pr101ArtifactArrayElementShapeV10RejectWriteBearingMessage(message, "PR10_1_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_PROBE_MUST_BE_NO_WRITE");
    return _pr101CharacterizeGeneratedArtifactArrayElementShapeV10();
  }
  return _pr101ArtifactArrayElementShapeV10PriorExecuteNativeTurn(message);
};
