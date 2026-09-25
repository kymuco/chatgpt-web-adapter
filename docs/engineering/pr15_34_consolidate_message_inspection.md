# PR15.34 — Consolidate message-inspection ownership

## Purpose

Continue #107 by removing the remaining source-order replacement chain around
`_pr812InspectMessage`.

The exact shipping order before this slice was:

```text
PR8.12 response-activity base inspector
→ PR15.22 product observation
→ PR9.3 structured source/citation observation
```

PR15.22 already consolidated connector lifecycle, connector-router, and artifact
observation into one product-observation stage. The later read-domain source/citation
overlay still captured and reassigned the same public inspector name, so final
ownership still depended on startup order across domains.

## New ownership

The three stages are now explicit helpers:

```text
_pr812BaseInspectMessage(...)
_pr10ProductObservationInspectMessage(...)
_pr93InspectMessage(...)
```

The sole public production owner is:

```text
service_worker_message_inspection.js
```

It composes the historical side-effect order directly:

```text
_pr812InspectMessage(...)
→ _pr812BaseInspectMessage(...)
→ _pr10ProductObservationInspectMessage(...)
→ _pr93InspectMessage(...)
```

## Why direct composition is correct

Both historical overlays invoked their prior inspector first and then added their own
observation side effects. Therefore the effective order was base, product observation,
then source/citation observation.

All modules are loaded synchronously during service-worker startup before event
dispatch. The final owner is installed in the read-domain after the source/citation
helper is available and before canonical-read assembly continues.

Existing response-activity consumers continue to resolve `_pr812InspectMessage`
dynamically at call time.

## Preserved semantics

PR15.34 changes ownership only.

The base stage still owns normalized reasoning, browsing, tool/activity, and patch
message inspection. PR15.22 still owns connector lifecycle, connector-router, and
generated-artifact observations with independent fail-open isolation. PR9.3 still owns
bounded structured source/citation extraction, deduplication, sensitive-URL rejection,
private-thought suppression, and source/citation relationship emission.

No write, submit, retry, navigation, canonical-finality, connector authorization, or
artifact materialization authority is added.

## Assembly

```text
service_worker_product_source_citations_pr9_3.js
→ service_worker_message_inspection.js
→ service_worker_canonical_read_v2.js
```

The PR8.12 base and PR15.22 product-observation helpers are already loaded by the
earlier observability assembly.

## Static target

```text
_pr812InspectMessage public definitions = 1
_pr812InspectMessage runtime assignments = 0
PriorInspectMessage aliases              = 0
UpstreamInspectMessage aliases           = 0
```

## Regression strategy

PR15.34 verifies:

- one public message-inspection owner;
- zero runtime reassignments in product/source layers;
- explicit base/product/source helpers;
- exact base → product → source side-effect order;
- read-domain owner placement before canonical read;
- exactly-once delegation with unchanged arguments;
- response-activity consumers still resolve the public inspector dynamically;
- source/citation fixtures invoke the explicit PR9.3 helper directly.

Tracking: #107
