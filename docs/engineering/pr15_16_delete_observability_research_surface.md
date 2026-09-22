# PR15.16 — Delete isolated observability research surface

Tracking: #107

## Purpose

PR15.15 removed the PR8.7 Temporary research bootstrap from ordinary startup.
PR15.16 continues the same rule inside `service_worker_observability.js`:

```text
research history
!= production composition
```

This slice removes one fully isolated diagnostic/control concept and one dormant
research-import switch.

## Deleted concept: orphan Browser Authority lease reconciliation

PR15.3 had already removed this concept from ordinary `executeNativeTurn`
ownership and converted it into an explicit diagnostic handler.

No production caller depended on that handler, it was not part of the root public
API, and the Python wrapper existed only for the retained PR8.8 characterization
workflow.

PR15.16 therefore retires the whole surface instead of carrying a permanent
production diagnostic registry entry:

- browser worker;
- Python research runner/provider;
- dedicated tests;
- dedicated PR8.8 documentation.

The Browser Authority production path itself is unchanged. This deletes only the
manual zero-write orphan-reconciliation research RPC.

## Deleted dormant PR10.1 runtime switch

The closed artifact-shape v1-v10 research overlays were already guarded by:

```text
PR101_ARTIFACT_CHARACTERIZATION_ENABLED = false
```

That meant ordinary startup did not execute them, but production source still
contained eleven dormant `importScripts(...)` references and a research re-entry
switch.

PR15.16 removes the switch and those references entirely from the production
assembly source. The closed research files remain as source/Git evidence and are not
loaded by ordinary runtime.

The active generated-artifact observation overlay remains loaded.

## Preserved invariants

- no ordinary-turn write semantics change;
- Browser Authority acquisition/release semantics unchanged;
- Instant selection behavior unchanged;
- response/finality lifecycle unchanged;
- active generated-artifact observation unchanged;
- no new retry path;
- no new product mutation authority.

## Acceptance

```text
orphan lease diagnostic imported by production       = 0
orphan lease diagnostic shipping implementation      = 0
orphan lease Python research wrapper                  = 0
dormant PR10.1 artifact import switch                 = 0
dormant artifact research import refs in observability = 0
active generated-artifact overlay                     = preserved
```
