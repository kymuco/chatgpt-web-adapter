# PR15.50 — Final browser-worker ownership closure gate

## Purpose

Close the PR15 ownership pass with a static proof over the production browser-worker
import graph rather than another hand-maintained symbol inventory.

The gate starts at the manifest background service worker and recursively follows
active literal `importScripts(...)` edges. Only files reachable through that graph
are production ownership surface.

## Closure audit result

The earlier confirmed ownership inventory was empty after PR15.49, but the graph-wide
audit found two older shipping seams that had been called "single owners" while still
depending on mutable global bindings:

```text
service_worker_selection_preparation.js
  locateAndFocusComposer = async function ...
  _cwaSelectionPreparationPriorLocateAndFocusComposer

service_worker_ui_compat_pr11_7.js
  queryComposerReadiness = _pr117QueryComposerReadiness
  _pr117HistoricalQueryComposerReadiness
```

PR15.50 closes both before enabling the gate.

## Explicit composer-focus ownership

Base:

```text
_cwaBaseLocateAndFocusComposer(...)
```

Public production owner:

```text
locateAndFocusComposer(...)
→ _pr810PrepareComposer(...)
→ _pr88SelectionPrepareComposer(...)
→ _pr88InstantObserveComposerBeforeWrite(...)
→ _cwaBaseLocateAndFocusComposer(...)
```

No captured prior alias remains.

## Explicit composer-readiness ownership

Base:

```text
_cwaBaseQueryComposerReadiness(...)
```

PR11.7 compatibility helper:

```text
_pr117QueryComposerReadiness(...)
→ _cwaBaseQueryComposerReadiness(...)
→ bounded structural fallback only when historical discovery reports composer_missing
```

Public production owner:

```text
queryComposerReadiness(...)
→ _pr117QueryComposerReadiness(...)
```

No runtime assignment or historical query alias remains.

## Static closure gate

`tools/browser_worker_ownership_closure_gate.py`:

1. reads `manifest.json`;
2. resolves the background worker;
3. recursively follows active `importScripts(...)` edges;
4. rejects any reachable top-level bare identifier assignment;
5. rejects reachable captured aliases whose names encode historical composition
   (`Prior`, `Original`, or `Upstream`);
6. rejects any accidental production reachability of the detached PR8.7 Temporary
   characterization chain.

The engineering quality gate invokes this check on every CI run, independent of
which files changed.

## Detached historical evidence

The PR8.7 Temporary characterization chain remains source evidence only. It may retain
historical internal mutation patterns, but it is not exempted inside the production
graph: if any of those files becomes reachable from the manifest worker, the closure
gate fails immediately.

## Preserved semantics

- composer focus still performs model-profile preparation, Instant selection repair,
  Instant prewrite observation, then the original AX/DOM focus;
- PR11.7 readiness still prefers historical readiness and uses structural discovery
  only for `composer_missing`;
- no write, retry, navigation, Browser Authority, or canonical-finality boundary changes;
- detached Temporary characterization remains detached;
- provider behavior is unchanged.

## Closure target

```text
reachable production worker top-level rebindings = 0
reachable captured historical aliases            = 0
reachable detached Temporary characterization    = 0
```

After this gate is green, PR15 ownership closure is mechanically enforced rather
than maintained as a prose inventory.

Tracking: #107
