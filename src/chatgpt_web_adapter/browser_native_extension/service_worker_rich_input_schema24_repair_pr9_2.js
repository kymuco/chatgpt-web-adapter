// PR9.2 schema-24 official-composer mount race repair.
//
// Loaded after schema 23. Authenticated live validation showed a fresh inactive
// runtime tab can reach browser tab "complete" before ChatGPT's React composer has
// mounted. Schema 15's pre-stage clean proof immediately sampled attachment
// evidence after Runtime.enable and therefore treated `officialComposerMounted=false`
// as a dirty composer instead of a transient not-yet-mounted state.
//
// Schema 24 keeps every clean-composer safety invariant but first waits, through
// the same production page-owned attachment-evidence reader, until the official
// prompt + owning form are mounted. Only then do the two authoritative empty-set
// clean polls run. A mounted composer with any attachment evidence still fails
// closed immediately. The mount wait consumes the same single outer rich-turn
// deadline; there is no retry, staging, or protected-write authority in this phase.

const PR92_SCHEMA24_REPAIR_SCHEMA = 24;

const PR92_SCHEMA24_MOUNT_OBSERVATION_CAP_MS = 25_000;

async function _pr92Schema24WaitForOfficialComposerMounted(debuggee, context, tabId) {
  const startedAt = performance.now();
  const localDeadlineAt = Math.min(
    context.deadlineAt,
    startedAt + PR92_SCHEMA24_MOUNT_OBSERVATION_CAP_MS
  );
  let lastEvidenceKind = "not-read";
  let observedPolls = 0;

  while (performance.now() < localDeadlineAt) {
    let evidence;
    try {
      // Runtime.evaluate is not guaranteed to finish promptly on a stalled
      // inactive tab. Bound the page-owned observation itself, not just its
      // polling loop, without granting any new write or cleanup authority.
      evidence = await _pr92Schema7RunUntil(
        localDeadlineAt,
        "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_MOUNT_READ",
        () => _pr92ClosureReadPageOwnedAttachmentEvidence(debuggee, [], context)
      );
    } catch (error) {
      const detail = typeof error?.message === "string" ? error.message : String(error);
      if (!detail.startsWith("PR9_2_TOTAL_TURN_TIMEOUT:")) throw error;
      lastEvidenceKind = "read-timeout";
      break;
    }
    observedPolls += 1;
    lastEvidenceKind = typeof evidence?.evidenceKind === "string"
      ? evidence.evidenceKind : "unknown";
    if (evidence?.officialComposerMounted === true) return evidence;

    const remaining = localDeadlineAt - performance.now();
    if (remaining <= 0) break;
    await _pr92BoundedSleep(
      context,
      Math.min(PR92_PAGE_ATTACHMENT_POLL_MS, remaining),
      "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_MOUNT_WAIT"
    );
  }

  // The tab's load status is NOT evidence that ChatGPT mounted a composer.
  // Expose bounded, non-sensitive facts so a blank background tab cannot
  // silently consume the entire 240s turn without a useful stage verdict.
  let tab = null;
  try {
    tab = await _pr92Schema7RunUntil(
      Math.min(context.deadlineAt, performance.now() + 1_000),
      "SCHEMA24_MOUNT_FAILURE_TAB_DIAGNOSTIC",
      () => chrome.tabs.get(tabId)
    );
  } catch {}
  const facts = {
    tabStatus: typeof tab?.status === "string" ? tab.status : "unavailable",
    tabActive: tab?.active === true,
    tabDiscarded: tab?.discarded === true,
    tabFrozen: tab?.frozen === true,
    lastEvidenceKind,
    observedPolls,
    elapsedMs: Math.round(performance.now() - startedAt)
  };
  console.warn("CWA_PRESTAGE_COMPOSER_MOUNT_NOT_OBSERVED", facts);
  throw new Error(
    "PR9_2_OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED:" +
      "tabStatus=" + facts.tabStatus +
      ":tabActive=" + facts.tabActive +
      ":tabDiscarded=" + facts.tabDiscarded +
      ":tabFrozen=" + facts.tabFrozen +
      ":evidence=" + facts.lastEvidenceKind +
      ":polls=" + facts.observedPolls
  );
}

function _pr92Schema24EvidenceIsClean(evidence) {
  const groupCount = Number(evidence?.groupLabelCount);
  const removalCount = Number(evidence?.removalLabelCount);
  return evidence?.officialComposerMounted === true &&
    evidence?.exactBasenameAssociation === true &&
    evidence?.exactAttachmentSet === true &&
    groupCount === 0 && removalCount === 0 &&
    Number(evidence?.previewImageCount || 0) === 0 &&
    Number(evidence?.inlineFileNameCount || 0) === 0;
}

async function _pr92Schema24RequireOfficialCleanComposerBeforeStaging(
  tabId,
  context
) {
  const debuggee = { tabId };
  let attached = false;
  let attachPending = null;
  try {
    _pr92RemainingTurnMs(context, "SCHEMA24_PRESTAGE_CLEAN_ATTACH");
    attachPending = chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    if (attachPending && typeof attachPending.catch === "function") {
      attachPending.catch(() => {});
    }

    try {
      await _pr92Schema7RunUntil(
        context.deadlineAt,
        "SCHEMA24_PRESTAGE_CLEAN_DEBUGGER_ATTACH",
        () => attachPending
      );
      attached = true;
    } catch (error) {
      // debugger.attach is non-cancellable. Preserve the reviewed late-success
      // best-effort release semantics without changing the failed outcome.
      if (attachPending && typeof attachPending.then === "function") {
        attachPending.then(
          () => _pr92Schema10BestEffortDetach(debuggee),
          () => {}
        );
      }
      throw error;
    }

    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA24_PRESTAGE_CLEAN_RUNTIME_ENABLE",
      () => chrome.debugger.sendCommand(debuggee, "Runtime.enable")
    );

    // Browser tab load completion is not composer-mount authority. Reuse the exact
    // production attachment-evidence reader and treat `officialComposerMounted=false`
    // as transient until the one outer turn deadline expires.
    let evidence;
    try {
      evidence = await _pr92Schema24WaitForOfficialComposerMounted(debuggee, context, tabId);
    } catch (error) {
      const detail = typeof error?.message === "string" ? error.message : String(error);
      if (detail.startsWith("PR9_2_OFFICIAL_COMPOSER_MOUNT_NOT_OBSERVED:")) {
        // The owning pre-stage observer must be fully detached BEFORE an
        // unmounted fresh page can be navigated by the caller. A best-effort
        // asynchronous detach would race the next staging attempt.
        await _pr92Schema15DetachWithinDeadline(
          debuggee,
          context,
          "SCHEMA24_PRESTAGE_MOUNT_FAILURE_DEBUGGER_DETACH"
        );
        attached = false;
      }
      throw error;
    }

    // The evidence that first proves mount is also the first clean poll. If the
    // freshly mounted composer already contains any attachment evidence, fail
    // closed immediately rather than sleeping or attempting staging.
    let stable = 0;
    while (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
      if (!_pr92Schema24EvidenceIsClean(evidence)) {
        throw new Error("PR9_2_OFFICIAL_COMPOSER_NOT_CLEAN_BEFORE_STAGING");
      }
      stable += 1;
      if (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA24_PRESTAGE_CLEAN_STABILITY"
        );
        evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
          debuggee,
          [],
          context
        );
      }
    }

    // Preserve schema 15's successful ownership handoff: staging may attach next,
    // so the clean observer must have fully relinquished debugger ownership first.
    await _pr92Schema15DetachWithinDeadline(
      debuggee,
      context,
      "SCHEMA24_PRESTAGE_CLEAN_DEBUGGER_DETACH"
    );
    attached = false;
  } finally {
    // Error/timeout cleanup remains non-authoritative and best-effort.
    if (attached) _pr92Schema10BestEffortDetach(debuggee);
  }
};

function _pr92Schema24AugmentSupportResult(result) {
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA24_REPAIR_SCHEMA,
    preStageOfficialComposerMountAwaited: true,
    preStageOfficialComposerMountWaitDeadlineBounded: true,
    officialComposerMountUsesProductionAttachmentEvidenceReader: true,
    tabCompleteAloneCanProveComposerMounted: false,
    missingComposerBeforeMountClassifiedDirty: false,
    mountedAttachmentEvidenceStillFailsClosed: true
  };
}
