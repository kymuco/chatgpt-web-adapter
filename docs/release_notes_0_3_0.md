# CWA 0.3.0

Release date: 2026-09-01

CWA 0.3.0 is the release that extends the frozen 0.2 browser-owned product runtime from a text-first baseline into a broader, evidence-backed product surface while preserving the same separation between product mutation, observation, canonical finality and downstream authority.

## Highlights

### Browser-owned production runtime contract

- `ChatGPTProductRuntime` remains the primary forward-looking application boundary.
- `browser-owned` remains the only `PRODUCTION` write transport.
- The runtime contract keeps automatic ambiguous-write retry disabled and has no hidden fallback to the historical direct-write path.
- Canonical read/status/final readback remains authoritative for completion; incremental or structured observations do not become canonical finality.
- Transport support tier and individual capability state remain separate machine-readable contracts.

### Images, files and multimodal continuation

PR9.2 graduates rich input on the live-proven production/default browser-owned provider path:

- image new chat;
- general file new chat;
- multimodal continuation;
- exact requested attachment-set validation;
- attachment-dependent response evidence;
- validated-click request-body correlation;
- request-bound conversation/message identity;
- one outer rich-turn deadline;
- canonical `CANONICAL_READBACK` finality;
- no automatic write retry and no fallback transport.

Native Messaging carries validated local paths rather than attachment bytes. The official ChatGPT page remains the owner of upload and protected submit.

Capability graduation is provider-aware. Custom or legacy providers do not inherit `images`, `files`, or `multimodal_continuation=AVAILABLE` from the `browser-owned` transport name alone when they do not preserve the live-proven provider send/RPC path.

### Structured search, tool, source and citation observations

PR9.3 adds immutable typed product observations for:

- search activity;
- generic tool/activity points;
- source identity;
- citation-to-source relationships;
- required-action observations.

`ProductRuntimeExecution` exposes the runtime-owned observation tuple and a dropped-observation-event count. The observation layer consumes bounded standardized events and deliberately excludes assistant text and canonical-finality authority.

Source/citation handling includes privacy and identity guards: only acceptable HTTP(S) source URLs are exposed, fragments are stripped, common credential-bearing/signed URL forms are rejected, citation ranges must be complete and valid, source identity must exist before a citation relation is emitted, and private-thought/raw metadata/tool payloads are not exported through this surface.

Authenticated PR9.3 live evidence proved a complete web-search → source → citation path with canonical readback and zero dropped observation events. A separate generic product-tool characterization proved that CWA records what the product actually emitted instead of inferring a desired internal tool from the prompt.

`web_search=AVAILABLE` is therefore provider-aware on the proven production/default path. `tools_connectors` deliberately remains `UNKNOWN`: generic tool observation does not establish connector coverage, connector credential/authorization behavior, required-action continuation, or a general caller-selectable tool-execution contract.

### CWA 0.3 public Python surface

The root `PRIMARY_PRODUCTION` surface now includes the immutable observation value types:

- `ProductObservationKind`;
- `ProductObservationPhase`;
- `ProductActivityObservation`;
- `ProductSourceObservation`;
- `ProductCitationObservation`;
- `ProductRequiredActionObservation`;
- `StructuredProductObservation`.

`MediaItem` and `MediaSource`, which are used by the primary runtime rich-input signatures, are classified as `SHARED_SUPPORT` rather than legacy compatibility.

The internal `ProductObservationCollector` is intentionally not root-exported and receives no public support tier.

### Experimental browserless transport

PR9.1 adds `browserless-request` behind the frozen product-runtime transport boundary, but it remains `EXPERIMENTAL`.

Its current contract is fail-closed around Sentinel/challenge admission, strips inherited one-shot protection credentials, serializes shared-client mutation authority, applies one total invocation deadline, requires submitted/completed/readback assistant identity agreement, and never falls back to browser-owned or legacy writes.

Authenticated live characterization reached the current Sentinel prepare path and returned a zero-write `CHALLENGE_BOUNDARY` when PoW/SO/Turnstile evidence was required. That is evidence for the safety boundary, not evidence for production browserless-write availability.

### Release and packaging hardening

CWA 0.3 strengthens the artifact contract beyond the 0.2 release gate:

- candidate exact-wheel smoke no longer hardcodes a release version and instead derives `[project].version` from the checkout;
- tagged publishing continues to pass the GitHub Release tag explicitly and must satisfy tag/version/changelog equality;
- wheel/sdist validation requires the frozen 0.3 runtime, capability, provenance, observation and public-surface modules;
- installed-wheel smoke validates root support tiers from `site-packages`, not the source checkout;
- the internal observation collector is checked not to leak into the root API;
- root `CHANGELOG.md` is explicitly included in the source distribution.

The strengthened gate caught the missing-changelog sdist defect during PR9.4 before the version bump; the artifact contract was preserved and the package manifest was repaired instead of weakening the gate.

## Compatibility

`ChatGPTWebClient` remains available without deprecation for existing callers and historical workflows. The 0.3 release does not silently redirect compatibility writes through `ChatGPTProductRuntime` and does not remove low-level research/diagnostic APIs merely for tree cleanliness.

The stable `cwa` CLI from 0.2 remains available. CWA 0.3 does not claim that every new Python runtime capability has a new stable CLI equivalent.

## Known limitations / intentionally conservative boundaries

CWA 0.3 deliberately does **not** graduate:

- `tools_connectors` as a stable general capability;
- connector OAuth/credential/required-action continuation authority;
- a general caller-selected internal ChatGPT tool contract;
- rich-input + arbitrary custom-provider equivalence;
- rich-input + all model-profile compositions without independent evidence;
- `browserless-request` to `PRODUCTION`;
- product observations into write, retry, canonical-finality or downstream external-action authority.

The current production write transport still requires Chrome/Chromium, the packaged extension and Native Messaging host.

## Safety / support note

This project is not the official OpenAI API. It operates against an ordinary authenticated ChatGPT web-product session, and undocumented product/browser behavior can change independently of the package.

The central 0.3 authority rule is:

```text
product observation defect
    != product write failure
    != retry authority
    != canonical finality
    != external/local action authority
```

## Release evidence

The pre-version-bump PR9.4 stabilization head `9673b55892a2459b76c9feb1b65f61424b69c7dc` passed GitHub Actions CI #587:

```text
Ubuntu Python 3.10-3.14 source matrix     5/5 PASS
Windows Python 3.10-3.14 source matrix    5/5 PASS
wheel + sdist build                        PASS
twine metadata validation                  PASS
strengthened candidate artifact gate       PASS
installed wheel Ubuntu 3.10 / 3.14         2/2 PASS
installed wheel Windows 3.10 / 3.14        2/2 PASS
```

The final 0.3.0 release-candidate head must repeat the same exact-head CI after the version/changelog finalization. A published `v0.3.0` release must additionally pass the strict tag/version/dated-changelog gate and post-publish public PyPI verification.
