# PR15.8 — Response lifecycle composition

## Goal

Replace the response-observation `executeNativeTurn` monkeypatch chain with one
explicit composition owner while preserving the established nested lifecycle.

## Before

Six adjacent layers independently captured and reassigned `executeNativeTurn`:

1. safe browser response stream;
2. revision-safe text delivery;
3. post-answer tail timing;
4. early product completion;
5. early product completion repair;
6. normalized activity stream.

Import order implicitly defined runtime nesting.

## After

The six modules keep their lower-level SSE, assistant-record, and page-turn hooks,
but expose their native-turn behavior as composable `(message, next)` layers.

`service_worker_response_lifecycle_pr15_8.js` is the single native-turn owner for
the cluster and freezes the historical outer-to-inner order explicitly:

```text
normalized activity
→ early completion repair
→ early completion
→ tail timing
→ revision-safe delivery
→ safe browser stream
→ prior runtime
```

The owner is imported at the former outer edge of this cluster, after normalized
activity and before connector lifecycle, so surrounding runtime nesting is
unchanged.

## Preserved boundaries

This slice does not change canonical finality, protected write authority, Browser
Authority, SSE parsing, activity normalization, early-completion acceptance,
retry policy, or raw-data export boundaries.
