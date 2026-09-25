# PR15.47 — Consolidate dirty-fence read ownership

## Purpose

Continue #107 by removing source-order reassignment from the durable dirty
attachment fence read:

```text
_pr92ReadDirtyAttachmentFence()
```

The read is safety-critical because a missing or unreadable durable fence cannot
be interpreted as proof that a previous staged composer is clean.

## Historical composition

```text
PR9.2 base durable-fence read
→ schema16 active-turn outer-deadline repair
```

The base implementation reads `PR92_DIRTY_ATTACHMENT_STORAGE_KEY`, normalizes
the persisted `tabId`, updates `_pr92DirtyAttachmentTabId`, and fails closed
with `PR9_2_STALE_ATTACHMENT_FENCE_READ_FAILED` on storage errors.

Schema16 adds one behavior: while a PR9.2 turn is active, the storage read itself
is raced against the authoritative outer turn deadline.

## Explicit helpers

```text
_pr92BaseReadDirtyAttachmentFence()
_pr92Schema16ReadDirtyAttachmentFenceWithinDeadline()
```

Outside an active turn, schema16 delegates directly to the immutable base helper.

Inside an active turn, schema16 intentionally races the raw storage read before
decoding or mutating `_pr92DirtyAttachmentTabId`. This preserves the historical
rule that a storage operation completing only after the deadline cannot mutate
the live fence state after the turn has already timed out.

## Sole public owner

`service_worker_attachment_fence_read.js` owns:

```text
_pr92ReadDirtyAttachmentFence()
→ _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline()
```

## Preserved semantics

- durable local storage remains the cleanup authority;
- missing/invalid persisted `tabId` still normalizes to `null`;
- storage failure still fails closed;
- non-active callers retain the original base behavior;
- active-turn reads remain bounded by the one outer PR9.2 deadline;
- timeout errors remain distinguishable from storage-read failures;
- late storage completion after timeout cannot update the in-memory dirty tab id;
- persistence, clear, destructive cleanup, staging, submit, retry, navigation,
  and canonical-finality authority are unchanged.

## Static target

```text
_pr92ReadDirtyAttachmentFence public definitions = 1
runtime assignments = 0
_pr92Schema16ReadDirtyAttachmentFenceWithinDeadline definitions = 1
```

## Remaining confirmed ownership inventory

After PR15.47:

```text
rich-input:
  _pr92Schema17OptionalPostWrite

Temporary state:
  _pr87TemporaryControlSnapshotExpression
```

Recommended order:

1. optional post-write ownership;
2. Temporary snapshot ownership;
3. final static no-reassignment closure gate.

Tracking: #107


## Follow-up ownership note

PR15.48 later consolidates `_pr92Schema17OptionalPostWrite` into one explicit
owner while preserving schema18's identity reserve and schema19's request-bound
causal response-body specialization.
