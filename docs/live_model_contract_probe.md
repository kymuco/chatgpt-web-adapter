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

## Safety properties

The JSON report does **not** serialize:

- prompt or assistant response text;
- access tokens, cookies, proof tokens, or resume tokens;
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
- `transport.*`
- `field_evidence`
- `verdict`

Expected first-pass verdict is `CONTRACT_OBSERVED`.

A mismatch verdict is evidence, not an instruction to patch aliases immediately.
Preserve the report and first determine whether the mismatch is caused by model
routing, automatic switching, stale detector locations, or an actual backend
contract change.

## PR7.9 exit criteria

PR7.9 can close when we have sanitized live evidence showing the current web
contract for at least Medium and High, plus regression fixtures for any new
metadata locations discovered by the probe.

Only after that evidence should PR7.10 update the model capability registry and
public convenience modes.
