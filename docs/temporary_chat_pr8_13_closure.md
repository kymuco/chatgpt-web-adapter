# PR8.13 Temporary Chat production graduation — closure

_Status: CLOSED / PASS — `temporary_chat = AVAILABLE`_

_Date: 2026-08-21_

This document is the authoritative closure record for PR8.13 and supersedes the validation-state wording in `temporary_chat_production_graduation_pr8_13.md`. PR8.7 documents remain historical records of the earlier characterization and the then-correct decision not to expose a production Temporary route.

## Decision

The browser-owned product transport now declares:

```text
temporary_chat = AVAILABLE
production conversation_mode="temporary" = ENABLED
fallback = none
automatic write retry = false
```

Graduation is based on an integrated production live gate plus a full regression suite, not on capability metadata alone.

## Production live evidence

The dedicated PR8.13 gate completed exactly two Temporary product writes in one live lifecycle:

```text
product_write_budget      = 2
product_write_completions = 2
profile                   = DEEP
target_product_mode       = HIGH
automatic_write_retry     = false
```

Both writes returned the exact expected assistant text.

The first write proved:

```text
requested product mode                     HIGH
selected product mode after proof           HIGH
conversation write before selection         false
temporary mode proven                       true
temporary prewrite proof                    FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
temporary continuation identity proven      false
paused conversation write count             1
page-owned stream observation present       true
canonical completion proven                 false
readback plane                              BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_STREAM
```

The second write proved the same mode/prewrite/finality invariants and additionally:

```text
temporary continuation identity proven      true
same Temporary product conversation id      true
same live Temporary lifecycle               true
```

The observed session-local product routing identity was stable across the two live turns. It is diagnostic/routing metadata only; it is not ordinary canonical conversation authority.

## Lifecycle and non-durability evidence

While the original Temporary lifecycle was still live:

```text
lifecycle state                  LIVE
process-local token present      true
token exported                   false
ordinary canonical GET           404 / NOT_FOUND
canonical payload read calls     1
write performed by read probe    false
attach performed                 false
navigation performed             false
```

After explicit lifecycle end:

```text
lifecycle state                  NOT_ESTABLISHED
conversation id in lifecycle     null
process-local token present      false
ordinary canonical GET           404 / NOT_FOUND
```

A post-end continuation attempt using the known Temporary product conversation id was blocked locally before product mutation:

```text
PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE:
conversation id alone does not grant continuation authority

write_may_have_been_submitted = false
reconciliation_required       = false
```

Therefore:

```text
Temporary product conversation id
    != ordinary canonical conversation
    != durable attach handle
    != post-close write authority

LIVE process-local lifecycle authority
    + expected session routing identity
    = allowed same-live-session continuation
```

The route is session-scoped. Runtime/tab reconstruction does not recreate Temporary write authority.

## Prewrite safety boundary

For every Temporary write, the ChatGPT page generates the conversation request. CDP Fetch pauses the request before network dispatch. CWA permits the request to continue only after browser-local inspection proves:

```text
history_and_training_disabled === true
```

For a live continuation, the page-generated request must also carry the expected session routing identity. Failure aborts the request before product mutation.

CWA does not export or rewrite the raw request body.

## Finality boundary

Temporary finality is intentionally not represented as ordinary canonical conversation completion.

```text
Temporary readback/finality plane
    = BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_STREAM

canonical completion proven
    = false
```

Revision-safe assistant streaming remains the authoritative page-owned final text surface for the live Temporary turn. Ordinary canonical GET remains expected to return 404 for the observed Temporary product identity.

## Model-profile compatibility

Both live Temporary writes independently proved the standard standalone default profile requirement:

```text
DEEP -> HIGH
selected_mode_after_proven       = true
conversation_write_before_selection = false
```

PR8.13 therefore preserves PR8.10 strict prewrite model-profile selection.

## Streaming compatibility

Temporary turns reuse the PR8.9/PR8.12 event surfaces rather than defining a parallel stream protocol:

```text
assistant_text_snapshot
assistant_text_delta
assistant_text_revision
activity_started
activity_text_snapshot
activity_text_delta
activity_text_revision
activity_completed
```

The Temporary runtime reconstructs the final assistant answer from the page-owned revision-safe stream and does not invent canonical finality.

## Regression evidence

After the live gate and compatibility repairs, the complete local suite passed:

```text
1222 passed in 23.19s
```

The final compatibility repair restored the frozen PR8.9 governance metadata field:

```text
streaming_reconciliation_states = [
    EXACT_MATCH,
    CANONICAL_EXTENDS_STREAM,
    STREAM_REVISED_BY_CANONICAL,
    STREAM_INCOMPLETE,
    UNAVAILABLE,
]
```

No browser/Temporary write semantics were changed by that repair.

## Capability graduation

The former validation state:

```text
temporary_chat = UNKNOWN
```

is now graduated to:

```text
temporary_chat = AVAILABLE
```

The supporting governance now states:

```text
temporary_chat_product_runtime_selection_supported = true
temporary_chat_capability_live_graduated            = true
temporary_chat_durable_fallback                     = false
temporary_chat_automatic_write_retry                = false
temporary_chat_canonical_get_required               = false
temporary_chat_conversation_id_alone_is_authority   = false
temporary_chat_runtime_reassembly_restores_lifecycle = false
temporary_chat_tab_recreation_restores_lifecycle    = false
temporary_chat_explicit_lifecycle_end_supported     = true
```

## CLI surface

Standalone one-shot Temporary usage remains:

```powershell
cwa send "..." --temporary
cwa send "..." --temporary --stream
cwa send "..." --temporary --stream --final-only
```

Standalone Temporary sends explicitly end their owned lifecycle after completion.

The SDK/runtime surface supports live-session continuation only while the same process-local Temporary lifecycle remains established. An id by itself is never sufficient authority.

## Closure

```text
PR8.13 implementation                         PASS
prewrite Temporary proof                     PASS
page-owned Temporary finality                 PASS
same-live-lifecycle two-turn continuation     PASS
strict DEEP -> HIGH selection                 PASS
canonical 404 while live                     PASS
canonical 404 after close                    PASS
explicit lifecycle end                       PASS
post-end continuation blocked before write   PASS
no automatic retry                           PASS
no durable fallback                          PASS
full regression                              1222 PASS
capability state                             AVAILABLE

PR8.13 = CLOSED / PASS
```
