# PR15.30 — Consolidate Native Messaging routing ownership

## Purpose

Continue #107 by removing the remaining source-order ownership chain around
`onNativeMessage`.

Before this slice, four shipping layers captured and reassigned the same hook:

```text
service_worker_product_surface_pr11_0.js
service_worker_runtime_tab_reconciliation.js
service_worker_canonical_read_v2.js
service_worker_ui_liveness.js
```

Given the production import graph, the effective outer-to-inner call path was:

```text
UI liveness
→ canonical read v2
→ release_runtime_tab
→ product action-state
→ base turn handler
```

## New ownership

The base turn handler in `service_worker.js` is now private:

```text
_cwaBaseOnNativeMessage(message, port)
```

The historical owners expose explicit helpers:

```text
_cwaOnNativeMessageWithProductState(message, port, next)
_pr88OnNativeMessageWithBrowserAuthorityLease(message, port, next)
_cwaOnNativeMessageWithCanonicalRead(message, port, next)
_cwaOnNativeMessageWithUiLiveness(message, port, next)
```

The single public owner is:

```text
service_worker_native_message_router.js
```

with explicit composition:

```text
ui(canonical(release(product(base))))
```

## Preserved routing semantics

### Base turn handler

The base handler still accepts only protocol-valid `turn` messages, owns the
shared `activeRequestId` busy lane for ordinary turns, dispatches through the
native-turn runtime, and emits the same `turn_result` success/failure shapes.

### Product action-state

The product layer remains immediately around the base turn handler.

This ordering is significant. Historically:

- ordinary turns pass through product state and update the action badge/title;
- `release_runtime_tab` is intercepted by the outer release layer;
- `canonical_read` is intercepted by the outer canonical layer;
- `ui_liveness` is intercepted by the outer liveness layer.

Therefore read/control messages do not newly acquire product busy-state side
effects in PR15.30.

The existing microtask update after synchronous `activeRequestId` acquisition,
plus the final action-state update after the base promise settles, are unchanged.

### Browser Authority release

`release_runtime_tab` remains owned by the Browser Authority layer. Protocol,
request-id validation, shared busy-lane exclusion, lease checks, release result
shape, and `activeRequestId` cleanup are unchanged.

### Canonical read v2

`canonical_read` remains owned by canonical-read v2. It preserves the shared
busy lane, authenticated browser-context fetch, pagination/throttle behavior,
chunked SHA-256-sealed transfer, sanitized errors, and release-bound lease
metadata.

### UI liveness

`ui_liveness` remains the outermost route. It still rejects write-bearing
fields, serializes non-liveness messages behind an active liveness probe, and
grants no write/retry/finality authority.

That serialization remains outside canonical/release/product/base exactly as
before.

## Assembly

The owner is loaded immediately after `service_worker_runtime_observation.js`.

At that point:

- product-state helper exists via the observability/product surface path;
- Browser Authority release helper exists from runtime-tab reconciliation;
- canonical-read helper exists from the read domain;
- UI-liveness helper exists from the observation domain.

The Native Messaging listener in the base worker invokes `onNativeMessage`
through a closure on each received message, so installing the final owner after
the helper modules preserves the live dispatch path.

## Static target

```text
onNativeMessage public definitions = 1
onNativeMessage runtime assignments = 0
PriorOnNativeMessage aliases        = 0
```

The retired `service_worker_canonical_read.js` historical source is not part of
the shipping runtime and is intentionally outside this production-owner slice.

## Regression strategy

PR15.30 adds an executable Node composition regression proving:

```text
enter UI
→ enter canonical
→ enter release
→ enter product
→ base
→ exit product
→ exit release
→ exit canonical
→ exit UI
```

Existing canonical-read, Browser Authority, product-surface, and UI-liveness
behavioral tests continue to own their domain semantics.

## Non-goals

This slice does not consolidate `connectNativeBridge`. Product surface still has
a separate bridge-connection wrapper; that is a distinct ownership problem and
should be evaluated independently after the native-message router is closed.

## Acceptance

- exactly one public `onNativeMessage` owner in shipping production;
- zero runtime assignments of `onNativeMessage` in active layers;
- zero shipping `PriorOnNativeMessage` aliases;
- exact historical outer-to-inner routing preserved;
- product-state side effects remain ordinary-turn scoped;
- canonical, release, and liveness authority semantics unchanged;
- engineering quality and JavaScript syntax green;
- full Linux/Windows Python 3.10–3.14 matrix green;
- release build and installed-wheel smoke green.
