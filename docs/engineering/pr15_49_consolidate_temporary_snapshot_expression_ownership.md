# PR15.49 — Consolidate Temporary snapshot-expression ownership

## Purpose

Continue #107 by removing the final confirmed source-order ownership seam:

```text
_pr87TemporaryControlSnapshotExpression()
```

This code belongs to the detached PR8.7 Temporary characterization chain. PR15.15
already removed that chain from production runtime assembly, so this slice must
not reconnect it to production.

## Historical composition

```text
service_worker_temporary_chat.js
  defines the base DOM expression
→ service_worker_temporary_chat_state_semantics.js
  reassigns the public expression with aria-label action-state semantics
```

The state-semantics hypothesis remains historical characterization evidence. It
must not acquire production Temporary write authority.

## Explicit helpers

```text
_pr87BaseTemporaryControlSnapshotExpression()
_pr87TemporaryControlSnapshotExpressionWithAriaActionState()
```

## Sole public owner

`service_worker_temporary_snapshot_expression.js` owns:

```text
_pr87TemporaryControlSnapshotExpression()
```

The owner preserves both historical load modes:

```text
state helper loaded
  → _pr87TemporaryControlSnapshotExpressionWithAriaActionState()

state helper absent
  → _pr87BaseTemporaryControlSnapshotExpression()
```

`service_worker_temporary_chat.js` imports this owner only inside the detached
characterization chain. `service_worker_runtime.js` does not import either file.

## Preserved semantics

- the base DOM-only characterization remains available as fallback;
- loading state semantics still makes aria-label action-state interpretation the
  effective snapshot expression;
- raw aria-label/DOM content remains browser-local;
- AX and semantic-notice characterization layers are unchanged;
- production PR8.13 Temporary startup readiness continues to use its copied
  `_cwaTemporaryControlSnapshot` semantics, not this historical PR8.7 chain;
- production Temporary write authority remains request-body proof based;
- no native-turn, submit, retry, navigation, or canonical-finality authority is
  added.

## Static target

```text
_pr87TemporaryControlSnapshotExpression public definitions = 1
runtime assignments = 0
production imports of Temporary characterization chain = 0
```

## Ownership inventory after PR15.49

The confirmed PR15 ownership inventory is empty.

Next step:

1. add the final static no-reassignment closure gate;
2. use that gate to prove the reviewed production ownership surface stays closed;
3. then delete any remaining displaced historical production composition that
   the closure audit identifies.

Tracking: #107


## PR15.50 closure follow-up

PR15.50 replaces the hand-maintained ownership inventory with a recursive
manifest-rooted production worker graph gate. The detached PR8.7 chain remains
outside that graph and becomes a hard failure if it is ever reintroduced.


## PR15.51 retirement follow-up

PR15.49 closed the final ownership seam inside a chain that was already detached
from production. PR15.51 now physically removes that PR8.7 characterization
chain from the extension package. The snapshot-expression implementation remains
available through Git history only; production startup readiness continues to
use `_cwaTemporaryControlSnapshot`.
