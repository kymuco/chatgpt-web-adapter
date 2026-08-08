# Changelog

All notable changes to this project should be documented in this file.

The format is intentionally lightweight. Keep entries focused on user-visible behavior, compatibility notes, and experimental-surface changes.

## Unreleased

- compatibility: ordinary text writes to existing conversations now use the live-observed `conversation/prepare` -> conduit-token -> fresh chat-requirements/Turnstile -> `/f/conversation` sequence; warmup-prefetched requirements are discarded before prepare, while new-chat and multimodal writes remain unchanged pending independent evidence
- compatibility: prepared existing-conversation writes reuse one user message id across `partial_query` and the final message, require `client_prepare_state: success`, and fail closed before the final write on prepare/conduit/Turnstile failures
- diagnostics: prepared existing-text writes retain the established expanded send instrumentation (request/requirements/stream lifecycle events, structured request errors, and latency/backend metrics) and preserve observed model/reasoning/finish metadata from successful streams
- diagnostics: prepared-write lifecycle events expose only structural token-presence state, while sanitized traces continue to redact `x-conduit-token`
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
