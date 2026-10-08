# Canonical checkpoint — PR16 closure and PR17.2 background runtime

Status: DOCUMENTATION CHECKPOINT ONLY (2026-10-08).
Baseline: `main@02b56911ae132d91d35d8bb87511141351968f80`.

This document records the observed/merged state of the repository. It is not
a new runtime proof, release, public API commitment, or permission to retry
product writes. Always inspect the installed extension/runtime revision before
claiming that a local installation matches this source baseline.

## Release versus source

- Published release: `v0.3.0` (2026-09-01), package `0.3.0`.
- The current development `main` contains substantial unreleased work.
- The exact merged source head passed GitHub Actions push CI #1945.
- CI validates this source revision; it does **not** prove the installed
  `v0.3.0` wheel includes the post-release capabilities.
- Before any release, verify built wheel and browser extra for the supported
  Python/platform matrix (tracking #171), and typed package metadata (#172).

## PR16 generated-artifact closure

| Slice | Closure | Support boundary |
| --- | --- | --- |
| PR16.5 | Gemini Notebook Audio Overview generate/observe | Experimental module-only; asynchronous acceptance followed by separate same-ref, reload-verified observation |
| PR16.6 (#190) | Audio artifact retrieval | Private exact-ref byte retrieval only |
| PR16.7 (#192) | Independent Video generated-artifact lifecycle proof | Private Video generation, observation and retrieval; not a public Video API |
| PR16.8 (#194) | Shared browser byte acquisition, staging/integrity and Python orchestration | Private consolidation only |

The prior ChatGPT generated-artifact download handoff remains unsupported
without its own stable product identity and authorization contract. The
Notebook-specific private retrieval proof does **not** grant callers a generic
download API, raw signed locator export, filesystem publication, registry,
or `HostedArtifactLifecycle` abstraction.

## PR17 background ChatGPT closure

- PR17.1 (#196): composer/profile readiness and protected submit drift repair.
- PR17.2 shipping (#198): inactive tab reasoning selection and background
  ordinary-text Enter commit; exact `0..2` slider remains the shipping product
  selector (not direct `Instant/Medium/High` option clicking).
- PR17.2 Phase C (#199): separately established reasoning preservation scope.

At shipping runtime revision `PR17_2_BACKGROUND_PRODUCTION_R12`:

```text
FAST     -> INSTANT -> 0
BALANCED -> MEDIUM  -> 1
DEEP     -> HIGH    -> 2
MAX      -> unmapped / unsupported
```

Evidence:

- Fresh `active:false` runtime tab: no tab/window foreground activation
  during proven selection and ordinary-text commit.
- One 24,033-character `DEEP` background submission: write observed,
  canonical completion, no automatic write retry.
- Three-profile shipping E2E: 3/3 protected writes and canonical completions.
- Separate A/B/new-chat Phase C: 3/3 writes and seven read-only observations;
  fresh-renderer A/B modes independently rehydrated.

```text
model_selection          = AVAILABLE
reasoning_selection      = AVAILABLE
model_preservation       = UNKNOWN
reasoning_preservation   = AVAILABLE
reasoning_scope          = CONVERSATION_LOCAL_DURABLE
new_chat_default         = LAST_SELECTED_MODE_OBSERVED
scope_is_write_authority = false
```

Preservation is observational, not mutation authority. Every explicit
`FAST/BALANCED/DEEP` request remains a per-turn `TURN_REQUIREMENT` and must pass
strict prewrite mode proof. The canonical read/lease-before-write ordering,
no-automatic-retry-after-ambiguity, and noncanonical-versus-canonical finality
distinctions remain unchanged. No backend persistence mechanism is inferred.

Source records:

- [PR17.2 selection/submit evidence](pr17_2_background_reasoning_selection.md)
- [PR17.2 Phase C scope evidence](pr17_2_reasoning_scope_phase_c.md)
- [PR16.8 private artifact stop line](pr16_8_internal_artifact_primitive_consolidation.md)

## Next work is intentionally separate

1. Maintain/release what exists: accurate support docs, installed-wheel
   reproducibility, deadline-bound browser 429 recovery (#168), and
   contributor-owned snapshot/export race review (#177 / #169).
2. Explore `Capability Capture v0` on a separate research branch, **not**
   as a shipping generic provider/runtime abstraction. Start with one
   bounded Google Translate demonstration, an annotated semantic trace,
   and browser-owned replay equivalence against the hand-written reference.
3. Only if independent product cases reproduce semantics and
   write/finality/reconciliation invariants should compiler/Studio/registry
   productization be considered.

The current repository/distribution/import/CLI names remain unchanged.
