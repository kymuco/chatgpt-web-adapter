# PR8.14 — Stable Product Inspection CLI, Product-Native Model Profile Aliases and Exit-Code Contract

_Status: CLOSED / PASS_

_Date: 2026-08-21_

_Base: `main` after integration PR #48 (`421e0b4bc4a92b7b23bfb28202907a6d5d10f1f9`)_

## Scope

PR8.14 starts CWA 0.2 stabilization. It adds a stable public CLI front controller without changing the proven product transport, browser write path, canonical read path, retry policy, or fallback policy.

Both console entry points route through `chatgpt_web_adapter.cli_v02:main`. The older `chatgpt_web_adapter.cli` remains the compatibility runner underneath it.

## Stable inspection commands

```powershell
cwa status
cwa status --conversation <id-or-url>
cwa capabilities
cwa messages <id-or-url>
```

All three commands are read-only and support `--json`.

`status` reports the existing `ProductRuntimeHealth`. A valid inspection that observes an unhealthy runtime returns exit `1`; it is not treated as an operational exception.

`capabilities` reports the existing evidence-backed `ProductCapabilities` plus the public model-profile naming contract.

`messages` uses `ChatGPTProductRuntime.get_messages()` and returns normalized `ChatMessage.to_dict()` items from the canonical current branch. It supports `--limit`, repeated `--role`, and `--include-empty`.

The artifact boundary is explicit:

```text
messages = inspect canonical product state now
snapshot = create a deterministic ConversationSnapshot artifact on disk
export   = broader/raw archival representation

messages != snapshot != export
```

## Product-native model profile aliases

The already-proven mapping is accepted directly by the public CLI:

```text
FAST     <-> INSTANT
BALANCED <-> MEDIUM
DEEP     <-> HIGH
```

Product-native names are first-class input:

```powershell
cwa send "..." --profile INSTANT
cwa send "..." --profile MEDIUM
cwa send "..." --profile HIGH
```

Existing semantic names remain compatible. Input normalizes before the existing selector:

```text
INSTANT -> FAST     -> product INSTANT
MEDIUM  -> BALANCED -> product MEDIUM
HIGH    -> DEEP     -> product HIGH
```

The public default is `HIGH`; the existing internal semantic key remains `DEEP`. No selector, slider-index, Browser Authority, prewrite selection, or provenance semantics change. `MAX` remains unmapped because no fourth product state is proven.

## Machine-readable schema

Successful inspection commands use `schema = 1`, `command`, and `ok`.

`status` adds `transport` and `health`; `capabilities` adds `transport`, `product`, and `model_profiles`; `messages` adds `conversation_id`, `count`, and `messages`.

For `--json`, post-parse failures use the same schema with `ok=false` and an `error` object. Bounded structured exception fields are included when available. Argparse syntax failures remain normal argparse stderr failures because no parsed command payload exists yet.

## Exit-code contract

```text
0 = success
1 = valid inspection observed unhealthy/unavailable state
2 = CLI usage or input validation failure
3 = product/runtime operational failure
4 = ambiguous write outcome requiring reconciliation
```

Exit `4` is selected only when structured exception state reports `reconciliation_required == true`; message text is not used to infer ambiguity.

## Compatibility and safety

Existing `auth`, `snapshot`, `send`, `browser-native`, and `runtime` commands continue through the compatibility runner. Nested `runtime status` remains supported, while the new top-level inspection commands are the intended 0.2-facing surface.

The new commands do not call `send_text()` or `send_text_observed()` and introduce no automatic write retry or fallback.

## Regression evidence

User-reported on 2026-08-21:

```text
focused PR8.14                10 passed in 0.21s
relevant CLI/runtime          27 passed in 0.25s
full repository suite       1246 passed in 23.31s
```

## Production CLI smoke evidence

`cwa capabilities --json` passed with:

```text
ok = true
schema = 1
default profile = HIGH
accepted = INSTANT, MEDIUM, HIGH, FAST, BALANCED, DEEP
HIGH -> DEEP
MEDIUM -> BALANCED
INSTANT -> FAST
max_mapped = false
```

`cwa status --json` passed with:

```text
ok = true
health.ready = true
reason = READY_FOR_BROWSER_OWNED_WRITE
bridge_available = true
extension_connected = true
automatic_write_retry = false
fallback_transport = null
```

A controlled public alias write passed:

```text
cwa send "Reply with exactly: CWA_PR8_14_HIGH_ALIAS_OK" --profile HIGH --json
```

Observed result:

```text
ok = true
text = CWA_PR8_14_HIGH_ALIAS_OK
backend_status = 200
completion.source = CANONICAL_READBACK
canonical_completion_proven = true
write_event_observed = true
conversation_mode = NORMAL
```

This smoke proves that the public CLI accepts `HIGH` and dispatches successfully through the existing profile-selection path. The generic send JSON does not itself expose `selected_mode_after=HIGH`; browser-side HIGH selection remains covered by the previously frozen PR8.10 live evidence. PR8.14 does not alter that selector.

A direct read-only production smoke also passed for the same conversation:

```powershell
cwa messages 6a8863ef-a89c-83eb-afd5-02389d6fc849 --json
```

The returned schema, conversation id, normalized user message, assistant response `CWA_PR8_14_HIGH_ALIAS_OK`, and message count matched the PR8.14 contract. No product write was performed by this inspection command.

## Closure

PR8.14 is closed as PASS. The stable public surface now includes read-only `status`, `capabilities`, and `messages`; product-native profile names are first-class aliases; and CLI exit classes are frozen for the 0.2 stabilization line.
