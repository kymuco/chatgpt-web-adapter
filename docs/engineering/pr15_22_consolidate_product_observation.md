# PR15.22 — Consolidate product observation ownership

## Purpose

Continue #107 by removing source-order monkeypatching from shipping product observations.

Before this slice, three workers wrapped the PR8.12 message inspector:

```text
service_worker_connector_lifecycle_pr10_0.js
service_worker_connector_router_characterization_pr10_0.js
service_worker_generated_artifact_pr10_1.js
```

Because each worker captured and reassigned `_pr812InspectMessage`, production behavior depended on import order.

## Historical side-effect order

Although generated-artifact observation was the outermost final wrapper, each overlay called its prior function first. The actual observation sequence was:

```text
PR8.12 base inspection
→ connector lifecycle observation
→ connector router characterization
→ generated artifact observation
```

PR15.22 preserves this exact order explicitly.

## New production owner

Production now loads one module:

```text
service_worker_product_observation.js
```

It captures PR8.12 once and performs one final install:

```text
_pr10ProductObservationUpstreamInspectMessage = _pr812InspectMessage
_pr812InspectMessage = _pr10ProductObservationInspectMessage
```

The owner then calls:

```text
upstream PR8.12
→ _pr100InspectMessage
→ _pr100RouterInspect
→ _pr101InspectMessage
```

Each optional observation remains isolated by its own fail-open `try/catch`.

## Preserved safety boundaries

- connector identity still requires explicit connector/app/plugin metadata;
- generic tool activity is not promoted to connector lifecycle;
- router characterization remains scoped to `api_tool.call_tool`;
- raw connector arguments/results/content are not exported;
- artifact identity still requires explicit product-owned artifact/file/asset id;
- locator values remain internal-only signals;
- all three observation families remain non-authoritative and may never perturb a product turn;
- no write authority or retry semantics change.

## Acceptance

- one shipping product-observation owner replaces three workers;
- one install of `_pr812InspectMessage`;
- zero retired prior-function aliases;
- old three worker imports are absent;
- historical side-effect order is explicit and regression-tested;
- connector/router/artifact observation contracts remain unchanged;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107


## Follow-up ownership note

PR15.34 later lifts the final public `_pr812InspectMessage` installation into the
explicit cross-layer message-inspection owner. PR15.22 remains the owner of the
connector/router/artifact observation stage itself, but no longer installs the
shared public inspector name.
