# PR15.42 — Consolidate runtime lifecycle ownership

## Purpose

Continue #107 by removing the final assignment-form ownership from the two root
runtime dispatch names:

```text
executeNativeTurn(...)
executeOfficialPageTurn(...)
```

PR15.8 through PR15.14 already converted the historical domain monkeypatch chains
into explicit lifecycle helpers and composition owners. PR15.42 does not reorder
those graphs. It finalizes the root ownership form.

## Native-turn ownership

The original worker entrypoint is now named:

```text
_cwaBaseExecuteNativeTurn(message)
```

The root lifecycle remains:

```text
ordinary-text identity
→ rich-input lifecycle
→ browser-authority lease
→ Temporary lifecycle
→ response lifecycle
→ selection lifecycle
→ stale-UI recovery
→ _cwaBaseExecuteNativeTurn(...)
```

The sole public production owner is the function declaration in:

```text
service_worker_native_turn_lifecycle.js
```

No captured prior binding remains.

## Official-page-turn ownership

The original PR8-era worker page-turn implementation is retained under the
historical base name:

```text
_cwaBaseExecuteOfficialPageTurn(...)
```

It is not the active terminal of the current page-turn graph.

The reviewed active graph remains:

```text
ordinary identity
→ schema29
→ schema20
→ schema19
→ schema18 / intentional schema19 bypass
→ schema17
→ schema16
→ rich base
→ Temporary session identity
→ observability lifecycle
→ recovery terminal
```

with the deliberate schema29 → schema19 bypass of schema20 preserved.

The active observability terminal remains:

```text
_executeOfficialPageTurnWithEarlyTerminalBoundary(...)
```

from `service_worker_recovery.js`.

The sole public `executeOfficialPageTurn` owner is now a normal function
declaration in `service_worker_official_page_turn_lifecycle.js`.

## Cross-root handoff

`_cwaBaseExecuteNativeTurn` continues calling the public
`executeOfficialPageTurn` name dynamically.

Because `service_worker_runtime.js` loads the official-page owner before the
native-turn owner, ordinary runtime dispatch therefore keeps the reviewed page
lifecycle rather than bypassing it to the displaced historical base page-turn.

## Static target

```text
executeNativeTurn public definitions = 1
executeNativeTurn runtime assignments = 0
_cwaNativeTurnBaseExecute aliases = 0

executeOfficialPageTurn public definitions = 1
executeOfficialPageTurn runtime assignments = 0
```

## Authority

PR15.42 changes root ownership form only.

It does not add or reorder:

- Browser Authority;
- rich-input authority;
- Temporary authority;
- submit authority;
- response/finality authority;
- retry/recovery behavior;
- lifecycle bypass edges.

## Remaining confirmed ownership inventory

After PR15.42, `executeNativeTurn` and `executeOfficialPageTurn` are removed
from the PR15.40 confirmed inventory.

Still confirmed:

```text
runtime tab state:
  storedRuntimeTabId

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
```

Final closure still requires consolidation of those names and a static
no-reassignment gate over the shipping worker surface.

Tracking: #107


## Follow-up ownership note

PR15.43 later consolidates `storedRuntimeTabId` into an explicit owner while
preserving the historical distinction between the initial raw persisted-id read
used by native bootstrap and live-validated runtime reads after reconciliation.
