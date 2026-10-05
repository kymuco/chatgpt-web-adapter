# PR17.2 Phase C — Reasoning State Scope

Status: LIVE-PROVEN.

## Question

PR17.2 proved that CWA can select `INSTANT / MEDIUM / HIGH` in a hidden
runtime tab before write. Phase C separately asks where ChatGPT stores that
reasoning mode after the write:

- per existing conversation;
- only in one renderer/runtime tab;
- shared across conversations;
- or as a setting-like default for new chats.

This proof does not relax the per-turn selection safety contract.

## Experiment

The bounded live gate started with no CWA runtime tab and performed exactly
three product writes:

```text
conversation A: DEEP     -> HIGH
conversation B: BALANCED -> MEDIUM
conversation A: FAST     -> INSTANT
```

It then performed seven read-only observations:

```text
persistent runtime navigation:
  A after B setup
  B after setup
  A after A -> INSTANT
  B after A -> INSTANT
  new-chat surface

fresh active:false renderers:
  A after A -> INSTANT
  B after A -> INSTANT
  new-chat surface
```

Every observation required three consecutive identical proven mode snapshots,
zero conversation writes, no tab activation, debugger detach, and temporary
tab cleanup for fresh-renderer samples.

The gate used the production commit-bound provider so the continuation
baseline canonical read occurred before activation of the new write lease.

## Live result

The gate completed:

```text
write_attempts              = 3
write_completions           = 3
automatic_write_retry       = false
read_only_observation_count = 7
ok                          = true
runtime_revision            = PR17_2_BACKGROUND_PRODUCTION_R12
```

Observed modes:

```text
persistent runtime:
  A after B setup       = HIGH
  B after setup         = MEDIUM
  A after mutation      = INSTANT
  B after A mutation    = MEDIUM
  new chat              = INSTANT

fresh renderers:
  A after mutation      = INSTANT
  B after A mutation    = MEDIUM
  new chat              = INSTANT
```

Classifier verdict:

```text
CONVERSATION_LOCAL_DURABLE
```

## Interpretation

Existing durable conversations preserve distinct reasoning state.

The proof is stronger than same-renderer navigation:

- A retained `INSTANT` in a fresh renderer;
- B independently retained `MEDIUM` in another fresh renderer;
- mutating A did not mutate B.

Therefore the observed reasoning state is not merely renderer-local or a
single shared session variable.

The new-chat surface behaved differently. Both same-renderer and fresh-renderer
new-chat observations hydrated `INSTANT`, matching the most recently selected
reasoning mode from A. The bounded evidence therefore supports a separate
setting-like/default behavior for new chats:

```text
existing conversation reasoning state = conversation-local durable
new-chat reasoning default            = last-selected mode observed
```

The experiment establishes the observed behavior but does not identify the
backend storage mechanism or claim that every future product version must use
the same defaulting policy.

## Capability graduation

The browser-owned ChatGPT transport may now report:

```text
model_selection        = AVAILABLE
reasoning_selection    = AVAILABLE
model_preservation     = UNKNOWN
reasoning_preservation = AVAILABLE
```

The preservation claim is specifically:

```text
reasoning_preservation_scope = CONVERSATION_LOCAL_DURABLE
```

`model_preservation` remains `UNKNOWN` because Phase C did not vary or
independently prove model identity preservation.

## Safety boundary remains unchanged

Durable preservation is observational evidence, not write authority.

CWA still treats every explicit profile request as:

```text
TURN_REQUIREMENT
  -> prove requested reasoning mode before write
  -> otherwise fail before conversation write
```

In particular:

- preservation never authorizes skipping strict prewrite verification;
- new-chat default state is not trusted as an explicit requested profile;
- no automatic retry is introduced;
- no foreground activation is introduced;
- no claim is made for `MAX` or a fourth selector.

Tracks #197. PR #199 contains the Phase C diagnostic surface, bounded live gate,
tests, and capability graduation.
