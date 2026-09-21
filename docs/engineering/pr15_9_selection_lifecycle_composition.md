# PR15.9 — Selection lifecycle composition

## Goal

Replace the model-selection/phase-timing `executeNativeTurn` monkeypatch chain
with one explicit lifecycle owner while preserving the established nesting.

## Before

Four adjacent layers independently captured and reassigned `executeNativeTurn`:

1. phase timing;
2. Instant mode observation;
3. Instant selection repair;
4. model-profile selection.

Import order implicitly produced this outer-to-inner runtime chain:

```text
model profile
→ Instant selection repair
→ Instant mode observation
→ phase timing
→ prior runtime
```

## After

The four modules keep their lower-level picker, composer, page-turn, stream
metadata, and timing hooks, but expose native-turn behavior as composable
`(message, next)` layers.

`service_worker_selection_lifecycle.js` is the single native-turn owner for the
cluster and freezes the historical order explicitly.

The owner is imported immediately after model-profile selection and before the
response lifecycle modules, so surrounding runtime nesting is unchanged.

## Preserved boundaries

This change does not alter model-selection proof, Browser Authority, write
authority, phase timing intervals, Instant route evidence, model-profile mapping,
retry policy, or finality semantics.
