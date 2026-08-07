# Live Model Contract Probe

`examples/probe_live_contract.py` records the minimum evidence needed to update
`chatgpt-web-adapter` after a ChatGPT web model rollout without guessing private
backend model slugs or reasoning values.

The probe is deliberately **evidence-only**. It does not change SDK defaults,
model aliases, or reasoning mappings.

## Why an existing conversation is required

The web UI is the source of truth for the user-facing model/mode selection. Create
(or reuse) a conversation in ChatGPT with the target model and reasoning mode,
then let the SDK attach to that conversation and continue it with
`preserve_model=True`.

This separates three contracts that must not be conflated:

1. ChatGPT UI label (for example Medium or High).
2. Private web backend model slug actually present in the conversation/request.
3. Private backend reasoning value actually present in the conversation/request.

API model ids are not assumed to equal private ChatGPT web slugs.

## Fast auth from `/api/auth/session`

While signed in to ChatGPT in the browser, the JSON returned by
`https://chatgpt.com/api/auth/session` can be saved locally as `auth_data.json`.
The adapter consumes the top-level `accessToken` and now best-effort maps the
endpoint's `sessionToken` to the ChatGPT NextAuth session cookie when explicit
browser cookies are not already present.

Explicit cookies win. This matters because current browser sessions may expose a
chunked session cookie such as `__Secure-next-auth.session-token.0` and `.1`.
If those cookies are copied into `auth_data.json`, the adapter leaves them intact.

Before a write, the adapter also reuses or obtains the server-issued `oai-did`
cookie and mirrors it into the `oai-device-id` request header.

`/api/auth/session` is **not** a complete substitute for browser challenge state.
If `chat-requirements` says Turnstile is required and no legitimate browser-derived
Turnstile token was supplied, the adapter stops before the conversation POST with
`TURNSTILE_REQUIRED`. It does not synthesize, solve, or bypass that challenge.

Never share `auth_data.json` or values copied from browser authentication headers.

## Safety properties

The JSON report does **not** serialize:

- prompt or assistant response text;
- access tokens, cookies, proof tokens, Turnstile tokens, or resume tokens;
- conversation, message, turn, conduit, or topic ids;
- raw SSE/WebSocket frames;
- full websocket URLs;
- connector/tool payload values.

Identifiers are represented only as `*_present: true/false`. The probe stores
model/reasoning scalar values only when they come from model/reasoning-named
fields and match a conservative token-like character set.

Still review the report before attaching it to an issue or pull request.
Never share `auth_data.json` or a raw `watch_conversation.py` transcript.

## Run on Windows PowerShell

Install the checkout in editable mode. Installing `websockets` is recommended so
we can distinguish a real websocket path from polling fallback while PR7.11 is
still pending.

```powershell
python -m pip install -e ".[test]"
python -m pip install websockets
```

Create separate ChatGPT conversations for the modes you want to measure. Then run:

```powershell
python .\examples\probe_live_contract.py `
  "https://chatgpt.com/c/<conversation-id>" `
  --output .\artifacts\gpt56-medium.json
```

If the current web session requires Turnstile, the command no longer loses the
useful read evidence. It writes a sanitized report with:

```text
verdict = WRITE_BLOCKED_TURNSTILE
```

and keeps the model/reasoning values detected while attaching to the existing
conversation.

You can explicitly request a read-only probe with no write attempt:

```powershell
python .\examples\probe_live_contract.py `
  "https://chatgpt.com/c/<conversation-id>" `
  --attach-only `
  --output .\artifacts\gpt56-medium.json
```

A successful read-only capture reports `ATTACH_ONLY_CONTRACT_OBSERVED` when the
existing conversation exposes a detectable model contract.

Repeat for High and, when available to the account/workspace, Extra High and Pro.
The prompt defaults to `Reply exactly: probe-ok`; it is intentionally not written
to the report.

## What to compare

For each report inspect:

- `attach.detected_model`
- `attach.detected_reasoning_effort`
- `request.sent_model`
- `request.sent_reasoning_effort`
- `request.observed_model`
- `request.observed_reasoning_effort`
- `write_gate.*`
- `transport.*`
- `field_evidence`
- `verdict`

Expected full-write first-pass verdict is `CONTRACT_OBSERVED`. A read-only result
or a Turnstile-blocked result is still useful evidence for the attach-side model
contract, but it does not prove the write/stream transport contract.

A mismatch verdict is evidence, not an instruction to patch aliases immediately.
Preserve the report and first determine whether the mismatch is caused by model
routing, automatic switching, stale detector locations, or an actual backend
contract change.

## Frozen live evidence — 2026-08-07

Attach-only probes against UI-selected GPT-5.6 Sol conversations produced the
following private web contract:

| UI selection | Private model slug | Private reasoning |
| --- | --- | --- |
| Medium | `gpt-5-6-thinking` | `standard` |
| High | `gpt-5-6-thinking` | `extended` |

PR7.10 promotes `gpt-5-6-thinking` to the convenience thinking default and stores
these two observed reasoning mappings in the model capability registry.

Extra High and Pro remain unobserved in this evidence set. The registry therefore
does not invent mappings for them. Unknown explicit model slugs also remain
pass-through, and model detection remains independent of registry membership so a
future rollout can be observed before policy is updated.

## PR7.9 exit criteria

PR7.9's minimum evidence requirement was satisfied by the Medium and High captures
above. Additional modes should continue to be probed before they are added to the
registry or exposed as convenience reasoning aliases.
