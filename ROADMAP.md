# chatgpt-web-adapter Roadmap

_Last updated: 2026-09-02_

This is the current product roadmap for `chatgpt-web-adapter` (CWA). Historical PR8/PR9 planning documents remain in `docs/` as evidence and lineage; this file describes the current direction after CWA 0.3 and the completed PR10/PR11 milestones.

## Product role

CWA is a standalone local SDK / CLI / ChatGPT product bridge.

```text
ordinary ChatGPT product
          |
          v
chatgpt-web-adapter
 typed product runtime
          |
   +------+------+ 
   |             |
   v             v
 Python / CLI   downstream runtimes
               CMA / HDE / others
```

CWA owns product/session mechanics, canonical observation, product mutation, transport boundaries, capabilities, provenance, product-level observations, diagnostics, and the local browser bridge product surface.

CWA does **not** own project cognition, Git/workspace authority, autonomous continuation policy, or approval policy for external actions. Those remain downstream concerns.

## Completed generations

### CWA 0.2 — production text baseline

Released `v0.2.0` on 2026-08-22.

Established:

- `ChatGPTProductRuntime` as the forward-looking application boundary;
- browser-owned production text turns;
- canonical read/status/final readback;
- revision-safe streaming;
- model profiles;
- Temporary Chat;
- stable `cwa` CLI;
- snapshot/export artifacts and deterministic manifests;
- release-grade CI and installed-wheel validation.

### PR9 generation — CWA 0.3

Completed and released as `v0.3.0` on 2026-09-01.

```text
PR9.0  browser-owned v1 + standalone runtime contract
PR9.1  experimental browserless-request transport
PR9.2  images / files / multimodal continuation
PR9.3  search / tools / source / citation observations
PR9.4  0.3 stabilization and release
```

CWA 0.3 is the current public release baseline.

### PR10.0 — app/connector and required-action observation

Completed after 0.3.

Added stronger typed models for connector activity and required-action lifecycle while preserving the authority rule:

```text
product observation
!= product approval
!= connector authorization
!= external/local action authority
!= canonical finality
!= retry authority
```

Authenticated product evidence proved required-action point observation, but did not prove enough stable connector execution identity/correlation to graduate `tools_connectors` from `UNKNOWN`.

### PR10.1 — generated-artifact observation and handoff boundary

Completed and merged 2026-09-02.

The milestone established a bounded artifact observation model and investigated available product surfaces without exporting capability-bearing locator values.

Current frozen result:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

Actual generated-artifact download/materialization remains intentionally unimplemented. The research path stops rather than depending on minified React/update-queue internals as a public SDK contract.

### PR11.0 — browser bridge product surface

Completed after the public-readiness pass.

PR11.0 gives the unpacked Chrome bridge its own CWA identity and a bounded read-only product surface:

- CWA extension icon family and repository visual identity;
- concise manifest name/description;
- light/dark popup;
- local Native Messaging connection, runtime-tab presence and activity status;
- sanitized copyable diagnostics;
- toolbar ready/working/unavailable state;
- exact packaging/release validation for HTML/CSS/PNG extension assets.

The popup does not send ChatGPT turns, provision the runtime tab merely by opening, inspect ChatGPT page content, expose product ids/credentials, or gain retry/approval authority.

Chrome Web Store publication remains deferred; the current installation flow stays explicit and local (`Developer mode -> Load unpacked`).

See [`docs/browser_bridge_product_surface_pr11_0.md`](docs/browser_bridge_product_surface_pr11_0.md).

## Current checkpoint

Current `main` is a strong post-0.3 product-runtime baseline with coherent public documentation and a coherent local browser-bridge surface.

The immediate goal is no longer “discover one more hidden ChatGPT surface” or “polish one more repository page.” The next work should be driven primarily by real consumer needs and observed product drift.

## Next vertical milestone: consumer-driven runtime hardening

The preferred next product milestone is a real-consumer pass using CWA as a dependency from CMA, HDE, or another application without reaching into CWA internals.

The key question is:

```text
Can a real application use ChatGPTProductRuntime
without depending on browser/transport implementation details?
```

Candidate outcomes may include:

- ergonomics fixes in the public Python runtime;
- richer but still bounded observation consumption;
- continuation/cancellation improvements;
- clearer capability/provider composition;
- stable rich-input helpers if real consumers need them;
- compatibility-drift diagnostics based on actual failures;
- downstream migration guidance and version pinning.

Do not pre-commit to a feature merely because the ChatGPT UI contains it. A new surface should enter CWA when there is product evidence **and** a credible application need.

## Reopen conditions for conservative boundaries

### Connector execution lifecycle

Revisit stronger connector capability only if authenticated product evidence exposes stable connector execution identity/correlation without exporting credentials, private retrieved content, or arbitrary connector payloads.

Until then:

```text
tools_connectors = UNKNOWN
```

### Generated-artifact download

Reopen only after both are proven:

1. a stable product-owned artifact/file/asset identity;
2. a safe browser-owned resolution path that keeps locator/capability material private.

Any future handoff must also preserve explicit caller destination/overwrite authority, exact final byte identity, no automatic retry/fallback, and no effect on canonical turn finality.

### Browserless production promotion

`browserless-request` remains `EXPERIMENTAL` until long-term evidence supports a stronger claim. Passing on one product revision is insufficient.

CWA will not add challenge-bypass machinery merely to make browserless writes appear reliable.

### Chrome Web Store distribution

Consider store publication only when external adoption justifies the additional distribution contract. Before reopening, review:

- `debugger` permission policy/review expectations;
- privacy disclosures;
- extension version/update lifecycle;
- support burden for externally installed bridge versions;
- whether store distribution materially improves the actual CWA consumer workflow.

Do not publish merely to remove the visual “unpacked/developer” label from a local development install.

## Compatibility-drift hardening

ChatGPT Web is an undocumented changing product surface. Drift work should be triggered by concrete evidence:

- a previously proven product path fails;
- schemas/DOM/request behavior change;
- canonical finality or identity assumptions stop holding;
- browser/extension behavior changes materially;
- a release or consumer exposes a reproducible compatibility regression.

Preferred response:

```text
observe failure
-> characterize narrowly
-> repair public contract if justified
-> deterministic regression
-> bounded live validation
-> document the new boundary
```

Avoid open-ended reverse engineering after the decision-relevant boundary is already known.

## Release direction

Do not cut a new major/minor release for repository/product-surface polish alone.

A likely release policy is:

- `0.3.x` for compatible fixes, drift repairs, documentation/packaging/product-surface hardening, and narrow ergonomics improvements;
- `0.4.0` when a coherent new product/consumer capability set materially expands the public runtime contract.

Every release continues to require Linux/Windows validation, exact built-artifact checks, installed-wheel smoke, explicit support/capability documentation, and tag/version/changelog agreement.

## Architectural invariants

1. CWA remains standalone; CMA/HDE are consumers, not owners of its roadmap.
2. Ordinary ChatGPT product semantics remain first-class.
3. Canonical observation and product mutation are separate planes.
4. Transport selection is explicit; there is no silent fallback.
5. Ambiguous writes are never automatically retried.
6. Streaming and structured observations are not canonical finality.
7. Provenance is observed rather than synthesized.
8. Capability state remains evidence-backed and provider-aware.
9. Observation never becomes approval or downstream authority by implication.
10. Browser internals remain below the public runtime boundary.
11. Research/diagnostic surfaces do not become public production contracts merely because they exist in-tree.
12. Product chrome may expose local sanitized bridge state, but opening the UI never grants ChatGPT product-write/finality authority.
13. No challenge-bypass expansion.
14. Product drift fails clearly rather than pretending permanence.

## Non-goals

CWA is not becoming:

- a full chat application or TUI;
- a general agent/orchestrator;
- HDE/CMA project memory or policy;
- a Git/filesystem authority layer;
- a caller-controlled abstraction over every internal ChatGPT tool;
- a browser-protection bypass toolkit;
- an unstable DOM/React scraper presented as a stable SDK;
- a Chrome Web Store product before distribution is justified by real adoption.

## Historical maps

Useful lineage documents:

- [`docs/post_pr8_daily_use_product_bridge_direction.md`](docs/post_pr8_daily_use_product_bridge_direction.md) — detailed PR8-era direction;
- [`docs/post_0_3_product_generation.md`](docs/post_0_3_product_generation.md) — PR10.0 working contract and post-0.3 planning context;
- [`docs/browserless_request_transport_pr9_1.md`](docs/browserless_request_transport_pr9_1.md) — browserless experimental boundary;
- [`docs/product_rich_input_pr9_2.md`](docs/product_rich_input_pr9_2.md) — rich-input evidence;
- [`docs/product_runtime_observation_integration_pr9_3.md`](docs/product_runtime_observation_integration_pr9_3.md) — structured observation integration;
- [`docs/generated_artifact_handoff_pr10_1.md`](docs/generated_artifact_handoff_pr10_1.md) — artifact handoff closure;
- [`docs/browser_bridge_product_surface_pr11_0.md`](docs/browser_bridge_product_surface_pr11_0.md) — browser bridge product-surface contract.

Use [`docs/README.md`](docs/README.md) for the complete documentation map.
