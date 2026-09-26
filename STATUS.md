# Project Status

_Last updated: 2026-09-26_

This is the compact current-state view for `chatgpt-web-adapter` (CWA).

Use [`ROADMAP.md`](ROADMAP.md) for direction,
[`README.md`](README.md) for the project overview, and
[`docs/README.md`](docs/README.md) for the documentation map.

## Release and branch state

```text
latest public release   v0.3.0
release date            2026-09-01
package version         0.3.0
current main            post-0.3 development
architecture            PR15 provider architecture frozen
current phase           PR16.3 adoption/discoverability foundation
license                 MIT
python                  3.10-3.14
```

Current `main` contains substantial product/runtime work newer than the `v0.3.0`
tag. Do not assume every current-main behavior exists in the published 0.3.0 wheel.

## Product role

CWA is a standalone local product-runtime bridge for authenticated consumer AI web
products.

Current provider/capability status:

```text
ChatGPT               PRODUCTION / default conversational runtime
DeepSeek Web          EXPERIMENTAL conversational runtime
Gemini Web            EXPERIMENTAL conversational runtime
Google Translate Web  EXPERIMENTAL non-chat translate_text capability
```

The shared provider-neutral architecture is represented by
`ProductProviderBoundary schema 2`, but that boundary is metadata/invariant validation
over a runtime, not an execution router.

## ChatGPT production/default surface

Primary application boundary:

```text
ChatGPTProductRuntime
```

Production mutation transport:

```text
browser-owned = PRODUCTION
```

Alternative direct-request transport:

```text
browserless-request = EXPERIMENTAL
```

Evidence-backed ChatGPT production capabilities include:

- text new chat and continuation;
- canonical conversation attach/read/status/final readback;
- revision-safe streaming/finality;
- model/reasoning profiles;
- Temporary Chat text turns;
- image and general-file input;
- multimodal continuation;
- web-search observation;
- immutable structured search/tool/source/citation/required-action observations;
- runtime health/capability/provenance reporting;
- stable CLI send/status/messages/snapshot/export/doctor surfaces.

Historical compatibility surface:

```text
ChatGPTWebClient / WebChatClient = COMPATIBILITY
```

## Experimental providers on current main

### DeepSeek Web

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
finality           PAGE_DOM_STABLE_COMPLETION (noncanonical)
```

### Gemini Web

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
finality           PAGE_DOM_STABLE_COMPLETION (noncanonical)
```

Both concrete runtimes remain module-only and are not root production exports.

See [`docs/providers.md`](docs/providers.md).

## Browser-owned strategy

Browser-owned execution is the reference/default web-product mutation strategy.

The browser owns the authenticated product environment, frontend execution, normal
navigation and page-owned submit behavior. CWA owns the bounded runtime operation and
its evidence/reconciliation rules.

Avoiding Chrome is not, by itself, a reliability improvement.

See [`docs/browser_owned.md`](docs/browser_owned.md).

## Conservative / incomplete boundaries

### Tools and connectors

```text
tools_connectors = UNKNOWN
```

CWA can observe bounded product-tool and required-action evidence on proven ChatGPT
paths, but current evidence does not justify a general connector execution contract.

### Generated artifacts

Current frozen handoff status:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

CWA does not synthesize artifact identity from filename, DOM order, assistant prose,
URL similarity or minified frontend internals.

### Browserless writes

`browserless-request` remains experimental and fail-closed around unsupported product
protection/challenge boundaries.

CWA does not add challenge-bypass machinery merely to promote browserless writes.

## Authority invariants

```text
product observation
!= product approval
!= connector authorization
!= product write authority
!= retry authority
!= canonical finality
!= filesystem/Git/workspace authority
```

```text
incremental output
!= canonical finality
```

```text
ambiguous write
→ reconciliation
→ no automatic retry
```

For page-owned providers, uncertainty after the click-capable submit operation may
have executed is reconciliation-required.

## Completed post-0.3 architecture work

The major post-release sequence is now:

```text
PR10  connector / required-action + artifact boundaries
PR11  browser bridge product surface
PR12-14 runtime hardening / authority / failure semantics
PR15  architecture reset + provider-neutral boundary
      → ChatGPT consolidation
      → DeepSeek live proof
      → neutrality audit
      → Gemini live proof
      → provider architecture freeze
PR16  public positioning/documentation alignment
      → naming deliberately deferred
      → PR16.2 non-chat hosted-capability falsification spike
```

The detailed PR15 lineage remains preserved in `docs/engineering/`.

## Current checkpoint

The technical chat-provider architecture remains frozen.

PR16.2 is closed with the first live-proven non-chat capability:

```text
Google Translate Web
→ translate_text
→ EXPERIMENTAL / module-only
→ no conversation id
→ no ProductWriteTransport
→ no ProductProviderBoundary claim
→ PAGE_DOM_STABLE_TRANSLATION
```

The experiment proved that CWA's lower browser bridge, authority lane and ambiguity
discipline can support at least one hosted capability outside conversation semantics.

It did **not** establish a generic hosted-capability runtime or registry. Future
generalization remains evidence-driven.

## Adoption and discovery

PR16.3 is a docs/metadata/community slice. It does not change runtime behavior.

The current goal is to make the proven project surface legible to:

- first-time users;
- Python application developers;
- local assistants / coding agents;
- future capability contributors;
- machine/LLM discovery.

New discovery surfaces include `docs/quickstart.md`, `docs/capabilities.md`,
`docs/agent_integration.md`, `docs/adding_capability.md`, and repository-root
`llms.txt`.

A dedicated MCP adapter remains a future integration layer, not a current support
claim.

## Release policy

Documentation/product-surface polish alone does not justify a new minor release.

Likely rule:

- `0.3.x` for compatible fixes, drift repairs, documentation, packaging and bounded
  ergonomics;
- `0.4.0` for a coherent new public runtime capability generation.

Release gates remain Linux/Windows CI, build-artifact validation, installed-wheel
smoke and tag/version/changelog agreement.
