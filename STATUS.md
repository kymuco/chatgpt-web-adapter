# Project Status

_Last updated: 2026-10-08_

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
current phase           PR17.2 merged; canonical checkpoint / release hygiene
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
Gemini Notebook Web    EXPERIMENTAL add_url_source + background Audio Overview lifecycle
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

The general ChatGPT artifact-download handoff remains frozen:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

The later **Gemini Notebook-specific** private retrieval proofs do not change
that ChatGPT boundary or create caller-facing download/publication authority.
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

The canonical post-release sequence now includes:

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
      → PR16.4 Notebook durable URL-source admission
      → PR16.5 Audio background generate/observe
      → PR16.6-16.8 private Audio/Video retrieval and consolidation
PR17  ChatGPT product/runtime repair
      → PR17.1 composer/submit drift repair
      → PR17.2 background reasoning/submit; durable conversation-local reasoning evidence
```

The detailed PR15 lineage remains preserved in `docs/engineering/`.

## Current checkpoint

Canonical `main` baseline after PR17.2: `02b56911ae132d91d35d8bb87511141351968f80`.
GitHub Actions push CI #1945 passed on this exact revision. It is newer than
published `v0.3.0`: source support must not be inferred for the released wheel.

PR16.5-PR16.8 closed the Gemini Notebook asynchronous Audio lifecycle and
independent Video lifecycle proof. Audio generation/observation remains
experimental/module-only. Audio/Video retrieval and their shared browser
byte-acquisition, temporary staging and orchestration are **private only**.
No public Video generation API, `HostedArtifactLifecycle`, registry/factory,
universal schema or filesystem publication authority was introduced.

PR17.1 and PR17.2 fixed ordinary ChatGPT composer/submit readiness and
background reasoning selection without foreground tab activation. The
shipping selector remains the three-state `0..2` slider, controlled with
background CDP focus emulation and strictly proven before each explicit turn:

```text
FAST     → INSTANT (0)
BALANCED → MEDIUM  (1)
DEEP     → HIGH    (2)
MAX      → unmapped
```

The Phase C bounded live test proved existing-chat reasoning preservation as
`CONVERSATION_LOCAL_DURABLE` across fresh renderers. New-chat default behavior
was `LAST_SELECTED_MODE_OBSERVED`; model preservation remains `UNKNOWN`.
Reasoning preservation is observational and **never** permission to skip
the `TURN_REQUIREMENT` strict prewrite proof.

Full evidence and boundaries:
[PR16/PR17.2 canonical product checkpoint](docs/engineering/pr17_2_canonical_product_checkpoint.md).
Older engineering documents remain historical evidence rather than overriding
this current product-status summary.

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

## Next experimental direction (not shipping)

The persistent-workspace URL-source admission experiment (PR16.4) and Audio
Overview generation/observation (PR16.5) are closed, module-only experimental
proofs. PR16.6-16.8 retained private artifact internals rather than publishing
a generic lifecycle.

A possible subsequent, independently gated **Capability Capture v0**
research experiment may demonstrate one existing Google Translate action,
capture bounded semantic evidence, derive a private spec and replay through
the already-proven browser-owned runtime. No Studio, registry, product
driver marketplace, direct-request compiler or public capability factory
is claimed by this checkpoint.

## Release policy

Documentation/product-surface polish alone does not justify a new minor release.

Likely rule:

- `0.3.x` for compatible fixes, drift repairs, documentation, packaging and bounded
  ergonomics;
- `0.4.0` for a coherent new public runtime capability generation.

Release gates remain Linux/Windows CI, build-artifact validation, installed-wheel
smoke and tag/version/changelog agreement.
