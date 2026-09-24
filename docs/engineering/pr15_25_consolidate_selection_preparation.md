# PR15.25 — Consolidate composer-selection preparation

## Purpose

Continue #107 by removing the remaining source-order `locateAndFocusComposer`
composition across model-profile selection, Instant selection repair, and Instant
mode observation.

Before this slice, three shipping modules independently captured and reassigned
`locateAndFocusComposer`:

```text
service_worker_instant_mode_pr8_8.js
service_worker_instant_selection_repair_pr8_8.js
service_worker_model_profile_selection_pr8_10.js
```

Because each wrapper called its prior function, the effective order was:

```text
model-profile selection
→ Instant selection repair
→ Instant prewrite observation
→ base composer focus
```

## New production owner

Production now loads:

```text
service_worker_selection_preparation.js
```

after the three capability modules and before the explicit selection native-turn
lifecycle owner.

The former wrappers are now pure helpers:

```text
_pr810PrepareComposer
_pr88SelectionPrepareComposer
_pr88InstantObserveComposerBeforeWrite
```

The single composer owner calls them explicitly:

```text
locateAndFocusComposer
→ _pr810PrepareComposer
→ _pr88SelectionPrepareComposer
→ _pr88InstantObserveComposerBeforeWrite
→ prior/base locateAndFocusComposer
```

## Preserved boundaries

- model-profile target selection still executes before Instant repair;
- Instant repair still completes before the prewrite picker snapshot;
- no prompt insertion occurs before selection preparation completes;
- model-selection write-boundary observation is unchanged;
- Instant effort slider semantics are unchanged;
- Instant network-hint extraction remains in its existing module;
- phase timing remains separate;
- native-turn selection lifecycle ordering remains unchanged.

## Acceptance

- one shipping `locateAndFocusComposer` owner for selection preparation;
- zero composer assignments in the three former wrapper modules;
- zero retired composer prior aliases;
- exact historical helper order regression-tested;
- runtime handoff to the base composer regression-tested;
- existing selection lifecycle remains the native-turn owner;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
