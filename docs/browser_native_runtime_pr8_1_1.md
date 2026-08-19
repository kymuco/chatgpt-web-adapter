# PR8.1.1 — Canonical-Completion-Backed Stale Runtime UI Recovery

PR8.1.1 repairs a lifecycle mismatch observed during live PR8.1 continuation:
the canonical conversation had already completed, while the persistent
background ChatGPT tab still exposed a generation control and therefore rejected
the next turn as `CHATGPT_COMPOSER_NOT_READY:generation_control_visible`.

## Core invariant

A visible generation control is never treated as stale by itself.

Recovery is authorized only when:

1. the request targets an existing conversation;
2. canonical `get_status()` reports `completed`;
3. an immediate second canonical status check still reports `completed`;
4. the completion evidence reaches the extension within five seconds;
5. the dedicated runtime tab still reports `generation_control_visible` before
   any prompt text is inserted.

If any condition fails, the ordinary PR8.1 readiness path remains authoritative.

## Recovery flow

```text
continuation request
      |
      v
canonical status #1 == completed?
      | yes
      v
canonical status #2 == completed?
      | yes
      v
fresh completion evidence -> Native Messaging
      |
      v
runtime tab UI says generation_control_visible?
      | yes
      v
bounded background reload (<=45s)
      |
      v
same conversation id still loaded?
      | yes
      v
ordinary core turn path exactly once
```

The reload happens before composer focus, `Input.insertText`, submit activation,
or any observed conversation POST. There is therefore no ambiguous prior write
to replay.

## Duplicate-safety boundary

PR8.1.1 does not retry after:

- prompt insertion;
- submit activation;
- an observed conversation POST;
- HTTP/stream failure after the write begins;
- canonical `running`, `unknown`, or failed status reads;
- stale completion evidence;
- a reload that lands on a different conversation id.

The recovery wrapper invokes the core turn implementation exactly once after a
successful reload.

## Safe diagnostics

The bridge may additionally return:

- `runtimeReloaded: bool`;
- `runtimeReloadMs: int | null`.

No canonical status payload or browser session material is added to the bridge
protocol.

## Live validation target

Reproduce a completed conversation whose runtime tab remains visually stuck in
generation state, then issue a continuation without manually refreshing the tab.
Expected behavior:

```text
canonical completed
runtime UI stale
      -> one automatic background reload
      -> same conversation id
      -> continuation sent once
      -> canonical SDK readback completes
```
