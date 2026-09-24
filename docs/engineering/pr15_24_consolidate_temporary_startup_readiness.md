# PR15.24 — Consolidate Temporary startup-readiness ownership

## Purpose

Continue #107 by removing the remaining PR8.13.2 source-order hook reassignment around Temporary startup readiness and proof diagnostics.

Before this slice, the historical readiness worker captured and reassigned:

```text
submitOfficialPageTurn
_pr813ResolveProof
_pr813RejectProof
```

after `service_worker_temporary_product.js` had already defined the product hooks.

That made startup-readiness behavior depend on import order.

## New ownership boundary

PR15.24 introduces:

```text
service_worker_temporary_startup_readiness.js
```

as a pure helper owner. It contains:

- fresh Temporary readiness sampling;
- bounded readiness wait;
- proof-resolution diagnostics;
- proof-rejection diagnostics;
- prewrite-abort classification;
- startup diagnostic result projection.

It does **not** reassign production hooks.

The assembly order is now explicit:

```text
Temporary startup-readiness helpers
→ Temporary product owner
→ Temporary native lifecycle owner
```

## Product-owned hooks

`service_worker_temporary_product.js` remains the sole owner of the actual product hooks.

Proof flow:

```text
_pr813ResolveProof
→ _pr8132ResolveProofWithDiagnostics
→ _pr813ResolveProofCore

_pr813RejectProof
→ _pr8132RejectProofWithDiagnostics
→ _pr813RejectProofCore
```

Submit flow:

```text
submitOfficialPageTurn
→ _pr813SubmitOfficialPageTurn
→ _pr8132SubmitOfficialPageTurnWithReadiness
→ _pr813SubmitOfficialPageTurnCore
→ prior official-page submit
```

The readiness helper therefore participates through an explicit call path instead of source-order monkeypatching.

## Preserved authority model

- startup readiness remains non-authoritative;
- only fresh Temporary turns receive the readiness delay;
- URL / composer / control state remain hints only;
- `history_and_training_disabled === true` on the Fetch-paused page-generated request remains the only prewrite mode authority;
- failed proof still aborts with `Fetch.failRequest`;
- no automatic retry;
- no durable fallback;
- continuation identity and live lifecycle binding remain unchanged;
- `service_worker_temporary_lifecycle.js` remains a separate explicit native-turn owner.

## Acceptance

- neutral startup-readiness production filename;
- historical PR8.13.2 readiness worker absent from shipping runtime;
- zero readiness assignments to `submitOfficialPageTurn`, `_pr813ResolveProof`, or `_pr813RejectProof`;
- zero retired prior-function aliases;
- Temporary product owns the real hooks and calls readiness explicitly;
- readiness loads before product, product before Temporary lifecycle;
- Fetch-paused proof semantics unchanged;
- PR15.11 lifecycle ordering unchanged;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
