# PR15.3 — Detach Zero-Write Control Characterization

> **PR15.17 supersession:** the orphan-lease and reasoning-effort characterization diagnostics described below were later retired and deleted from the shipping tree. The Instant-effort support owner remains pending its own consolidation slice.

Status: implementation candidate  
Base: `e7a3fe8ca78562265c27128fc739076d52a1e980`  
Tracking: #107  
Pull request: #111

## Goal

Remove characterization/control-only `executeNativeTurn` ownership from the ordinary
ChatGPT product path.

PR15.3 migrates three concepts whose wrappers had no ordinary-turn behavior:

- orphan Browser Authority lease reconciliation;
- retained reasoning-effort slider characterization;
- Instant effort-selection support.

For an ordinary request, all three wrappers previously delegated directly to the prior
`executeNativeTurn`.

## New ownership

Each concept now has one explicit diagnostic/control owner:

```text
orphan-lease-reconciliation
reasoning-effort-characterization
instant-effort-support
```

The three modules no longer redefine `executeNativeTurn`.

Ordinary product requests therefore do not pass through these historical
characterization layers.

## Preserved boundaries

### Orphan lease reconciliation

This surface may clear stale local Browser Authority metadata and an orphan lease, but
it performs zero ChatGPT product writes.

It preserves:

- exact lease compare-and-clear;
- runtime-tab presence fence;
- state-change abstention;
- no lease-id export;
- zero product writes;
- no automatic retry.

### Reasoning-effort characterization

This remains a retained-tab UI characterization surface. Optional UI navigation may
open the quick picker or Advanced only when explicitly acknowledged.

It preserves:

- zero conversation writes;
- no selection-control click;
- bounded topology export;
- no raw text export;
- no automatic retry.

### Instant effort support

This remains a no-write capability/support RPC describing the already-proven Instant
effort selection path.

It preserves:

- quick-picker-only contract;
- exact discrete range;
- semantic Home-key selection support;
- selected-Instant proof requirement;
- Advanced/model control click prohibition;
- no automatic retry.

## Deliberate non-migrations

PR15.3 does not move mixed-use layers that still participate in ordinary writes:

- Browser Authority phase timing;
- post-answer tail timing;
- Instant-mode observation;
- Instant selection repair;
- model-profile selection;
- rich-input repair/schema lineage;
- production Temporary lifecycle.

Those require separate migrations because removing their wrappers changes actual
ordinary-turn instrumentation or write semantics.

## Deterministic proof

The PR adds source and Node behavior tests proving:

- migrated modules contain no `executeNativeTurn` override or prior-turn alias;
- ordinary requests match none of the new handlers;
- support RPCs retain their frozen response contracts;
- orphan reconciliation and reasoning topology route to their existing implementation
  functions;
- zero-write, no-retry and no-selection authority boundaries remain explicit.

Existing provider/worker tests continue to validate the public result parsing and
safety contracts.

## Acceptance

```text
migrated ordinary-path wrappers = 0
+
explicit characterization/control owners = 3
+
ordinary requests claimed by them = 0
+
existing provider/worker contracts pass
+
full supported OS / Python / installed-wheel CI passes
```

No live product write is required because these three migrated ownership surfaces do
not perform ordinary ChatGPT product turns.
