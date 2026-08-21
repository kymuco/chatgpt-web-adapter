# PR8.13.2 — Temporary fresh-session readiness stabilization and prewrite-abort diagnostics

_Status: CLOSED / PASS_

_Date: 2026-08-21_

_Base: PR8.13.1 Temporary Chat session-only public API — CLOSED / PASS_

## Motivation

PR8.13.1 closed with a successful production live gate, but the immediately preceding independent invocation failed with:

```text
TemporaryProductWriteRuntimeError
CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED
```

The next invocation succeeded fully. No automatic retry or durable fallback occurred.

The exact cause of that individual abort was not observable from the old generic error. PR8.13.2 therefore hardens two boundaries without weakening the graduated Temporary safety model:

1. a newly-created Temporary product page receives a bounded, read-only stabilization window before its first submit;
2. a future `net::ERR_ABORTED` is classified according to the prewrite observation phase instead of remaining opaque.

## Non-goal: changing Temporary authority

PR8.13.2 does **not** make URL state, DOM state, composer state, or UI control state authoritative.

The only authority for a Temporary product write remains the PR8.13 request-stage proof:

```text
Fetch.requestPaused
    -> page-generated conversation POST
    -> request.postData parsed browser-locally
    -> history_and_training_disabled === true
    -> continuation conversation_id matches when applicable
    -> Fetch.continueRequest
```

If that proof fails, the existing PR8.13 fence still executes:

```text
Fetch.failRequest(errorReason="Aborted")
```

No PR8.13.2 readiness observation can override that fence.

## Fresh-session readiness hint

Only a **fresh** Temporary turn (`expectedConversationId == null`) is stabilized.

The readiness overlay samples:

```text
Temporary URL hint:
    ?temporary-chat=true

composer state:
    queryComposerReadiness(debuggee).ready == true

Temporary control hint, when available:
    explicit selected=false blocks readiness
    explicit selected=true permits the short selected-state path
```

The control hint uses the bounded PR8.7 Temporary-control observer when that observer remains available. It is a readiness hint only.

### Two bounded success paths

If the Temporary control is found unambiguously and selected:

```text
2 consecutive ready samples
    -> TEMPORARY_CONTROL_SELECTED_STABLE
```

If the UI control cannot be used as stable evidence because selectors/product UI changed, the overlay requires a continuous stable window:

```text
URL Temporary hint true
composer ready
no explicit Temporary-control false state
3+ consecutive ready samples
>= 750 ms continuously stable
    -> TEMPORARY_URL_COMPOSER_STABLE_HINT
```

Overall readiness is bounded by 5 seconds. Timeout fails **before product write**:

```text
PR8_13_2_TEMPORARY_FRESH_READINESS_TIMEOUT:<reason>
```

There is no retry.

## Continuation isolation

PR8.13.2 does not delay established same-session continuation turns.

```text
fresh Temporary lifecycle
    -> readiness stabilization applies

LIVE Temporary continuation
    -> no PR8.13.2 startup delay
    -> existing PR8.13 continuation identity fence applies
```

## Abort diagnostics

PR8.13.2 records only bounded state derived from the existing Temporary turn context:

```text
modeViolation
prewriteProofKind
pausedConversationWriteCount
fresh readiness kind/wait metadata
```

Raw request bodies are not exported.

When the underlying browser-native turn reports:

```text
CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED
```

the error is classified as one of:

```text
PR8_13_2_TEMPORARY_PREWRITE_ABORT:<modeViolation>
PR8_13_2_TEMPORARY_ABORT_AFTER_PREWRITE_PROOF:<proofKind>
PR8_13_2_TEMPORARY_ABORT_WITHOUT_RETAINED_PROOF:paused=<count>
PR8_13_2_TEMPORARY_ABORT_BEFORE_FETCH_OBSERVATION
```

The original browser error remains appended to the diagnostic string. This classification does not retry, reconcile, reopen, attach, or convert the turn to durable mode.

## Browser/extension layering

The overlay is:

```text
service_worker_temporary_startup_readiness_pr8_13_2.js
```

and loads after:

```text
service_worker_temporary_chat_production_pr8_13.js
service_worker_temporary_session_identity_pr8_13.js
service_worker_temporary_fresh_identity_flush_pr8_13.js
```

Therefore the previously proven Temporary production route and identity repair remain underneath it.

## Regression evidence

Executed on 2026-08-21:

```text
focused PR8.13.2 regression      6 passed in 0.08s
relevant Temporary regression   31 passed in 0.18s
full repository suite         1236 passed in 22.82s
```

All regression gates passed.

## Production live evidence

Dedicated gate:

```powershell
python -m chatgpt_web_adapter.temporary_chat_startup_readiness_live_gate_pr8_13_2 `
  --acknowledge-live-writes
```

The first live invocation after the PR8.13.2 extension reload passed:

```text
ok                         = true
product_write_budget       = 2
product_write_completions  = 2
fresh_lifecycle_budget     = 2
fresh_lifecycle_completions= 2
automatic_write_retry      = false
durable_fallback           = false
profile                    = DEEP
target_product_mode        = HIGH
```

### Fresh lifecycle #1

```text
response                                = CWA_PR8_13_2_FRESH_START_ONE_OK
conversation_id                         = 6a885198-4d0c-83eb-ac60-d377d6dc5bfe
browser_authority_lease_id              = 39df37d5-ec4f-447c-b9a1-444cb53a929d
temporary_mode_proven                   = true
temporary_prewrite_proof                = FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
temporary_continuation_identity_proven  = false
temporary_paused_conversation_write_count = 1
stream_observation_count                = 2
selected_mode_after                     = HIGH
conversation_write_before_selection     = false
```

Live lifecycle state was proven as:

```text
state          = LIVE
token_present  = true
token_exported = false
```

Explicit end then produced:

```text
state           = NOT_ESTABLISHED
conversation_id = null
token_present   = false
token_exported  = false
```

### Fresh lifecycle #2

Immediately afterwards a second independent fresh Temporary lifecycle passed:

```text
response                                = CWA_PR8_13_2_FRESH_START_TWO_OK
conversation_id                         = 6a8851a5-6fec-83eb-a955-8e1e4341d1c8
browser_authority_lease_id              = c990b49b-75a7-4d49-8b0c-e4f27f5f16d6
temporary_mode_proven                   = true
temporary_prewrite_proof                = FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
temporary_continuation_identity_proven  = false
temporary_paused_conversation_write_count = 1
stream_observation_count                = 2
selected_mode_after                     = HIGH
conversation_write_before_selection     = false
```

The second lifecycle also ended cleanly to `NOT_ESTABLISHED`.

The two fresh lifecycles used different private routing identities and different Browser Authority leases. This proves that the second turn was not an accidental continuation or reuse of the first Temporary lifecycle.

## Live summary

```text
two_independent_fresh_temporary_lifecycles_proven = true
fresh_routing_identity_rotated                     = true
fresh_browser_authority_lease_rotated              = true
each_fresh_turn_prewrite_proven                    = true
each_fresh_turn_exactly_one_product_write          = true
explicit_end_between_fresh_lifecycles_proven       = true
automatic_write_retry                              = false
durable_fallback                                   = false
```

The previously observed opaque startup abort from PR8.13.1 did not reproduce in this first PR8.13.2 live invocation. This does not prove that such a product-side transient can never recur; it proves that the readiness hardening preserves the Temporary safety model and successfully supports two consecutive independent fresh-session starts under the tested production conditions. If a future abort occurs, PR8.13.2 now has bounded phase diagnostics for classification.

## Graduation decision

All PR8.13.2 graduation conditions are satisfied:

```text
focused readiness/diagnostic regression    PASS
relevant Temporary regression              PASS
full repository suite                      PASS
two-independent-fresh-session live gate    PASS
fresh routing identity rotation            PASS
fresh Browser Authority lease rotation     PASS
one paused product write per lifecycle     PASS
explicit end between lifecycles            PASS
no automatic retry                         PASS
no durable fallback                        PASS
```

**PR8.13.2 — CLOSED / PASS.**

PR8.13 remains the Temporary capability graduation record. PR8.13.1 remains the session-only public API record. PR8.13.2 is the fresh-session reliability and abort-diagnostics hardening layer on top of them.
