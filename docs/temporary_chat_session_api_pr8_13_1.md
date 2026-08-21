# PR8.13.1 — Temporary Chat session-only public API

_Status: CLOSED / PASS_

_Date: 2026-08-21_

_Base: PR8.13 Temporary Chat Production Graduation — CLOSED / PASS_

## Goal

PR8.13 proved the browser-owned Temporary write route and lifecycle semantics. PR8.13.1 aligns the public Python API with that evidence: Temporary Chat is a **live runtime session**, not a durable conversation handle.

The public continuation contract is:

```python
runtime.send_text_observed("first", conversation_mode="temporary")
runtime.send_text_observed("second", conversation_mode="temporary")
runtime.send_text_observed("third", conversation_mode="temporary")

runtime.end_temporary_chat()
```

The caller never passes a Temporary conversation id between turns.

## Public rule

For `conversation_mode="temporary"`:

```text
conversation omitted + no LIVE Temporary lifecycle
    -> create a fresh Temporary session

conversation omitted + LIVE Temporary lifecycle
    -> continue the same live session
    -> transport uses its private stored routing identity internally

conversation=<anything>
    -> fail closed before Temporary low-level write
```

Explicit id-based continuation is rejected with:

```text
PR8_13_1_TEMPORARY_EXPLICIT_CONVERSATION_FORBIDDEN
write_may_have_been_submitted = false
reconciliation_required       = false
```

## Authority model

```text
public authority
    = same live ChatGPTProductRuntime / BrowserOwnedProductTransport lifecycle

private routing metadata
    = ephemeral Temporary conversation id held inside the live runtime

conversation id alone
    != continuation authority
    != attach authority
    != reopen authority
    != recovery authority
```

The low-level `TemporaryProductWriteRuntime` still carries the ephemeral routing id because the ChatGPT backend requires it for the next POST in the same live session. That remains an implementation detail, not a public handle.

## Lifecycle

A runtime with no active Temporary lifecycle starts a new Temporary session on the next Temporary send.

While the lifecycle is LIVE, another Temporary send with no `conversation` argument continues that same session.

After:

```python
runtime.end_temporary_chat()
```

the lifecycle becomes `NOT_ESTABLISHED`. The next Temporary send is fresh.

A process/runtime restart does not restore the prior Temporary lifecycle.

## Normal conversation isolation

Normal durable conversations keep the existing API:

```python
runtime.send_text_observed(
    "continue durable conversation",
    conversation="<durable-conversation-id>",
    conversation_mode="normal",
)
```

PR8.13.1 changes only Temporary public routing.

## Browser and product semantics

PR8.13.1 does **not** modify:

- the Chrome extension,
- the CDP Fetch prewrite fence,
- `history_and_training_disabled === true` proof,
- page-owned Temporary finality,
- model profile selection,
- Browser Authority Lease behavior,
- Temporary tab ownership,
- automatic retry policy,
- durable fallback policy,
- canonical read behavior.

The graduated PR8.13 browser/product path remains the execution mechanism.

## Governance additions

`BrowserOwnedProductTransport.governance()` declares:

```text
temporary_chat_public_continuation_model = LIVE_RUNTIME_SESSION_ONLY
temporary_chat_public_conversation_argument_supported = false
temporary_chat_same_runtime_implicit_continuation = true
temporary_chat_explicit_conversation_argument_fail_closed_before_write = true
temporary_chat_internal_routing_identity_is_public_authority = false
temporary_chat_new_session_after_explicit_end = true
```

## Regression evidence

Executed on 2026-08-21:

```text
focused PR8.13.1 regression      8 passed in 0.11s
relevant Temporary/CLI suite    28 passed in 0.18s
full repository suite           1230 passed in 22.82s
```

All regression gates passed.

## Production live evidence

Dedicated gate:

```powershell
python -m chatgpt_web_adapter.temporary_chat_session_api_live_gate_pr8_13_1 `
  --acknowledge-live-writes
```

Successful run:

```text
ok                                      = true
product_write_budget                    = 2
product_write_completions               = 2
automatic_write_retry                   = false
durable_fallback                        = false
public_continuation_model               = LIVE_RUNTIME_SESSION_ONLY
explicit_conversation_argument_supported = false
profile                                 = DEEP
target_product_mode                     = HIGH
```

Turn 1:

```text
response                                = CWA_PR8_13_1_SESSION_FIRST_OK
temporary_mode_proven                   = true
temporary_prewrite_proof                = FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
temporary_continuation_identity_proven  = false
selected_mode_after                     = HIGH
conversation_write_before_selection     = false
```

Turn 2 was issued through the public API **without** `conversation=<id>` and proved same-runtime continuation:

```text
response                                = CWA_PR8_13_1_SESSION_CONTINUE_OK
temporary_mode_proven                   = true
temporary_prewrite_proof                = FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
temporary_continuation_identity_proven  = true
selected_mode_after                     = HIGH
conversation_write_before_selection     = false
```

Both turns reported the same private routing identity:

```text
6a884544-0df0-83eb-8cd5-cc7418da6343
```

The public explicit-id attempt was then rejected locally:

```text
blocked_before_product_write = true
write_may_have_been_submitted = false
reconciliation_required = false
error = PR8_13_1_TEMPORARY_EXPLICIT_CONVERSATION_FORBIDDEN
```

Explicit lifecycle end produced:

```text
state = NOT_ESTABLISHED
conversation_id = null
token_present = false
token_exported = false
```

The live summary therefore proved:

```text
fresh_temporary_session_proven                      = true
implicit_same_runtime_continuation_proven            = true
stable_internal_routing_identity_proven              = true
explicit_conversation_argument_blocked_before_write  = true
explicit_lifecycle_end_proven                        = true
conversation_id_is_not_public_authority              = true
automatic_write_retry                                = false
durable_fallback                                     = false
```

## Observed fail-closed startup abort

Immediately before the successful live run, one independent invocation exited with:

```text
TemporaryProductWriteRuntimeError
CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED
```

No automatic retry or durable fallback occurred.

The PR8.13 extension explicitly uses CDP `Fetch.failRequest(..., errorReason="Aborted")` when a page-generated conversation request fails the Temporary prewrite fence. Therefore this observation is **consistent with a fail-closed startup/activation race**, for example a newly opened `?temporary-chat=true` page producing a request before its frontend Temporary state has fully stabilized.

The exact root cause of that individual abort is not proven because the generic turn error does not currently surface the underlying PR8.13 `modeViolation` reason. The successful second invocation proves the PR8.13.1 session-only API contract, while the first invocation remains a reliability/diagnostic observation for a follow-up Temporary startup-readiness hardening PR.

Importantly, the observed failure mode was safe:

```text
silent durable fallback = none
automatic write retry    = none
```

## Graduation decision

All PR8.13.1 graduation conditions are satisfied:

```text
focused regression                      PASS
relevant Temporary/CLI regression       PASS
full suite                              PASS
session-only two-turn live gate         PASS
implicit same-runtime continuation      PASS
explicit id attempt blocked pre-write   PASS
explicit lifecycle end                  PASS
```

**PR8.13.1 — CLOSED / PASS.**

PR8.13 remains the production Temporary capability graduation record. PR8.13.1 is the public session-only API alignment layer on top of it.
