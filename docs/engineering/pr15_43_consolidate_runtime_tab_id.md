# PR15.43 — Consolidate runtime-tab-id ownership

## Purpose

Continue #107 by removing source-order replacement from storedRuntimeTabId().

Historical behavior had two phases:

- initial extension bootstrap: raw persisted runtime-tab id read;
- runtime after reconciliation loads: live validation and stale-state repair.

PR15.43 makes those stages explicit.

## Explicit stages

Immutable persisted-id reader:

    _cwaBaseStoredRuntimeTabId()

Live-validation helper:

    _pr824a3StoredRuntimeTabIdWithLiveValidation()
    → _pr824a3ValidateStoredRuntimeTab()
    → _cwaBaseStoredRuntimeTabId()

Sole public production owner:

    service_worker_runtime_tab_id.js

Runtime call graph:

    storedRuntimeTabId()
    → _pr824a3StoredRuntimeTabIdWithLiveValidation()
    → _pr824a3ValidateStoredRuntimeTab()
    → _cwaBaseStoredRuntimeTabId()

## Preserved bootstrap semantics

The first native bridge connection is established while the base worker is still
loading, before runtime reconciliation installs the public owner. Historically
the native hello therefore read the raw persisted runtime-tab id.

PR15.43 preserves that behavior explicitly:

    _cwaBaseConnectNativeBridge()
    → _cwaBaseStoredRuntimeTabId()
    → hello.runtimeTabId

No live validation is introduced into that bootstrap edge.

## Preserved runtime semantics

Base runtime helpers such as _cwaBaseEnsureRuntimeTab and the tabs.onRemoved
listener continue resolving the public storedRuntimeTabId symbol dynamically.
After runtime assembly completes, those calls therefore use the live-validated
owner.

Canonical read, observability, product surface, retained-tab, rich-input,
connector-support, UI-liveness, and characterization paths likewise continue
using the final public owner.

## Preserved reconciliation behavior

The reconciliation state machine still:

- validates the persisted tab with chrome.tabs.get;
- requires the tab URL to remain under the ChatGPT origin;
- clears stale persistent state only when the expected id still matches;
- tolerates concurrent replacement;
- updates native runtime state when stale state is cleared;
- tracks tabs.onUpdated and tabs.onReplaced;
- publishes validated runtime state on startup;
- never creates a new tab or claims write authority.

Internal stale-state bookkeeping now calls the immutable base reader directly
instead of a captured-prior alias.

## Assembly

The runtime root now begins:

    service_worker_runtime_tab_reconciliation.js
    → service_worker_runtime_tab_id.js
    → service_worker_runtime_write.js

## Static target

    storedRuntimeTabId public definitions = 1
    storedRuntimeTabId runtime assignments = 0
    _pr824a3RawStoredRuntimeTabId aliases = 0

## Authority

PR15.43 changes ownership only. It does not add runtime-tab creation,
navigation, Browser Authority, ChatGPT write, retry, or canonical-finality
authority.

## Remaining confirmed ownership inventory

After PR15.43, storedRuntimeTabId is removed from the PR15.40 inventory.

Still confirmed:

    recovery / deadline:
      waitForTabComplete
      _pr811ReloadRuntimeTabAndWait
      _pr811MaybeRecoverStaleRuntimeUi

    rich-input schema hooks:
      _pr92ClosureReadPageOwnedAttachmentEvidence
      waitForSendButtonPoint
      _pr92Schema10RequireOfficialCleanComposerBeforeStaging
      _pr92Schema12ObservePostStageAttachmentEvidence
      _pr92ReadDirtyAttachmentFence
      _pr92Schema17OptionalPostWrite

    Temporary state:
      _pr87TemporaryControlSnapshotExpression

Final closure still requires consolidation of those names and a static
no-reassignment gate over the shipping worker surface.

Tracking: #107


## Follow-up ownership note

PR15.44 later consolidates the remaining recovery/deadline hook trio:
`waitForTabComplete`, `_pr811ReloadRuntimeTabAndWait`, and
`_pr811MaybeRecoverStaleRuntimeUi`. The explicit composition preserves
PR9.2's single rich-turn deadline and post-recovery attachment staging without
captured-prior aliases.
