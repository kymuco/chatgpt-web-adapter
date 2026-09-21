# PR15.14 — Single official-page-turn runtime owner

## Goal

Close the second major import-order ownership axis after PR15.12.

Before this change, page-turn ownership was still distributed across observability,
Temporary identity, rich-input schemas, and ordinary identity.

## Historical graph

The normal outer-to-inner route was:

```text
ordinary identity
→ schema 29
→ schema 20
→ schema 19
→ schema 18
→ schema 17
→ schema 16
→ rich-input base
→ Temporary session identity
→ observability lifecycle
→ recovery base
```

Two bypass edges are intentional and preserved explicitly:

```text
schema 19 new-chat → schema 17
schema 29 rich-turn → schema 19
```

The first bypass skips schema 18 route-based identity fallback for new chats.
The second skips schema 20's obsolete post-return multiplicity/user-gesture
decision while retaining schema 19 request-bound identity.

## After

All former page-turn owners expose named functions and no longer mutate
`executeOfficialPageTurn`.

`service_worker_official_page_turn_lifecycle.js` is loaded at the runtime root
and is the only active assignment to `executeOfficialPageTurn`.

The graph is assembled by named route functions instead of incidental import
order, including both deliberate bypasses.

## Preserved boundaries

This refactor does not change:

- stale-UI recovery;
- phase timing or response observation;
- Temporary session identity;
- rich-input total-turn deadlines;
- schema 16/17 protected page dispatch;
- schema 18 post-write identity reconciliation;
- schema 19 request-bound new-chat identity;
- schema 20 protected-submit request correlation;
- schema 29 request-body correlation;
- ordinary request-bound identity authority;
- retry or canonical-finality policy.
