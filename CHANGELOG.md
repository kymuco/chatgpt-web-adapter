# Changelog

All notable changes to this project should be documented in this file.

The format is intentionally lightweight. Keep entries focused on user-visible behavior, compatibility notes, and experimental-surface changes.

## Unreleased

- compatibility: prepared ordinary-text writes to existing conversations now consume one current two-phase finalized Sentinel bundle (`requirements` + proof + Turnstile) and never call the legacy single-step requirements path; new-chat and multimodal sends remain unchanged
- compatibility: finalized Sentinel bundles are monotonic-expiry, exclusive-reservation, one-write-attempt credentials; unknown write outcomes never restore/replay a consumed bundle
- security: two-phase Sentinel acquisition no longer trusts persisted `AuthData.turnstile_token`; current-prepare Turnstile/SO evidence must come from an in-memory provider explicitly bound to the exact `prepare_token` and current challenge descriptors, and absent/mismatched provider evidence fails closed before finalize
- compatibility: `so.required=true` is now an explicit browser-capability gate rather than structural-only evidence; PR7.11c ships no browser fulfillment provider, so current live writes stop at `SENTINEL_BROWSER_CHALLENGE_PROVIDER_REQUIRED` until that boundary is independently characterized
- compatibility: conversation prepare and final write now share one `x-oai-turn-trace-id`; local reuse of one user-message id across `partial_query` and the final message is documented as an adapter choice rather than a required browser invariant
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
- refactor: grouped public exports by support level
- refactor: tightened request error messages and stream-completion event naming
- packaging: added PyPI Trusted Publishing workflow for release-based package publishing
- packaging: raised the setuptools build backend requirement for modern license metadata

## 0.1.3

- existing release baseline prior to the current documentation, diagnostics, and compatibility-clarity pass
