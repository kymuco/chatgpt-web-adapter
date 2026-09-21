# PR15.11 — Temporary production lifecycle composition

## Goal

Replace the three remaining PR8.13 production `executeNativeTurn` wrappers with
one explicit lifecycle owner while preserving Temporary write authority and
startup/readback semantics.

## Before

Import order implicitly produced this outer-to-inner chain:

```text
startup readiness
→ fresh identity flush
→ Temporary production
→ prior runtime
```

`service_worker_temporary_session_identity_pr8_13.js` participates through
lower-level page-turn/SSE hooks and does not own `executeNativeTurn`.

## After

The three native-turn modules expose composable `(message, next)` layers.

`service_worker_temporary_lifecycle.js` is the single native-turn owner for the
cluster and is imported immediately after startup readiness, preserving the
historical outer boundary.

The production helper itself receives `next` explicitly so its one delegated
product write crosses the same inner runtime boundary as before.

## Preserved boundaries

This change does not alter the browser-local request-body Temporary proof,
fresh/continuation identity checks, owned inactive tab lifecycle, explicit
lifecycle end proof, live SSE session routing identity, startup readiness,
automatic retry policy, Browser Authority, or canonical finality.
