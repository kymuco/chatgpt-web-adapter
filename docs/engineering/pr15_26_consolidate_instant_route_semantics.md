# PR15.26 — Consolidate Instant route semantics ownership

## Purpose

Continue #107 by removing the last source-order override of the Instant-mode network-route classifier.

Before this slice, `service_worker_instant_mode_pr8_8.js` defined
`_pr88InstantDeriveNetworkRoute`, then
`service_worker_instant_unified_route_semantics_pr8_8.js` reassigned it with the
graduated GPT-5.6 semantics.

That left one concept with two production owners.

## New ownership

The final unified GPT-5.6 semantics now live directly in:

```text
service_worker_instant_mode_pr8_8.js
```

The historical overlay worker is removed.

Production therefore has:

```text
one _pr88InstantDeriveNetworkRoute definition
zero _pr88InstantDeriveNetworkRoute assignments
```

## Preserved route semantics

Model identity and reasoning state remain separate evidence dimensions.

A model identifier such as:

```text
gpt-5-6-thinking
gpt-5-6-auto-thinking
```

does not by itself prove Medium/High reasoning.

Positive reasoning-route evidence remains fail-closed when an explicit
reasoning/thinking metadata key is observed without an explicit OFF state.

The graduated route status remains:

```text
UNIFIED_GPT_5_6_ROUTE_WITHOUT_EXPLICIT_REASONING
```

and legacy `noReasoningRouteProven` remains strict.

## Preserved boundaries

- no model-selection behavior changes;
- no composer behavior changes;
- no prompt/write behavior changes;
- raw prompt/response content remains outside route metadata;
- request/response hint collection is unchanged;
- downstream Python validation contract is unchanged.

## Acceptance

- historical unified-route worker absent from shipping runtime;
- one direct route-classifier definition in Instant-mode owner;
- zero route-classifier runtime reassignment;
- unified GPT-5.6 identity/reasoning separation preserved;
- dedicated route regression points at the actual owner;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
