# PR15.48 — Consolidate optional post-write ownership

## Purpose

Continue #107 by removing source-order reassignment and captured-prior aliasing
from:

```text
_pr92Schema17OptionalPostWrite(...)
```

This seam controls only bounded post-write metadata/diagnostic reads. It has no
protected-write authority, but its budgets are part of the conversation-identity
and transport-return safety contract.

## Historical composition

```text
schema17 base optional-read policy
→ schema18 identity-reserve replacement
→ schema19 causal response-body specialization
```

Schema17 introduced short, non-authoritative post-write reads with a final RPC
return reserve.

Schema18 replaced that policy so ordinary optional reads leave a larger dedicated
conversation-identity reserve.

Schema19 captured schema18's effective binding and replaced the public name again.
For a new chat, only the exact completed request's `Network.getResponseBody`
read gets the larger causal-identity budget. Every other optional diagnostic
delegates to schema18's identity-reserve policy.

## Explicit helpers

```text
_pr92Schema17BaseOptionalPostWrite(...)
_pr92Schema18OptionalPostWriteWithIdentityReserve(...)
_pr92Schema19OptionalPostWrite(...)
```

No captured-prior alias remains. Schema19 explicitly delegates non-causal cases
to schema18.

## Sole public owner

`service_worker_optional_postwrite.js` owns:

```text
_pr92Schema17OptionalPostWrite(...)
→ _pr92Schema19OptionalPostWrite(...)
```

For ordinary optional diagnostics:

```text
_pr92Schema19OptionalPostWrite(...)
→ _pr92Schema18OptionalPostWriteWithIdentityReserve(...)
```

## Preserved semantics

- post-write reads remain non-authoritative for the already-submitted write;
- optional diagnostic failure still returns `{ ok: false, value: null }`;
- schema18's dedicated identity reserve remains authoritative for ordinary
  optional reads;
- new-chat exact-request response-body reads retain schema19's causal-identity
  budget and final RPC-return reserve;
- continuation turns retain schema18 policy;
- exact request binding and stream-handoff identity authority are unchanged;
- no retry, second submit, navigation, attachment, cleanup, or canonical-finality
  authority is added.

## Static target

```text
_pr92Schema17OptionalPostWrite public definitions = 1
runtime assignments = 0
_pr92Schema19PriorOptionalPostWrite aliases = 0
```

## Remaining confirmed ownership inventory

After PR15.48:

```text
Temporary state:
  _pr87TemporaryControlSnapshotExpression
```

Recommended order:

1. Temporary snapshot ownership;
2. final static no-reassignment closure gate.

Tracking: #107


## Follow-up ownership note

PR15.49 later consolidates `_pr87TemporaryControlSnapshotExpression` into one
explicit owner inside the detached PR8.7 characterization chain without
reconnecting that historical chain to production runtime assembly.
