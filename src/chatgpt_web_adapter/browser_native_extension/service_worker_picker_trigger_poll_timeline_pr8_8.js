_pr88SelectionPoint =
  async function _pr88SelectionPointWithTriggerIdentity(debuggee, kind) {
    const result = await _pr88TriggerPriorSelectionPoint(debuggee, kind);
    if (kind === "picker" && result?.found === true) {
      const context = _pr88TriggerEnsureContext(result, result?.mode);
      if (context !== null) {
        await _pr88TriggerAppendSample(debuggee, "PICKER_RESOLVED");
      }
    }
    return result;
  };

_pr88SelectionRawClick =
  async function _pr88SelectionRawClickWithActuationEvidence(debuggee, point) {
    const context = _pr88TriggerTimelineContext;
    if (
      context !== null &&
      context.awaitingPickerClick === true &&
      _pr88TriggerSamePoint(context.pickerPoint, point)
    ) {
      await _pr88TriggerAppendSample(debuggee, "PRE_CLICK");
      const startedAt = performance.now();
      const result = await _pr88TriggerPriorRawClick(debuggee, point);
      context.clickDispatchCompleted = true;
      context.pickerClickElapsedMs = _pr88TriggerSafeInt(
        performance.now() - startedAt
      );
      context.awaitingPickerClick = false;
      await _pr88TriggerAppendSample(debuggee, "POST_CLICK_IMMEDIATE");
      return result;
    }
    return _pr88TriggerPriorRawClick(debuggee, point);
  };

_pr88SelectionWaitForInstantOption =
  async function _pr88SelectionWaitForInstantOptionWithTimeline(
    debuggee,
    timeoutMs
  ) {
    const startedAt = performance.now();
    let last = null;
    let pollIndex = 0;
    while (performance.now() - startedAt < timeoutMs) {
      last = await _pr88TriggerPriorSelectionPoint(debuggee, "instant_option");
      pollIndex += 1;
      if (_pr88TriggerTimelineContext !== null) {
        _pr88TriggerTimelineContext.pollSampleCount = pollIndex;
        await _pr88TriggerAppendSample(
          debuggee,
          "OPTION_POLL",
          last,
          pollIndex
        );
      }
      if (last?.found === true) return last;
      await sleep(PR88_INSTANT_SELECTION_POLL_MS);
    }
    return (
      last || {
        found: false,
        reason: "instant_option_timeout",
        candidateCount: 0
      }
    );
  };


function _pr88TriggerMaterializationOutcome(context) {
  const best = context?.bestSeen;
  if (!best) return "TIMELINE_UNAVAILABLE";
  if (best.maxModeBearingPopupSurfaceCount > 0) {
    return "MODE_BEARING_PICKER_MATERIALIZED";
  }
  if (
    best.triggerStateTransitionObserved === true ||
    best.firstTriggerOpenSignalMs !== null
  ) {
    return "TRIGGER_ACTUATED_WITHOUT_MODE_PICKER";
  }
  if (context?.clickDispatchCompleted === true) {
    return "CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION";
  }
  return "PICKER_CLICK_NOT_CONFIRMED";
}

async function _pr88TriggerRoute(debuggee) {
  const tabId = Number.isInteger(debuggee?.tabId) ? debuggee.tabId : null;
  if (tabId === null) {
    return {
      captureTabId: null,
      routeKind: "UNKNOWN",
      observedConversationId: null
    };
  }
  try {
    const tab = await chrome.tabs.get(tabId);
    const url = typeof tab?.url === "string" ? tab.url : "";
    let observedConversationId = null;
    try {
      const value = conversationIdFromUrl(url);
      if (typeof value === "string" && value.trim()) {
        observedConversationId = value.trim();
      }
    } catch {}
    let pathname = "/";
    try {
      pathname = new URL(url).pathname || "/";
    } catch {}
    return {
      captureTabId: tabId,
      routeKind:
        observedConversationId !== null
          ? "CONVERSATION"
          : pathname === "/" || pathname === ""
            ? "ROOT"
            : "OTHER_CHATGPT",
      observedConversationId
    };
  } catch {
    return {
      captureTabId: tabId,
      routeKind: "UNKNOWN",
      observedConversationId: null
    };
  }
}

async function _pr88TriggerPersist(error, context, debuggee) {
  const leaseId = _pr88TriggerLeaseId(context?.leaseId);
  if (leaseId === null) return false;
  const route = await _pr88TriggerRoute(debuggee);
  const failureCode = (() => {
    try {
      return typeof _pr88FailureCode === "function"
        ? _pr88FailureCode(error)
        : "UNKNOWN";
    } catch {
      return "UNKNOWN";
    }
  })();
  const failureReason = (() => {
    try {
      return typeof _pr88FailureReason === "function"
        ? _pr88FailureReason(error)
        : null;
    } catch {
      return null;
    }
  })();
  const best = context.bestSeen || {};
  const record = {
    schemaVersion: PR88_PICKER_TRIGGER_TIMELINE_SCHEMA_VERSION,
    leaseId,
    capturedAtFailure: true,
    failureCode,
    failureReason,
    captureStatus: "TRIGGER_TIMELINE_CAPTURED",
    ...route,
    pickerMode: context.pickerMode || null,
    pickerPointAvailable:
      Number.isFinite(context?.pickerPoint?.x) &&
      Number.isFinite(context?.pickerPoint?.y),
    clickDispatchCompleted: context.clickDispatchCompleted === true,
    pickerClickElapsedMs: _pr88TriggerSafeInt(context.pickerClickElapsedMs),
    timelineSampleCount: context.samples.length,
    pollSampleCount: Number.isInteger(context.pollSampleCount)
      ? context.pollSampleCount
      : 0,
    timelineSamples: context.samples.slice(0, PR88_PICKER_TRIGGER_MAX_SAMPLES),
    timelineSamplesTruncated: context.samplesTruncated === true,
    bestSeen: {
      recognizedModes: Array.from(best.recognizedModes || []).sort(),
      maxModeBearingPopupSurfaceCount: Number.isInteger(
        best.maxModeBearingPopupSurfaceCount
      )
        ? best.maxModeBearingPopupSurfaceCount
        : 0,
      maxKnownModeDescendantCount: Number.isInteger(
        best.maxKnownModeDescendantCount
      )
        ? best.maxKnownModeDescendantCount
        : 0,
      firstModeBearingPopupSeenMs: _pr88TriggerSafeInt(
        best.firstModeBearingPopupSeenMs
      ),
      lastModeBearingPopupSeenMs: _pr88TriggerSafeInt(
        best.lastModeBearingPopupSeenMs
      ),
      firstTriggerOpenSignalMs: _pr88TriggerSafeInt(
        best.firstTriggerOpenSignalMs
      ),
      triggerStateTransitionObserved:
        best.triggerStateTransitionObserved === true,
      falseOpenGenericOnlyObserved:
        best.falseOpenGenericOnlyObserved === true,
      bestSelectedSurface:
        best.bestSelectedSurface &&
        typeof best.bestSelectedSurface === "object"
          ? best.bestSelectedSurface
          : null
    },
    materializationOutcome: _pr88TriggerMaterializationOutcome(context),
    rawUrlExported: false,
    rawTextExported: false,
    rawHtmlExported: false,
    leaseIdExported: false,
    zeroProductWrites: true,
    automaticRetry: false
  };
  await chrome.storage.local.set({
    [PR88_PICKER_TRIGGER_TIMELINE_STORAGE_KEY]: record
  });
  return true;
}

