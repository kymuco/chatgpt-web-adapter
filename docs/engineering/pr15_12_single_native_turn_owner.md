# PR15.12 — Single native-turn runtime owner

## Goal

Close the import-order native-turn ownership problem completely.

Before this change, PR15 had already consolidated large historical clusters, but
seven active modules still reassigned `executeNativeTurn` at different import
boundaries. Four were explicit PR15 cluster owners and three were older runtime
wrappers.

## Final active chain

The effective pre-PR15.12 outer-to-inner order was:

```text
ordinary-text identity
→ rich-input lifecycle
→ Browser Authority lease
→ Temporary lifecycle
→ response lifecycle
→ selection lifecycle
→ stale-UI recovery
→ base native turn
```

PR15.12 preserves that exact order explicitly.

## Architecture

Each domain now exposes a pure `(message, next)` native-turn layer.

`service_worker_native_turn_lifecycle.js` is imported last by
`service_worker_runtime.js` and is the only active runtime module that captures
and reassigns `executeNativeTurn`. Loading it after the read and observation
domains is safe because those domains no longer capture or reassign the native
turn function.

This makes native-turn composition independent of incidental import-order
monkeypatching while keeping lower-level page-turn, submit, Browser Authority,
streaming, Temporary, rich-input, and identity hooks in their established domain
modules. Domain modules still load at their historical boundaries; only the
native-turn call graph is assembled once at the runtime root.

## Preserved semantics

No layer changes its internal behavior. In particular, the change preserves:

- ordinary request-bound conversation identity authority;
- rich-input staging, submit, and committed identity semantics;
- Browser Authority lease storage and release behavior;
- Temporary prewrite proof and lifecycle authority;
- response streaming/finality behavior;
- Instant/model selection and phase timing behavior;
- stale-UI recovery and runtime reload metadata;
- retry and canonical-finality boundaries.
