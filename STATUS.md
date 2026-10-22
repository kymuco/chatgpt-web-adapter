# Project Status

_Last updated: 2026-10-22_

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
current phase           Qwen Web SDK + opt-in ChatGPT HTTP integrated on main
license                 MIT
python                  3.10-3.14
```

Current `main` includes #213-#216 (Qwen/docs) and #212 (direct ChatGPT HTTP),
merged on 2026-10-16 as `2c4a0215c5d3`. CI passed 16/16 jobs on that exact
commit. The newest published package remains `v0.3.0` from 2026-09-01; **do not**
assume these source capabilities ship in that published wheel.

## Product role

CWA is a standalone local product-runtime bridge for authenticated consumer AI web
products.

Current provider/capability status:

```text
ChatGPT               PRODUCTION / default conversational runtime
DeepSeek Web          EXPERIMENTAL conversational runtime
Gemini Web            EXPERIMENTAL conversational runtime
Qwen Web              EXPERIMENTAL isolated Chrome/Native Host SDK
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

Alternative direct-request transports (two distinct implementations):

```text
browserless-request = EXPERIMENTAL (historical runtime transport)
BrowserlessHTTPClient = EXPERIMENTAL / explicit opt-in direct HTTP SDK (#212)
```

The direct HTTP client uses a saved authenticated session, Node.js 24+ and curl;
it does not start a tab or silently fall back to the browser-owned runtime. One
user-run Codexia bootstrap proved three Markdown attachments, GPT-6 High
requested/extended observed, streaming and exact assistant-message readback.
The resulting `CAPTURED_UNADMITTED` is transport evidence, **not** Codexia Work
completion or a general stability claim. See
[`docs/browserless_http_sdk.md`](docs/browserless_http_sdk.md).

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

Both DeepSeek/Gemini concrete runtimes remain module-only and are not root production exports.

### Qwen Web

The Qwen provider uses a separate Chrome extension and native host. **User-run
installed Windows SDK evidence** confirms new chat, multi-turn text, network-SSE
answer delivery and cross-process `--chat` reattachment. Explicit `/retry` handles
a *confirmed* high-demand/Regenerate state; it never automatically resends a
possibly accepted prompt. Direct HTTP, canonical durable readback and advanced
rich-input/model features are **not** production claims.

The regular ChatGPT/HDE extension, host and bridge remain separate. The source
and reference examples are in [`docs/qwen.md`](docs/qwen.md).

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

Historical canonical `main` baseline after PR17.2 (not the current branch tip): `02b56911ae132d91d35d8bb87511141351968f80`.
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

## Release readiness checkpoint (2026-10-22)

- **No new public release yet.** `v0.3.0` remains the published package;
  a new version/tag is a separate release decision.
- **Linux PR [#217](https://github.com/kymuco/chatgpt-web-adapter/pull/217)**
  has 16/16 green CI but remains Draft pending a real
  EndeavourOS Chrome/Chromium + Qwen Native Messaging E2E.
- **Browser-extra CI [#218](https://github.com/kymuco/chatgpt-web-adapter/pull/218)**
  was merged as `3caa50b96aff` after 16/16 green CI. The installed-wheel
  release/publish smoke now installs the exact built wheel with `[browser]`,
  verifies the scoped `zendriver` requirement and imports it from isolated
  `site-packages` on Linux/Windows Python 3.10 and 3.14.
- **Rich-input [#211](https://github.com/kymuco/chatgpt-web-adapter/pull/211)**
  remains Draft with a distinct protected Send/attachment boundary.
  Do not replay any previously claimed/ambiguous send. Historical
  [#208](https://github.com/kymuco/chatgpt-web-adapter/pull/208)
  overlaps merged composer resolver fix #210 and should not be merged wholesale.
- Open hardening issues include [#168](https://github.com/kymuco/chatgpt-web-adapter/issues/168)
  (read deadline during 429 backoff), [#172](https://github.com/kymuco/chatgpt-web-adapter/issues/172)
  (PEP 561 typing), and [#114](https://github.com/kymuco/chatgpt-web-adapter/issues/114)
  (long-history read checkpoints).

Release order: complete minimum install/release gates; reconcile affected live
browser boundaries; choose version/changelog; run exact-wheel/publish gates; only
then consider a release. CI green is not equivalent to a live product E2E.

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
