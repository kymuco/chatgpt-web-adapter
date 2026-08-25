# Changelog

All notable changes to this project should be documented in this file.

The format is intentionally lightweight. Keep entries focused on user-visible behavior, compatibility notes, and experimental-surface changes.

## Unreleased

- experimental transport: add explicit `browserless-request` under `ChatGPTProductRuntime` while keeping `browser-owned` as the default `PRODUCTION` transport; browserless remains `EXPERIMENTAL` and uses only the current two-phase Sentinel prepare/finalize plus conversation-prepare/conduit final-write sequence
- browserless safety: fail closed on required or malformed Sentinel challenge descriptors, never invoke browser/proof challenge providers or legacy/browser fallbacks, strip inherited one-shot requirements/proof/Turnstile/conduit credentials, and never automatically retry an ambiguous write
- browserless finality: serialize continuation mutation authority per canonical client, refresh queued continuation parents after lock acquisition, enforce one total invocation deadline across queue/preflight/write/recovery/reconciliation, and require submitted assistant identity to match canonical completed-status and readback identity before success
- browserless live gate: add bounded structured outcomes for direct completion, challenge boundary, protocol drift, reconciliation-required, and prewrite request/assembly failure; authenticated live evidence reproduced a zero-write `CHALLENGE_BOUNDARY` when current Sentinel required PoW, SO, and Turnstile evidence
- runtime-contract: add schema-1 `ProductRuntimeContract` inspection, validate the complete stable runtime operation/interface boundary, and fail closed on missing or contradictory retry, fallback, reconciliation, finality, transport, or product-semantics governance
- transport: classify built-in `browser-owned` as `PRODUCTION` while unknown/future transports default to `EXPERIMENTAL`; keep transport support tier independent from capability state and derive support/schema metadata rather than accepting caller self-promotion
- compatibility: preserve the released `ChatGPTProductRuntime`, `ProductRuntimeHealth`, and minimal `ProductWriteTransport` surfaces while exposing new contract/support authority through the primary Python SDK and capability/contract serialization

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
