# PR15.22 — Consolidate product-message observation ownership

## Purpose

Continue #107 by removing the source-order wrapper chain on `_pr812InspectMessage`.

Before this slice, production loaded three independent observation workers:

```text
service_worker_connector_lifecycle_pr10_0.js
service_worker_connector_router_characterization_pr10_0.js
service_worker_generated_artifact_pr10_1.js
```

Each worker captured the current `_pr812InspectMessage` and reassigned it. The effective historical call order was:

```text
generated artifact
→ connector router
→ connector lifecycle
→ PR8.12 base message inspection
```

## New production owner

Production now loads one worker:

```text
service_worker_product_observation.js
```

The three observation behaviors are explicit layers:

```text
_pr101GeneratedArtifactInspectMessageLayer
_pr100RouterInspectMessageLayer
_pr100ConnectorInspectMessageLayer
```

and one owner composes them in the historical order before installing the hook once:

```text
_pr812InspectMessage = _pr10ProductInspectMessageOwner
```

## Preserved semantics

Connector lifecycle evidence still:

- requires explicit connector/app/plugin identity;
- does not infer connector identity from generic tool activity;
- treats a message id as point evidence only, not fabricated cross-message pairing;
- requires both explicit required-action id and type;
- never exports raw metadata, arguments, results, credentials, URLs, cookies, or authorization material.

Connector-router characterization still:

- applies only to `api_tool.call_tool`;
- traverses only bounded whitelisted envelope structure;
- blocks argument/result/content scopes from identifier extraction;
- emits bounded structural evidence and safe identifier candidates only.

Generated-artifact observation still:

- requires an explicit product-owned artifact/file/asset id;
- never invents identity from filename, URL, message order, DOM position, or assistant text;
- treats a download locator only as an internal boolean;
- never exports locator values.

All three layers remain evidence-only and catch their own observation failures after the lower layer has executed.

## Preserved boundaries

- PR8.12 response activity remains the upstream message-inspection owner;
- connector support diagnostics remain separate no-write handlers;
- PR8.13 Temporary remains outside this owner;
- no product-write, retry, canonical-finality, or Browser Authority semantics change.

## Acceptance

- shipping product-message observation workers reduce from three to one;
- `_pr812InspectMessage` is installed exactly once by this product-observation owner;
- historical layer order is explicit and regression-tested;
- old three observation imports/files are absent;
- connector, router, and generated-artifact safety contracts remain covered;
- engineering quality + JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build + installed-wheel smoke pass.

Tracking: #107
