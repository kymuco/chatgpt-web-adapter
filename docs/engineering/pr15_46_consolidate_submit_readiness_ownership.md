# PR15.46 — Consolidate submit-readiness ownership

## Purpose

Continue #107 by removing source-order replacement from:

```text
waitForSendButtonPoint(...)
```

This is the remaining public send-readiness seam used by the rich-input submit
path. PR11.7 has a separate compatibility helper for ordinary-text hardening and
does not own this public binding.

## Historical composition

```text
base send-button polling
→ schema12 active-rich-turn outer-deadline wrapper
```

The base helper polls `querySendButtonPoint` until the supplied local timeout.
Schema12 does not change the readiness predicate or grant submit authority. While
a PR9.2 rich-input context is active, it races the complete helper invocation
against the same total rich-turn deadline so a stalled `Runtime.evaluate` cannot
outlive the turn.

## Explicit helpers

```text
_cwaBaseWaitForSendButtonPoint(...)
_pr92Schema12DeadlineBoundedSendReadiness(...)
```

The schema12 helper now delegates directly to the immutable base helper both
outside and inside an active rich-input turn.

## Sole public owner

`service_worker_submit_readiness.js` owns:

```text
waitForSendButtonPoint(...)
→ _pr92Schema12DeadlineBoundedSendReadiness(...)
→ _cwaBaseWaitForSendButtonPoint(...)
```

## PR11.7 boundary

PR11.7 remains separate:

```text
_pr117WaitForSendButtonPoint(...)
```

That helper adds structural UI-drift discovery and is selected explicitly by
PR11.3 ordinary-text submit hardening. It neither replaces
`waitForSendButtonPoint` nor becomes part of the rich-input readiness owner.

## Preserved semantics

- base polling cadence and local timeout behavior are unchanged;
- non-rich callers retain the base behavior;
- active rich-input calls remain bounded by the one outer PR9.2 deadline;
- a late readiness observation has no write authority;
- protected mouse/Enter submit ownership is unchanged;
- no retry, navigation, attachment staging, or canonical-finality authority is
  added.

## Static target

```text
waitForSendButtonPoint public definitions = 1
runtime assignments = 0
_pr92Schema12PriorWaitForSendButtonPoint aliases = 0
```

## Remaining confirmed ownership inventory

After PR15.46:

```text
rich-input:
  _pr92ReadDirtyAttachmentFence
  _pr92Schema17OptionalPostWrite

Temporary state:
  _pr87TemporaryControlSnapshotExpression
```

Recommended order:

1. dirty-fence read ownership;
2. optional post-write ownership;
3. Temporary snapshot ownership;
4. final static no-reassignment closure gate.

Tracking: #107


## Follow-up ownership note

PR15.47 later consolidates `_pr92ReadDirtyAttachmentFence` into one explicit
owner while preserving schema16's active-turn deadline race and fail-closed
durable-fence semantics.
