# PR15.18 — Consolidate Instant-effort production ownership

## Purpose

Continue #107 by collapsing the shipping PR8.8 Instant reasoning-effort chain into one explicit production owner.

Before this slice, one capability was spread across seven source-ordered workers:

```text
service_worker_instant_effort_slider_contract_pr8_8.js
service_worker_instant_effort_slider_key_pr8_8.js
service_worker_instant_effort_slider_selection_pr8_8.js
service_worker_instant_effort_activation_hardening_pr8_8.js
service_worker_instant_effort_dom_activation_pr8_8.js
service_worker_instant_effort_transient_foreground_pr8_8.js
service_worker_instant_effort_slider_support_pr8_8.js
```

The chain also reassigned `_pr88SelectionEnsureInstant` and `_pr88SelectionRecord` after earlier owners had already defined them.

## New owner

Production observability now loads:

```text
service_worker_instant_effort_selection.js
```

This owner contains the semantic slider contract, Home-key selection, DOM trigger actuation, relaxed slider resolution, transient foreground handling, foreground restoration, and the read-only support diagnostic.

The production path is explicit:

```text
locateAndFocusComposer
→ _pr88SelectionEnsureInstant
→ transient foreground only when required
→ _pr88SelectionEnsureInstantCore
→ proven current-effort control
→ proven 0..2 slider
→ focus slider
→ Home
→ selected INSTANT proof
→ restore prior active tab
→ composer focus / prompt insertion
```

## Removed composition

The seven historical Instant-effort worker files are deleted from the shipping extension.

The new owner does not perform runtime reassignment of:

```text
_pr88SelectionEnsureInstant
_pr88SelectionRecord
_pr88InstantEffortOpenPickerWithFallback
```

The superseded option-click implementation of `_pr88SelectionEnsureInstant` was also removed from the base Instant-selection repair. The base layer retains shared selection identity, network-boundary observation, persistence, and the pre-input hook.

Selection-record effort fields are now produced directly by the base selection record rather than by a later wrapper.

## Preserved behavior

This is an ownership migration, not a product-capability change.

Preserved invariants:

- required model mode remains `INSTANT`;
- no prompt insertion before selection completes;
- no automatic retry;
- current model mode must be proven;
- the reasoning-effort slider must prove the exact discrete range `0..2`;
- the slider must be focusable;
- selection uses semantic `Home`;
- selected `INSTANT` must be proven after mutation;
- unexpected conversation writes during selection remain fatal;
- fresh inactive runtime tabs may receive one bounded transient foreground window;
- the previously active tab is restored in `finally`;
- Advanced/model controls remain forbidden;
- canonical response/finality behavior is unchanged.

## Acceptance

- production imports exactly one Instant-effort owner;
- the seven historical PR8.8 Instant-effort workers are absent;
- `_pr88SelectionEnsureInstant` has one active definition and no runtime reassignment;
- `_pr88SelectionRecord` is not wrapped by the Instant-effort layer;
- regression tests bind to the explicit owner rather than source-order fragments;
- engineering quality and JavaScript syntax checks pass;
- full Linux/Windows Python matrix passes;
- release build and exact installed-wheel smoke pass.

Tracking: #107
