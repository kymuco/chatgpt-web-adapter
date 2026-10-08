// C2 research: reference-independent browser structure observation.
// No Google Translate result selectors, no page text reads, no product writes.
// Page instrumentation is bounded to the consented capture and removed in finally.

const CWA_C2_OPERATION = "research_capture_independent_delta_v0";
const CWA_C2_ORIGIN = "https://translate.google.com";
const CWA_C2_PAGE_KEY = "__cwaResearchIndependentDeltaV0";

function _cwaC2PageProbe(command) {
  "use strict";
  const KEY = "__cwaResearchIndependentDeltaV0";
  const MAX_INPUT_EVENTS = 64;
  const MAX_CANDIDATES = 8;

  function region(element) {
    const rect = element.getBoundingClientRect();
    const width = document.documentElement.clientWidth;
    if (!(width > 0)) return "unknown";
    const middle = (rect.left + rect.width / 2) / width;
    return middle < 1 / 3 ? "left" : middle < 2 / 3 ? "center" : "right";
  }

  function visible(element) {
    if (!(element instanceof Element)) return false;
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 &&
      style.display !== "none" && style.visibility !== "hidden";
  }

  function sourceKind(element) {
    if (!(element instanceof Element)) return null;
    const tag = element.tagName.toLowerCase();
    if (tag === "textarea" || tag === "input") return tag;
    return element.isContentEditable === true ? "contenteditable" : null;
  }

  function leafKind(element) {
    const tag = element.tagName.toLowerCase();
    if (tag === "span" || tag === "div" || tag === "p" ||
        tag === "section" || tag === "output") return tag;
    return "other";
  }

  function descriptor(element, role) {
    return {
      role,
      kind: role === "source_input" ? sourceKind(element) : leafKind(element),
      region: region(element)
    };
  }

  function routeMatches(source, target) {
    const url = new URL(location.href);
    return url.origin === "https://translate.google.com" &&
      url.searchParams.get("sl") === source &&
      url.searchParams.get("tl") === target;
  }

  if (command.action === "install") {
    if (globalThis[KEY] !== undefined || !document.documentElement) {
      return { installed: false, reason: "NOT_FRESH" };
    }
    if (!routeMatches(command.source, command.target)) {
      return { installed: false, reason: "ROUTE_MISMATCH" };
    }
    const state = {
      source: null,
      distinctSourceTargets: 0,
      inputEvents: 0,
      candidates: new Set(),
      overflow: false,
      lastMutationAt: 0,
      sourceAmbiguous: false,
      observer: null,
      onInput: null
    };

    function maybeRemember(element) {
      if (!state.source || !(element instanceof Element)) return;
      if (state.source === element ||
          state.source.contains(element) || element.contains(state.source)) return;
      if (element.children.length !== 0 || !visible(element)) return;
      if (sourceKind(element) !== null) return; // A control is not an output.
      if (state.candidates.has(element)) {
        state.lastMutationAt = performance.now();
        return;
      }
      if (state.candidates.size >= MAX_CANDIDATES) {
        state.overflow = true;
        return;
      }
      state.candidates.add(element);
      state.lastMutationAt = performance.now();
    }

    function scanNewNode(node, budget) {
      // Structural traversal only. No text, attributes, IDs, or names read.
      if (budget.remaining <= 0) {
        state.overflow = true;
        return;
      }
      budget.remaining -= 1;
      if (node instanceof Element) {
        maybeRemember(node);
        for (const child of node.children) {
          if (budget.remaining <= 0) {
            state.overflow = true;
            return;
          }
          scanNewNode(child, budget);
        }
      } else if (node && node.parentElement) {
        maybeRemember(node.parentElement);
      }
    }

    state.onInput = event => {
      if (event.isTrusted !== true) return;
      const candidate = event.target;
      if (!visible(candidate) || sourceKind(candidate) === null) return;
      state.inputEvents += 1;
      if (state.inputEvents > MAX_INPUT_EVENTS) {
        state.overflow = true;
        return;
      }
      if (state.source === null) {
        state.source = candidate; // Ephemeral DOM identity never exported.
        state.distinctSourceTargets = 1;
      } else if (state.source !== candidate) {
        state.distinctSourceTargets = 2;
        state.sourceAmbiguous = true;
      }
    };

    state.observer = new MutationObserver(records => {
      if (!state.source || state.overflow) return;
      for (const record of records) {
        if (state.overflow) break;
        const budget = { remaining: 24 };
        if (record.type === "characterData") {
          maybeRemember(record.target.parentElement);
        } else if (record.type === "childList") {
          for (const node of record.addedNodes) {
            scanNewNode(node, budget);
            if (state.overflow) break;
          }
          maybeRemember(record.target);
        } else if (record.type === "attributes") {
          maybeRemember(record.target);
        }
      }
    });
    document.addEventListener("input", state.onInput, true);
    state.observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "style", "hidden"]
    });
    globalThis[KEY] = state;
    return { installed: true };
  }

  const state = globalThis[KEY];
  if (!state) return { ready: false };

  if (command.action === "remove") {
    state.observer.disconnect();
    document.removeEventListener("input", state.onInput, true);
    delete globalThis[KEY];
    return { removed: true };
  }

  if (command.action !== "observe") return { ready: false };
  const source = state.source;
  const alive = [...state.candidates].filter(element =>
    element.isConnected === true && visible(element));
  // Clean-up state transitions are reported conservatively: absent elements
  // are excluded, but no new candidates are inferred from page text.
  const candidates = alive.filter(element =>
    source !== element && !source?.contains(element) &&
    !element.contains(source) && element.children.length === 0);
  return {
    ready: true,
    routeVerified: routeMatches(command.source, command.target),
    inputEvents: state.inputEvents,
    sourceCandidateCount: state.distinctSourceTargets,
    sourceDescriptor: source !== null && !state.sourceAmbiguous
      ? descriptor(source, "source_input") : null,
    mutationLeafCount: candidates.length,
    mutationLeafDescriptor: candidates.length === 1
      ? descriptor(candidates[0], "changed_leaf") : null,
    mutationOverflow: state.overflow,
    sourceAmbiguous: state.sourceAmbiguous,
    structuralQuiet: source !== null && candidates.length > 0 &&
      performance.now() - state.lastMutationAt >= 1000
  };
}

function _cwaC2Expression(action, source, target) {
  return "(" + _cwaC2PageProbe.toString() + ")(" +
    JSON.stringify({ action, source, target }) + ")";
}

function _cwaC2ValidateLanguages(source, target) {
  const valid = x => typeof x === "string" &&
    /^[A-Za-z][A-Za-z0-9-]{1,19}$/.test(x);
  if (!valid(source) || !valid(target)) {
    throw new Error("CAPTURE_C2_INVALID_LANGUAGES");
  }
}

function _cwaC2TabRoute(tab, source, target) {
  try {
    const url = new URL(tab?.url || "");
    return url.origin === CWA_C2_ORIGIN &&
      url.searchParams.get("sl") === source &&
      url.searchParams.get("tl") === target;
  } catch {
    return false;
  }
}

async function _cwaC2Evaluate(debuggee, action, source, target) {
  const response = await _cwaBaseSendCommand(
    debuggee, "Runtime.evaluate", {
      expression: _cwaC2Expression(action, source, target),
      returnByValue: true,
      awaitPromise: true
    }
  );
  if (response?.exceptionDetails || !response?.result?.value) {
    throw new Error("CAPTURE_C2_PAGE_EVALUATION_FAILED");
  }
  return response.result.value;
}

function _cwaC2ValidateSample(sample) {
  const kinds = {
    source_input: ["textarea", "input", "contenteditable"],
    changed_leaf: ["span", "div", "p", "section", "output", "other"]
  };
  function validDescriptor(desc, role) {
    return desc && typeof desc === "object" &&
      Object.keys(desc).sort().join(",") === "kind,region,role" &&
      desc.role === role && kinds[role].includes(desc.kind) &&
      ["left", "center", "right", "unknown"].includes(desc.region);
  }
  if (sample?.ready !== true || sample?.routeVerified !== true ||
      !Number.isInteger(sample.inputEvents) || sample.inputEvents < 0 ||
      sample.inputEvents > 64 ||
      !Number.isInteger(sample.sourceCandidateCount) ||
      sample.sourceCandidateCount < 0 || sample.sourceCandidateCount > 2 ||
      !Number.isInteger(sample.mutationLeafCount) ||
      sample.mutationLeafCount < 0 || sample.mutationLeafCount > 8 ||
      typeof sample.mutationOverflow !== "boolean" ||
      typeof sample.sourceAmbiguous !== "boolean" ||
      typeof sample.structuralQuiet !== "boolean") {
    throw new Error("CAPTURE_C2_INVALID_SAMPLE");
  }
  if (sample.sourceCandidateCount === 1 && !sample.sourceAmbiguous) {
    if (!validDescriptor(sample.sourceDescriptor, "source_input")) {
      throw new Error("CAPTURE_C2_SOURCE_DESCRIPTOR_INVALID");
    }
  } else if (sample.sourceDescriptor !== null) {
    throw new Error("CAPTURE_C2_SOURCE_DESCRIPTOR_UNEXPECTED");
  }
  if (sample.mutationLeafCount === 1) {
    if (!validDescriptor(sample.mutationLeafDescriptor, "changed_leaf")) {
      throw new Error("CAPTURE_C2_RESULT_DESCRIPTOR_INVALID");
    }
  } else if (sample.mutationLeafDescriptor !== null) {
    throw new Error("CAPTURE_C2_RESULT_DESCRIPTOR_UNEXPECTED");
  }
  // Explicitly copy closed fields; never export raw CDP/page objects.
  const copyDesc = value => value === null ? null : {
    role: value.role, kind: value.kind, region: value.region
  };
  return {
    inputEvents: sample.inputEvents,
    sourceCandidateCount: sample.sourceCandidateCount,
    sourceDescriptor: copyDesc(sample.sourceDescriptor),
    mutationLeafCount: sample.mutationLeafCount,
    mutationLeafDescriptor: copyDesc(sample.mutationLeafDescriptor),
    mutationOverflow: sample.mutationOverflow,
    sourceAmbiguous: sample.sourceAmbiguous,
    structuralQuiet: sample.structuralQuiet
  };
}

async function _cwaC2ObserveReferenceIndependentDelta(message) {
  const tabId = message?.tabId;
  const source = message?.sourceLanguage;
  const target = message?.targetLanguage;
  const seconds = message?.seconds;
  if (!Number.isSafeInteger(tabId) || tabId <= 0 ||
      !Number.isInteger(seconds) || seconds < 6 || seconds > 20) {
    throw new Error("CAPTURE_C2_INVALID_REQUEST");
  }
  _cwaC2ValidateLanguages(source, target);
  if (message?.consent !== "EXPLICIT_SINGLE_TAB_EVENT_DELTA") {
    throw new Error("CAPTURE_C2_CONSENT_REQUIRED");
  }
  const tab = await chrome.tabs.get(tabId);
  if (!_cwaC2TabRoute(tab, source, target)) {
    throw new Error("CAPTURE_C2_TAB_ROUTE_MISMATCH");
  }
  const debuggee = { tabId };
  let attached = false;
  let installAttempted = false;
  let cleanupUnproven = false;
  const startedAt = performance.now();
  let last = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");
    installAttempted = true;
    const setup = await _cwaC2Evaluate(debuggee, "install", source, target);
    if (setup?.installed !== true) {
      throw new Error("CAPTURE_C2_OBSERVER_NOT_FRESH");
    }
    while (performance.now() - startedAt < seconds * 1000) {
      const sample = await _cwaC2Evaluate(debuggee, "observe", source, target);
      last = _cwaC2ValidateSample(sample);
      if (last.mutationOverflow) {
        throw new Error("CAPTURE_C2_MUTATION_BOUND_EXCEEDED");
      }
      if (last.inputEvents > 0 && last.structuralQuiet) break;
      await sleep(180);
    }
    const after = await chrome.tabs.get(tabId);
    if (!_cwaC2TabRoute(after, source, target)) {
      throw new Error("CAPTURE_C2_TAB_ROUTE_DRIFT");
    }
    if (last === null) throw new Error("CAPTURE_C2_NOT_OBSERVED");
    const sourceStatus = last.sourceCandidateCount === 0 ? "MISSING" :
      last.sourceCandidateCount === 1 && !last.sourceAmbiguous
        ? "EVENT_TARGET_OBSERVED" : "AMBIGUOUS";
    const resultStatus = last.mutationLeafCount === 0 ? "MISSING" :
      last.mutationLeafCount === 1 && last.structuralQuiet
        ? "ONE_STRUCTURAL_CHANGE_CANDIDATE" : "AMBIGUOUS";
    return {
      schema: "CWA_CAPTURE_C2_INDEPENDENT_DELTA_V0",
      productId: "google-translate-web",
      captureMode: "EXPLICIT_SINGLE_TAB_EVENT_DELTA",
      routeVerified: true,
      sourceLanguage: source,
      targetLanguage: target,
      inputEventCount: last.inputEvents,
      source: {
        status: sourceStatus,
        candidateCount: last.sourceCandidateCount,
        descriptor: sourceStatus === "EVENT_TARGET_OBSERVED"
          ? last.sourceDescriptor : null,
        provenance: "TRUSTED_HUMAN_INPUT_EVENT"
      },
      result: {
        status: resultStatus,
        candidateCount: last.mutationLeafCount,
        descriptor: resultStatus === "ONE_STRUCTURAL_CHANGE_CANDIDATE"
          ? last.mutationLeafDescriptor : null,
        provenance: "POST_INPUT_GENERIC_DOM_MUTATIONS"
      },
      structuralQuiet: last.structuralQuiet,
      referenceSelectorConsulted: false,
      semanticFinalityProven: false,
      learnedLocatorProven: false,
      canonicalCompletionProven: false,
      replayExecutable: false,
      newWriteAuthority: false,
      automaticRetry: false,
      rawContentRetained: false
    };
  } finally {
    if (attached) {
      if (installAttempted) {
        try {
          const removed = await _cwaC2Evaluate(debuggee, "remove", source, target);
          if (removed?.removed !== true) cleanupUnproven = true;
        } catch {
          cleanupUnproven = true;
        }
      }
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        cleanupUnproven = true;
      }
    }
    if (cleanupUnproven) throw new Error("CAPTURE_C2_CLEANUP_UNPROVEN");
  }
}

async function _cwaOnNativeMessageWithIndependentDelta(message, port, next) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
      message?.type !== CWA_C2_OPERATION) {
    return next(message, port);
  }
  const requestId = message?.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (_cwaC2CaptureActive) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_independent_delta_v0_result",
      request_id: requestId,
      ok: false,
      error: "CAPTURE_C2_BUSY"
    });
    return;
  }
  _cwaC2CaptureActive = true;
  try {
    const result = await _cwaC2ObserveReferenceIndependentDelta(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_independent_delta_v0_result",
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    const reason = error instanceof Error && error.message.startsWith("CAPTURE_C2_")
      ? error.message : "CAPTURE_C2_OBSERVATION_FAILED";
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "research_capture_independent_delta_v0_result",
      request_id: requestId,
      ok: false,
      error: reason
    });
  } finally {
    _cwaC2CaptureActive = false;
  }
}

let _cwaC2CaptureActive = false;
