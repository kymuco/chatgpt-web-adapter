# Project Status

_Last updated: 2026-10-30 (v0.4.0 release candidate audit; not published)_

This is the compact current-state view for `chatgpt-web-adapter` (CWA).

Use [`ROADMAP.md`](ROADMAP.md) for direction,
[`README.md`](README.md) for the project overview, and
[`docs/README.md`](docs/README.md) for the documentation map.

## Release and branch state

```text
latest public release   v0.3.0
release date            2026-09-01
package version         0.4.0 (staged source candidate; not published)
current main            9519d390 (post-0.3 with cleanup #250 merged)
architecture            PR15 provider architecture frozen
current phase           v0.4.0 release candidate verification
license                 MIT
python                  3.10-3.14
```

Current `main` is `9519d390d48945fd098f2a92421f133821662407`
(2026-10-30): pre-v0.4.0 cleanup #250 was merged, reducing the source
diff by 5,985 net lines (66 changed paths; 21 removed files). No extension
JavaScript or active Direct HTTP send behavior was changed in that cleanup.
The branch also includes fail-closed curl transfer integrity and bounded
read-only canonical-GET curl-28 timeout handling.

The synchronized versioned release candidate [#238](https://github.com/kymuco/chatgpt-web-adapter/pull/238)
at `a84bba9e84e8e6702053b74422700745c5c15b29` passed 16/16 GitHub
CI checks (Windows/Linux Python 3.10–3.14, wheel/sdist, candidate release
gate and installed-wheel smoke). This is the **pre-documentation** checked
head; the final documentation-updated head needs its own green CI.
The newest published package remains `v0.3.0` (2026-09-01); its wheel
does **not** include post-0.3 features.

## Proposed v0.4.0 scope and readiness (audit: 2026-10-30)

The source candidate stages package version `0.4.0`, but this is **not** a Git
tag, published GitHub Release, or authorization to upload to PyPI. Preserve
the legacy browser-owned SDK default for compatibility while promoting
`BrowserlessHTTPClient` to the primary ChatGPT public surface for live-verified
operations. Browser-owned is secondary/experimental, not an automatic fallback.
Ship the already-merged post-0.3 capabilities: ChatGPT Direct HTTP; Deep Research launch and canonical report readback (#227/#228);
ordinary-request image generation observation and generated-image readback
(#229); narrow governed file handoff; isolated experimental Qwen Web;
experimental DeepSeek/Gemini and module-only Google Translate/Gemini Notebook.
Neither one live success nor a release number promotes private web protocols
to production or guarantees automatic image tool selection.

**Confirmed:** versioned candidate `a84bba9e` passed 16/16 CI, including
four clean installed-wheel smokes on Ubuntu/Windows with Python 3.10 and
3.14. These packaging and deterministic checks are not fresh live-product
evidence. Earlier image readback was independently proven on UI/HTTP,
and governed generated-file handoff verified exact bytes and SHA-256.

**2026-10-29 evidence and disposition:** PR #237 changes the recommended
ChatGPT integration path to primary Direct HTTP without changing the legacy
SDK default. The current public API classification is PRIMARY_PRODUCTION for
`BrowserlessHTTPClient` and EXPERIMENTAL for browser-owned.
The exact `main` at `0e330c5e` passed 16/16 CI. A user-run Direct HTTP E2E
completed one send with three Markdown files, two streaming callbacks,
file-only expected values and canonical ID/text/status match. GPT-6 High
was requested, not independently server-attested. A fresh browser-owned
three-file attempt stalled after one visible attachment; no confirmed
multi-file browser acceptance exists for this source revision. Do not
resend that attempt or silently promote its capability reliability.

**Release disposition and remaining steps:**

1. **Known limitation for v0.4.0:** browser-owned three-file UI acceptance did not complete on 2026-10-29. Browser-owned stays `EXPERIMENTAL`, not a production multi-file reliability claim. Historical draft [#211](https://github.com/kymuco/chatgpt-web-adapter/pull/211) is not to be merged wholesale; publishing requires the maintainer to accept the scoped limitation explicitly. No automatic replay after ambiguous writes.
2. **Closed / retained:** browser-native canonical 429 read-deadline issue [#168](https://github.com/kymuco/chatgpt-web-adapter/issues/168) was fixed by #232. Subsequent curl-transfer-integrity and bounded canonical-read curl-28 fallback changes preserve fail-closed semantics. The HTTP 500 step-down proposal in draft [#221](https://github.com/kymuco/chatgpt-web-adapter/pull/221) remains unproven and excluded.
3. **Closed:** cleanup PR #250 merged; versioned candidate `a84bba9e` passed 16/16 release CI. Installed-wheel and static import verification do not attest private-web-protocol stability.
4. **Pending:** green CI on the final documentation-updated candidate, an exact release SHA, dated changelog and tag/version parity, and separate maintainer authorization before merging/tagging or publishing to PyPI.

**Deferred unless independently justified:** experimental Linux Qwen draft
[#217](https://github.com/kymuco/chatgpt-web-adapter/pull/217) requires actual
EndeavourOS Native Messaging E2E; Qwen #223/#226 are deferred. The narrow
verified capability metadata correction from #225 and PEP 561 packaging
marker from #172 are staged in the candidate; full strict type checking and
resumable history (#114) remain out of scope. No Codexia/HDE change, MCP layer, universal provider
router, new browser-bypass code, or implicit retries belong in this release.

## Product role

CWA is a standalone local product-runtime bridge for authenticated consumer AI web
products.

Current provider/capability status:

```text
ChatGPT HTTP          PRIMARY_PRODUCTION / live-verified SDK
ChatGPT browser UI    EXPERIMENTAL / secondary (legacy default)
DeepSeek Web          EXPERIMENTAL conversational runtime
Gemini Web            EXPERIMENTAL conversational runtime
Qwen Web              EXPERIMENTAL isolated Chrome/Native Host SDK
Google Translate Web  EXPERIMENTAL non-chat translate_text capability
Gemini Notebook Web    EXPERIMENTAL add_url_source + background Audio Overview lifecycle
```

The shared provider-neutral architecture is represented by
`ProductProviderBoundary schema 2`, but that boundary is metadata/invariant validation
over a runtime, not an execution router.

## ChatGPT primary HTTP SDK and secondary UI runtime

Primary ChatGPT application client (live-verified operations):

```text
BrowserlessHTTPClient
```

The historical `ChatGPTProductRuntime` and its browser-owned default remain
available as a secondary UI compatibility surface.

Secondary UI mutation transport (legacy default):

```text
browser-owned = EXPERIMENTAL
```

Alternative direct-request transports (two distinct implementations):

```text
browserless-request = EXPERIMENTAL (historical runtime transport)
BrowserlessHTTPClient = PRIMARY_PRODUCTION / primary ChatGPT SDK (#212, #237)
```

The direct HTTP client uses a saved authenticated session, Node.js 24+ and curl;
it does not start a tab or silently fall back to the browser-owned runtime. One
user-run Codexia bootstrap proved three Markdown attachments, GPT-6 High
requested/extended observed, streaming and exact assistant-message readback.
The resulting `CAPTURED_UNADMITTED` is transport evidence, **not** Codexia Work
completion. A separate user-run Windows check on 2026-10-23 confirmed one GPT-6
High-requested send, Temporary Chat send, streaming (two chunks), two Markdown
and one PNG input, cross-process continuation, a 13-message canonical export
and SHA-256-verified 25-byte generated-artifact handoff. This does not prove
general reliability. See [direct HTTP SDK](docs/browserless_http_sdk.md).

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

Browser-owned remains a secondary experimental UI mutation strategy. Its
legacy runtime default is retained for compatibility, not as a recommendation.

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

The old PR10.1 unsupported status was superseded by the **narrow PR14.0
governed handoff**: `ChatGPTWebClient.handoff_generated_artifact(...)`, also
inherited by `BrowserlessHTTPClient`, can materialize exactly one caller-named,
conversation-owned generated artifact using the product `file_id`, resolver,
integrity verification and explicit no-overwrite local destination policy.

On 2026-10-23 a user-run Windows HTTP conversation generated a 25-byte TXT;
its inherited handoff downloaded the exact expected bytes and verified
SHA-256 with `overwritten=False`. This is bounded live evidence, not a
general claim about uploaded attachments, arbitrary links, provider lifecycle
or indefinite availability. Observing an artifact never grants permission
to download or write without an explicit caller destination.

See [PR14.0](docs/engineering/pr14_0_governed_generated_artifact_handoff.md).

### Browserless writes

`browserless-request` remains experimental. The separate
`BrowserlessHTTPClient` is now the PRIMARY_PRODUCTION public SDK for selected
live-verified operations; it is still vulnerable to private protocol changes
and does not guarantee automatic auth recovery or transport fallback. Scoped browser-session sync and
canonical-GET `401` recovery do not automatically apply to `BrowserlessHTTPClient.send()`.

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
