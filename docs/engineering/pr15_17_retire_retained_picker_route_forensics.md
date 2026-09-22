# PR15.17 — Retire retained picker / route forensics

Tracking: #107

## Purpose

PR15.17 removes two PR8.8 read-only post-failure characterization concepts from
the shipping runtime:

- retained route identity forensics;
- retained picker surface forensics.

Both concepts had already been moved out of ordinary `executeNativeTurn`
ownership. They remained explicit diagnostic handlers loaded by production and
also formed unnecessary inheritance layers in the Python research stack.

## Production boundary

Before:

```text
Instant selection
→ failure evidence
→ retained route diagnostic
→ retained picker diagnostic
```

After:

```text
Instant selection
→ bounded in-failure evidence
→ original failure propagation
```

The in-failure popup-subtree evidence already captures bounded route identity and
picker topology while the failure state is still present. PR15.17 therefore removes
the later retained-tab re-probes rather than preserving two overlapping diagnostic
systems.

## Ownership flattening

`ReasoningEffortSliderProvider` and `InstantFailureForensicsProvider` now inherit
directly from `InstantSelectionRepairProvider`.

This removes historical research inheritance from active provider composition.

## Deleted surface

- two browser diagnostic workers;
- two Python retained-forensics providers/runners;
- two dedicated test modules;
- two dedicated PR8.8 documents.

## Preserved behavior

PR15.17 does not change:

- Instant selection/click behavior;
- picker-trigger identity/timeline instrumentation;
- in-failure popup-subtree capture;
- failure record persistence;
- prompt insertion or submit;
- Browser Authority semantics;
- retry authority;
- canonical finality.

The original selection exception is still re-thrown unchanged.

## Acceptance

```text
retained picker worker in shipping tree       = 0
retained route worker in shipping tree        = 0
retained picker Python provider               = 0
retained route Python provider                = 0
retained-forensics production imports         = 0
provider inheritance through retained probes  = 0
in-failure evidence capture                   = preserved
picker-trigger production semantics           = preserved
```
