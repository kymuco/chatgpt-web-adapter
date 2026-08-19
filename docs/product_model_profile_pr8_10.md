# PR8.10.1 — Semantic Model Profiles over Proven Reasoning-Effort Slider

Status: implementation-ready for one bounded live gate.

## Goal

Generalize the already-proven PR8.8 production effort selector without reopening picker research.

HDE-facing semantic intent for this characterization slice:

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

The existing PR8.8 Instant path remains in the call chain. This overlay uses the same proven browser-local primitives rather than introducing a new picker topology.

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
- unsupported explicit product modes fail before write.

## Live gate

One sequence only:

```text
FAST -> DEEP -> BALANCED
```

This proves all three characterized slider states and both direction changes with three writes total.

The gate records requested mode, selected mode before/after, slider target, whether mutation was needed, foreground activation/restoration, Browser Authority lease identity, and the exact assistant acknowledgement.

## Capability boundary

This slice does **not** yet graduate `model_selection`, `reasoning_selection`, `model_preservation`, or `reasoning_preservation` to `AVAILABLE`.

Why:

- strict selection must first survive the live three-state gate;
- cross-conversation sticky-state scope is not proven by a single-conversation transition sequence;
- preservation capability therefore remains `UNKNOWN` until independent scope evidence exists.

After a green live gate, the next commit can expose `FAST/BALANCED/DEEP` through `ChatGPTProductRuntime` and graduate only the capabilities directly supported by that evidence.
