// PR9.2 schema-24 official-composer mount/readiness race repair.
//
// Loaded after schema 23. Authenticated live validation showed a fresh inactive
// runtime tab can reach browser tab "complete" before ChatGPT's React composer has
// mounted. Schema 15's pre-stage clean proof immediately sampled attachment
// evidence after Runtime.enable and therefore treated `officialComposerMounted=false`
// as a dirty composer instead of a transient not-yet-mounted state.
//
// Schema 24 keeps every clean-composer safety invariant but inserts one bounded
// official-composer readiness wait before the two authoritative empty-set evidence
// polls. Once the composer is mounted, any real attachment evidence still fails
// closed immediately. The wait consumes the same single outer rich-turn deadline;
// there is no retry, staging, or protected-write authority in this phase.

const _pr92Schema24PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA24_REPAIR_SCHEMA = 24;

_pr92Schema10RequireOfficialCleanComposerBeforeStaging = async function _pr92Schema24RequireOfficialCleanComposerBeforeStaging(
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

    // A browser tab reporting load-complete is not proof that the client-side
    // composer has mounted. Wait for the same official composer readiness used by
    // the page-turn path before interpreting a missing composer as attachment
    // state. This wait is bounded by the one outer rich-turn deadline.
    const readinessBudget = _pr92RemainingTurnMs(
      context,
      "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_READY_BUDGET"
    );
    await _pr92Schema7RunUntil(
      context.deadlineAt,
      "SCHEMA24_PRESTAGE_OFFICIAL_COMPOSER_READY",
      () => waitForComposerReady(debuggee, readinessBudget)
    );

    // After mount/readiness, preserve the exact schema-15 authoritative proof:
    // two stable empty-set polls, exact basename semantics, and zero role-group /
    // structured-removal evidence. Any actual attachment remains an immediate
    // fail-closed condition before staging.
    let stable = 0;
    while (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
      const evidence = await _pr92ClosureReadPageOwnedAttachmentEvidence(
        debuggee,
        [],
        context
      );
      const groupCount = Number(evidence?.groupLabelCount);
      const removalCount = Number(evidence?.removalLabelCount);
      const clean = evidence?.officialComposerMounted === true &&
        evidence?.exactBasenameAssociation === true &&
        evidence?.exactAttachmentSet === true &&
        groupCount === 0 && removalCount === 0;
      if (!clean) {
        throw new Error("PR9_2_OFFICIAL_COMPOSER_NOT_CLEAN_BEFORE_STAGING");
      }
      stable += 1;
      if (stable < PR92_SCHEMA10_PRESTAGE_CLEAN_STABLE_POLLS) {
        await _pr92BoundedSleep(
          context,
          PR92_PAGE_ATTACHMENT_POLL_MS,
          "SCHEMA24_PRESTAGE_CLEAN_STABILITY"
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

executeNativeTurn = async function _executeNativeTurnWithPr92Schema24Repair(message) {
  const result = await _pr92Schema24PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA24_REPAIR_SCHEMA,
    preStageOfficialComposerReadinessAwaited: true,
    preStageOfficialComposerReadinessDeadlineBounded: true,
    tabCompleteAloneCanProveComposerMounted: false,
    missingComposerBeforeReadinessClassifiedDirty: false,
    mountedAttachmentEvidenceStillFailsClosed: true
  };
};
