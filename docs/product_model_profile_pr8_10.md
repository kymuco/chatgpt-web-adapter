# PR8.10.1 — Semantic Model Profiles over Proven Reasoning-Effort Slider

Status: CLOSED — live-proven and graduated to the production product runtime surface.

## Goal

Generalize the already-proven PR8.8 production effort selector without reopening picker research.

HDE-facing semantic intent:

```text
FAST     -> INSTANT -> slider 0
BALANCED -> MEDIUM  -> slider 1
DEEP     -> HIGH    -> slider 2
MAX      -> UNMAPPED
```

`MAX` is deliberately not synthesized from the existing three-state slider.

## Selection contract

An explicit profile requirement is strict:

```text
profile requested
  -> exact product target resolved
  -> current product mode proven
  -> if needed, proven 0..2 effort slider focused
  -> Home establishes index 0
  -> bounded ArrowRight count reaches target index
  -> selected product mode proven before prompt insertion/write
or
  -> fail before conversation write
```

The existing PR8.8 Instant path remains in the call chain. PR8.10 uses the same proven browser-local primitives rather than introducing a new picker topology.

A mode already selected requires no mutation and no transient foreground activation.

## Safety

- one ordinary browser-owned product write per test turn;
- no automatic retry;
- no model-option coordinate guessing;
- no Advanced navigation;
- no raw request/response export;
- no Fetch interception;
- no response-body extraction;
- conversation write before selection proof is a hard failure;
- unsupported explicit product modes fail before write;
- no silent profile fallback.

## Production live evidence

The bounded sequence completed successfully:

```text
FAST -> DEEP -> BALANCED
```

Observed evidence:

- `FAST`: `INSTANT -> INSTANT`, `NO_SELECTION_REQUIRED`, selected mode proven before write;
- `DEEP`: `INSTANT -> HIGH`, slider index `2`, transient foreground activation and restoration proven;
- `BALANCED`: `HIGH -> MEDIUM`, slider index `1`, transient foreground activation and restoration proven;
- all three turns reported `conversationWriteBeforeSelection = false`;
- `write_attempts = 3`, `write_completions = 3`, `automatic_write_retry = false`;
- `strict_prewrite_selection_supported = true`;
- `all_three_slider_states_proven = true`;
- `max_profile_mapped = false`.

The first post-write evidence lookup exposed a namespace collision between PR8.10's stored selection lease and the outer PR8.8 transport lease envelope. The repair moved the selection record into a dedicated `modelProfileSelection` namespace; a repeated full live gate then passed.

## Production runtime surface

`ChatGPTProductRuntime.send`, `send_text`, and `send_text_observed` accept a per-turn semantic requirement:

```python
runtime.send(
    "hello",
    conversation=conversation,
    model_profile="DEEP",
)
```

The generic `ProductWriteTransport` protocol remains unchanged. `model_profile=` is forwarded only when the selected transport explicitly advertises PR8.10 support. The browser-owned transport places the requirement inside the same `ProductModelProfileProvider.require_profile()` context used by the successful live gate.

A custom browser-native provider that does not expose the PR8.10 profile context does not inherit the capability claim and rejects an explicit profile before write.

## Capability boundary

The production browser-owned transport now graduates only the capabilities supported by live evidence:

```text
model_selection        = AVAILABLE
reasoning_selection    = AVAILABLE
model_preservation     = UNKNOWN
reasoning_preservation = UNKNOWN
```

Cross-conversation sticky-state scope was not established by the three-state transition gate. Selection is therefore modeled as a `TURN_REQUIREMENT`; preservation remains unclaimed until independent scope evidence exists.

Preservation is not an unresolved PR8.10 shipping blocker: PR8.10 closes with the narrower, evidence-backed per-turn selection contract and leaves independent cross-conversation preservation proof to future work.

## Final validation

- focused PR8.10/PR8.8/PR8.9 integration gate: `48 passed`;
- PR8.8 browser-native provider compatibility boundary: `4 passed`;
- repository-wide regression suite: `1136 passed`;
- no additional live product writes were required after the successful bounded PR8.10 live gate;
- the two full-suite repairs were test-double compatibility updates only and did not change the production write path.
