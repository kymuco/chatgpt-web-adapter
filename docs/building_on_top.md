# Building On Top of the SDK

This package is best treated as an engine for tools that want to reuse a live ChatGPT web session. If you are building a higher-level product such as `gptty`, keep the app layer clearly separated from the SDK layer.

## Recommended Foundation for a Product Layer

Use these as the core primitives:

- `ChatGPTWebClient.send()`
- `send_to_conversation()`
- `attach_conversation()`
- `get_messages()`
- `get_status()`
- `wait_until_completed()`
- image upload support
- sanitized debug traces for diagnostics

These are the most natural building blocks for a terminal UI, CLI, or orchestration app.

## Treat These as Optional or Experimental

- `approve_pending_action()`
- `wait_and_approve_pending_actions()`
- `send_and_auto_approve()`
- `PayloadBuilder`
- `validate_payload()`
- `send_payload()`

They are useful, but they should not be the foundation of a product architecture. They depend more directly on unstable web behavior and should be isolated behind product-specific feature flags or adapter layers.

## Suggested Product Boundary for gptty

`chatgpt-web-adapter` should remain responsible for:

- auth consumption
- transport
- payload shaping
- stream parsing
- conversation parsing
- reusable client-side status helpers

`gptty` should be responsible for:

- terminal UX
- conversation/session presentation
- command routing
- local config and user preferences
- retry policy
- product-specific approval UX
- app-specific workflow automation
- logging/presentation decisions beyond the SDK event model

## Do Not Push App Logic Down Into the SDK

Examples of app-layer behavior that should stay outside this repository:

- slash commands
- prompt templates tied to a UX
- terminal rendering decisions
- persistent local chat history policy
- connector-specific product rules
- repository-specific or workspace-specific allowlists

If a feature only exists because `gptty` needs it, that is a strong sign it belongs in `gptty`, not here.

## How to Integrate Safely

Recommended approach:

1. Treat the SDK as a library boundary.
2. Wrap it in a small product-side service layer.
3. Consume structured events instead of scraping exceptions or token text.
4. Keep experimental SDK features behind explicit product-side opt-in behavior.
5. Use live smoke checks after any change that touches transport, parsing, uploads, or approvals.

## Practical Recommendation

If `gptty` needs richer workflows, prefer adding product-side orchestration first. Only promote logic into `chatgpt-web-adapter` when it is clearly reusable, application-agnostic, and justified for the stable core.
