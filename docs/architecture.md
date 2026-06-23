# Architecture

`webchat-adapter` is intentionally small, but it already has a few distinct layers. Keeping those layers clear is important if the package is going to remain a reusable SDK instead of drifting into an application framework.

## Layer 1: Auth Loading

Primary files:

- `src/webchat_adapter/auth.py`
- `src/webchat_adapter/types.py`

Responsibilities:

- load `auth_data.json`
- fall back to `.env` when needed
- normalize access token, cookies, and headers
- detect expired JWT-like access tokens when possible

This layer should stay narrowly focused on consuming existing auth material. It should not grow into login automation or browser-based capture logic.

## Layer 2: Transport

Primary files:

- `src/webchat_adapter/client.py`

Responsibilities:

- build HTTP headers
- construct `curl` commands
- run standard requests
- run streaming backend requests
- persist response cookies
- optionally write sanitized debug traces

This is the core engine of the SDK. It should remain reusable and low-level. Product-specific orchestration should not be pushed down into transport unless it is genuinely required by all consumers.

## Layer 3: Backend Contract Shaping

Primary files:

- `src/webchat_adapter/client.py`
- `src/webchat_adapter/payload_builder.py`
- `src/webchat_adapter/payload_validation.py`
- `src/webchat_adapter/raw_payload.py`

Responsibilities:

- create web-backend message payloads
- encode model, reasoning, search, temporary-chat, and media options
- handle upload handshake and multimodal message shaping
- provide an escape hatch for experimental raw payload work

This layer is where reverse-engineered request contracts live. It should stay explicit and easy to diff when the site changes.

## Layer 4: Stream and Conversation Parsing

Primary files:

- `src/webchat_adapter/client.py`
- `src/webchat_adapter/message_text.py`
- `src/webchat_adapter/messages.py`
- `src/webchat_adapter/model_detection.py`
- `src/webchat_adapter/status.py`
- `src/webchat_adapter/attach.py`

Responsibilities:

- parse SSE backend events
- extract assistant text and finish reasons
- attach to existing conversation state
- read current-branch messages
- detect models best-effort
- derive conversation status and pending approval descriptors

This layer is inherently fragile because it depends on undocumented response shape. Tests and live smoke checks should be concentrated here.

## Layer 5: Workflow Helpers

Primary files:

- `src/webchat_adapter/wait.py`
- `src/webchat_adapter/conversation_send.py`
- `src/webchat_adapter/policy_approval.py`
- `src/webchat_adapter/diagnostic_metrics.py`

Responsibilities:

- continue existing conversations ergonomically
- wait for completion
- add policy-aware approval wrappers
- enrich `send()` with expanded metrics and events

This layer is where the SDK starts to feel higher-level. It is useful, but it should still remain application-agnostic.

## Stable vs Experimental Pressure

In practice:

- auth, transport, send/continue, conversation read/status, and uploads are the stable core
- approval helpers and raw-payload helpers are experimental pressure points

That distinction matters architecturally. Experimental flows should not dictate the shape of the stable core.

## What Should Stay Out of This Repository

The SDK should avoid becoming:

- a full CLI product
- a TUI or terminal chat experience
- a browser automation suite
- a connector-specific automation product
- a repository of app-specific workflow policy

Those belong in a product layer built on top of the SDK.
