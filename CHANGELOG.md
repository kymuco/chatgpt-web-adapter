# Changelog

All notable changes to this project should be documented in this file.

The format is intentionally lightweight. Keep entries focused on user-visible behavior, compatibility notes, and experimental-surface changes.

## Unreleased

- auth: add public `browser_login_current_tab()` through the installed Chrome extension and Native Messaging bridge; it opens one active additional `chatgpt.com` tab in the already-running Chrome, captures only bounded ChatGPT session material, atomically replaces the selected auth file, and never reads or clears the Chrome profile cookie database
- auth security: serialize current-Chrome capture with browser writes/reads/tab disposal, validate ChatGPT cookie domains and payload bounds in both extension and Python, sanitize bridge failures, and never retry after a response is lost following delegation
- connectors / required actions: add post-0.3 typed connector and required-action lifecycle observations that require explicit stable product identity/correlation; authenticated product evidence proves required-action point observation while the combined `tools_connectors` capability remains `UNKNOWN`
- connector authority boundary: keep product observation separate from approval, connector authorization, canonical finality, retry authority, and downstream filesystem/Git/workspace authority; generic router/tool activity, display names, DOM adjacency and generated ids are not treated as connector lifecycle identity
- generated artifacts: add a bounded `ProductArtifactObservation` boundary and fail closed around locator-bearing evidence; current generated-artifact download/materialization status is `ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY`
- artifact research closure: preserve PR10.1 characterization probes as reproducible evidence while disabling the historical v1-v10 DOM/CDP/React startup chain in ordinary runtime; no download, destination, overwrite, retry or fallback authority is introduced
- docs/public readiness: refresh README, status, roadmap, usage, architecture, security, contribution guidance and documentation navigation to reflect the actual post-0.3 / PR10 runtime boundary while retaining historical PR-specific evidence as lineage
- browser bridge product surface: give the unpacked Chrome bridge a CWA-specific icon family, product name/description, light/dark read-only popup, sanitized local status, toolbar ready/working/unavailable state and explicit `Open ChatGPT` / `Copy status` actions without adding product-write, runtime-tab provisioning, retry, approval or finality authority
- browser bridge packaging: package and release-gate the complete extension product surface (`.json`, `.js`, `.html`, `.css`, `.png`) so popup/icon assets cannot disappear from built wheel/sdist artifacts

## 0.3.0 - 2026-09-01

- runtime-contract: freeze browser-owned schema-1 product runtime/support metadata as the standalone production baseline while keeping transport support tier independent from individual capability state
- browserless: add explicit `browserless-request` behind `ChatGPTProductRuntime` as an `EXPERIMENTAL` transport with fail-closed Sentinel/challenge admission, one total invocation deadline, shared-client mutation serialization, strict submitted/completed/readback identity agreement, no browser/legacy fallback, and no automatic retry after ambiguous writes
- browserless live evidence: authenticated characterization reached current Sentinel prepare and returned a zero-write `CHALLENGE_BOUNDARY` when PoW, SO, and Turnstile evidence were required; this validates the safety boundary rather than production browserless-write availability
- rich input: add browser-owned image new chat, general file new chat, and multimodal continuation through `media=`, with exact requested attachment-set validation, official-composer ownership, bounded staging/materialization, validated-click request-body correlation, request-bound message/conversation identity, one outer turn deadline, and canonical readback finality
- rich-input capability freeze: report `images`, `files`, and `multimodal_continuation=AVAILABLE` only on the live-proven production/default provider path; custom/legacy providers or send/RPC overrides remain conservative and do not inherit authority from transport identity alone
- observations: add immutable structured product observations for search, generic tool/activity points, source identity, citation-to-source relationships, and required-action evidence; `ProductRuntimeExecution` now carries runtime-owned observations and a dropped-observation-event count
- observation safety: keep assistant text, raw tool args/results, raw metadata/SSE, credential-bearing source URLs, DOM/HTML and private-thought text outside the typed observation boundary; observation defects do not become write failure, retry authority, canonical finality, connector authority, or downstream mutation authority
- web search: authenticated live evidence proves typed search activity, safe source identity, citation relationships, valid citation ranges, zero dropped observation events, one write, canonical `CANONICAL_READBACK` completion, no automatic retry, and no fallback transport on the proven production/default browser-owned path
- tools: authenticated generic product-tool characterization records the operations the ChatGPT product actually emitted rather than inferring an internal tool from the prompt; combined `tools_connectors` intentionally remains `UNKNOWN`
- public API: promote the immutable observation value types to root `PRIMARY_PRODUCTION`; classify `MediaItem` / `MediaSource` as `SHARED_SUPPORT`; keep internal `ProductObservationCollector` outside the root public API
- packaging: make candidate exact-wheel smoke version-agnostic by deriving `[project].version` from the checkout while keeping tagged publishing explicit; strengthen wheel/sdist and installed-package validation around frozen 0.3 runtime/capability/provenance/observation/public-surface modules
- source distribution: explicitly package root `CHANGELOG.md`; the strengthened PR9.4 artifact gate caught this missing-sdist-file defect before the 0.3 version bump and the package manifest was repaired rather than weakening the gate
- release: stage package metadata at `0.3.0`, preserve Linux/Windows Python 3.10-3.14 CI, exact wheel/sdist validation, installed-wheel smoke, and strict tag/version/dated-changelog equality before Trusted Publishing
- compatibility: retain `ChatGPTWebClient`, the stable `cwa` CLI, experimental raw/backend helpers, and low-level research/diagnostic browser/Sentinel surfaces without silently promoting them or removing them for tree cleanliness

## 0.2.0 - 2026-08-22

- runtime: graduate `ChatGPTProductRuntime` as the primary forward-looking text-turn boundary with browser-owned product writes, canonical browserless read/status/final readback where available, explicit completion provenance, no automatic ambiguous-write retry, and no hidden compatibility fallback
- streaming: add revision-safe streaming/finality handling and stable final-only observation without fabricating completion metadata
- models: stabilize product-native CLI profile aliases `INSTANT`, `MEDIUM`, and `HIGH` alongside compatibility aliases `FAST`, `BALANCED`, and `DEEP`; `MAX` remains intentionally unmapped because no fourth proven selector is frozen
- temporary: graduate Temporary Chat for production text turns with session-local identity, explicit lifecycle closure, fail-closed fresh-session startup readiness, and no durable-conversation authority derived from Temporary ids
- cli: add the stable `cwa` surface for `send`, `status`, `capabilities`, `messages`, `snapshot`, `export`, and read-only `doctor`, with frozen exit-code classes for success, unavailable state, usage failure, operational failure, and reconciliation-required boundaries
- artifacts: separate canonical `messages`, portable current-branch `export`, curated `snapshot`, and schema-1 completion manifests that record media type, exact byte count, and SHA-256 identity for emitted files
- diagnostics: add `cwa doctor` checks for environment, auth, Native Messaging install/registration, browser bridge, product runtime, capabilities, and optional artifact-integrity verification without performing login, refresh, install, reload, product writes, retries, fallbacks, or artifact repair
- packaging: stage the distribution at `0.2.0`, harden Linux/Windows CI across Python 3.10-3.14, validate exact wheel/sdist contents and console entry points, smoke-test the installed wheel from a disposable environment outside the source checkout, and gate Trusted Publishing on tag/version/changelog agreement
- docs: preserve compatibility/research support tiers and historical examples while documenting the stable 0.2 `cwa` path, release integrity, and intentionally deferred image/file/multimodal/tools/browserless-write work
- compatibility: retain `ChatGPTWebClient`, experimental raw/backend helpers, and low-level Sentinel/browser-native surfaces under their existing support tiers rather than silently promoting them into the frozen 0.2 product-runtime contract

## 0.1.7 - 2026-08-11

- auth: persist structured `browserCookies` with domain/path/expiry metadata while retaining the backward-compatible flat `cookies` map
- auth: report persistent-profile health and structured cookie count through `auth status`
- browser: serialize cross-process access to the persistent Chromium profile and close its CDP connection without the benign duplicate-close warning
- sentinel: retry transient browser capture failures, expose privacy-safe stage diagnostics, and support the `auto_sentinel` client shortcut with optional headless capture
- live: verify first-turn system prompts, new chat, continuation, attach/read/status, headless text writes, PNG/JPEG/GIF/WebP uploads, multiple images, and image continuation against the current web backend
- packaging: add Python 3.14 to package metadata and the Linux/Windows CI matrix
- auth: refresh expired or missing web access tokens through `/api/auth/session`, rotate session credentials in memory, and atomically update `auth_data.json`; `refresh_auth()` provides an explicit refresh boundary
- compatibility: route normal new-chat and multimodal `send()` calls through the observed conversation prepare/conduit flow when a Sentinel provider is installed
- compatibility: new-chat prepare now uses the observed `client-created-root`, `client_prepare_state=none`, debounced/window-focus shape without a legacy partial query or initial conduit header
- compatibility: finalized Sentinel bundles now protect new-chat and image writes as well as existing ordinary-text continuation writes
- compatibility: browser Sentinel capture now uses trusted keyboard input and reads finalize bodies from the exact `ResponseReceived` request instead of relying on Zendriver's unstable `LoadingFinished` dispatch
- tests: add contract coverage for auth rotation/persistence, protected new-chat creation, and the full create/upload/finalize multimodal path

## 0.1.6 - 2026-08-11

- feat: added an optional `ZendriverSentinelBundleProvider` (`chatgpt-web-adapter[browser]`) that captures a complete unused bundle from the official ChatGPT page without submitting a message or persisting one-shot credentials
- compatibility: finalized-bundle providers can now bypass SDK-side prepare/finalize entirely, while the lower-level current-prepare challenge-provider boundary remains available for custom integrations
- compatibility: prepared ordinary-text writes to existing conversations now consume one current two-phase finalized Sentinel bundle (`requirements` + proof + Turnstile) and never call the legacy single-step requirements path; new-chat and multimodal sends remain unchanged
- compatibility: finalized Sentinel bundles are monotonic-expiry, exclusive-reservation, one-write-attempt credentials; unknown write outcomes never restore/replay a consumed bundle
- security: two-phase Sentinel acquisition no longer trusts persisted `AuthData.turnstile_token`; current-prepare Turnstile evidence must come from an in-memory provider bound to the exact prepare input, `prepare_token`, and current challenge descriptor, and absent/mismatched provider evidence fails closed before finalize
- compatibility: prepared writes reserve their rolling finalized bundle before conversation prepare, consume it only at final write-header construction, and start a best-effort background refill after consumption; the public provider boundary remains fail-closed when no legitimate browser provider is installed
- compatibility: browser frontend evidence establishes required SO collector work as fire-and-forget rather than a finalize blocker; SO descriptors remain available to the provider context, while finalize continues to contain only `prepare_token`, PoW, and Turnstile evidence
- compatibility: conversation prepare and final write now share one `x-oai-turn-trace-id`; local reuse of one user-message id across `partial_query` and the final message is documented as an adapter choice rather than a required browser invariant
- compatibility: finalized expiry is clamped by both `expire_after` and `expire_at` before conversion to a monotonic deadline
- security: conduit and all three Sentinel write headers are always redacted from debug traces even when ordinary trace sanitization is disabled; Sentinel prepare/finalize raw bodies remain suppressed in favor of structural traces
- diagnostics: existing prepared-send requirements timing now measures the execution-local finalized-bundle acquisition/consumption boundary while preserving the established `requirements_ready` event shape
- diagnostics: added a privacy-safe probe for the current two-phase Sentinel `chat-requirements/prepare` contract; it records only status/key/presence structure and stops before challenge finalization or any conversation write
- compatibility: live browser evidence now records a current `chat-requirements/prepare -> chat-requirements/finalize` Sentinel sequence; the legacy single-step requirements path remains unchanged for legacy sends but is not considered live-validated for the current prepared-write contract
- compatibility: any `stream_handoff` observed on the prepared existing-text path forces bounded conversation recovery even when the initial stream already contains a text prefix and assistant id; recovered prefix extensions emit only the missing token suffix
- diagnostics: prepare responses never serialize raw conduit-token credentials into debug traces; credential-bearing generic HTTP tracing is suppressed for prepare and replaced with a structural status/key/presence trace
- diagnostics: prepared existing-text writes retain the established expanded send instrumentation (request/requirements/stream lifecycle events, structured request errors, and latency/backend metrics); successful streams copy only allowlisted model/reasoning/finish fields from the real private parser state, without exposing raw SSE or handoff credentials
- diagnostics: prepared existing-text streaming emits each public structured `assistant_token` once by keeping expanded send instrumentation as the token-event owner and filtering the lower-level duplicate transport event
- diagnostics: prepared-write lifecycle events expose only structural token-presence state
- diagnostics: added an ordinary-text `conversation/prepare` contract probe that records structural evidence without serializing prompt text, ids, raw responses, or conduit-token values
- compatibility: added a reusable text prepare/conduit boundary using the observed `partial_query` shape and initial `x-conduit-token: no-token`
- models: the default reasoning path now uses the live-observed GPT-5.6 web slug `gpt-5-6-thinking`; Medium maps to `standard` and High maps to `extended`
- models: added an evidence-backed capability registry and `gpt-5.6` / `thinking` convenience aliases while keeping unknown explicit model slugs pass-through and leaving unobserved Extra High unmapped
- auth: raw ChatGPT `/api/auth/session` dumps now best-effort map `sessionToken` to the web session cookie while preserving explicit/chunked browser cookies
- compatibility: web writes now synchronize `oai-did` to `oai-device-id` and fail early with `TURNSTILE_REQUIRED` when ChatGPT requires browser challenge evidence that was not supplied
- diagnostics: live contract probes now preserve read-only model/reasoning evidence when a write is blocked by Turnstile and support explicit `--attach-only` capture
- diagnostics: added a privacy-safe live model/transport contract probe for validating ChatGPT web model rollouts before changing SDK defaults or aliases
- docs: added the PR7.9 live model contract probe protocol and evidence/exit criteria

## 0.1.5 - 2026-06-24

- feat: added experimental required-action detection for connector OAuth/linking cards such as Gmail connect prompts
- docs: documented required-action handling and its distinction from browserless tool approvals

## 0.1.4 - 2026-06-24

- breaking: renamed the canonical Python import package to `chatgpt_web_adapter` and removed the old `webchat_adapter` import path
- feat: added opt-in sanitized debug trace mode for HTTP and streaming requests
- docs: aligned repository metadata after the `chatgpt-web-adapter` rename
- docs: defined stable vs experimental SDK surface and compatibility policy
- docs: clarified approval helpers as experimental and unstable
- docs: added SDK positioning, failure model, live smoke checklist, release checklist, architecture notes, and build-on-top guidance
- refactor: grouped public exports by support level
- refactor: tightened request error messages and stream-completion event naming
- packaging: added PyPI Trusted Publishing workflow for release-based package publishing
- packaging: raised the setuptools build backend requirement for modern license metadata

## 0.1.3

- existing release baseline prior to the current documentation, diagnostics, and compatibility-clarity pass
