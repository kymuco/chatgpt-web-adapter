# PR8.13 — Temporary Chat production graduation

_Status: IMPLEMENTED — targeted tests and live production graduation gate pending_

_Date: 2026-08-21_

_Base contract: PR8.7 Temporary Chat characterization and T13 graduation review_

## Goal

PR8.13 implements the production `conversation_mode="temporary"` route that PR8.7 deliberately refused to graduate prematurely.

The production contract is:

```text
caller requests TEMPORARY
        ↓
BrowserOwnedProductTransport selects dedicated Temporary runtime
        ↓
ChatGPT page creates the conversation POST
        ↓
CDP Fetch pauses that POST before network dispatch
        ↓
request body proves history_and_training_disabled === true
        ↓
only then may the page-generated POST continue
        ↓
page-owned revision-safe assistant stream proves Temporary final text
        ↓
process-local lifecycle token preserves same-live-session continuation authority
```

No ordinary canonical conversation GET is promoted into Temporary finality, no direct/private product request is synthesized by CWA, and no durable fallback exists.

## Capability state during validation

The implementation route exists, but this branch intentionally does **not** claim successful production graduation before live evidence exists.

```text
temporary_chat implementation route = IMPLEMENTED
temporary_chat capability state      = UNKNOWN
production conversation_mode=temporary = ENABLED only through mode-aware browser-owned route
fallback                             = none
```

After targeted regression tests and the dedicated two-turn live gate pass, the capability may be reviewed for `AVAILABLE`.

## 1. Pre-write Temporary proof

PR8.7 proved that URL/title/UI markers alone are insufficient evidence of true Temporary product semantics. PR8.13 therefore does not authorize a Temporary mutation from `?temporary-chat=true` by itself.

The production extension enables CDP Fetch interception at request stage before the page-generated conversation POST reaches the server:

```text
Fetch.requestPaused
    ↓
parse browser-local page-generated request JSON
    ↓
history_and_training_disabled === true ?
    yes -> continue
    no  -> Fetch.failRequest(errorReason="Aborted")
```

The successful proof kind is:

```text
FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE
```

For a fresh Temporary turn the page-generated request must not already contain a conversation id. For a continuation it must contain exactly the expected live Temporary conversation id.

Failure reasons include:

```text
REQUEST_POST_DATA_MISSING
REQUEST_POST_DATA_NOT_JSON
REQUEST_PAYLOAD_NOT_OBJECT
HISTORY_AND_TRAINING_DISABLED_NOT_TRUE
FRESH_TEMPORARY_REQUEST_HAS_CONVERSATION_ID
TEMPORARY_CONTINUATION_CONVERSATION_MISMATCH
```

All such failures abort the paused product request. They do not downgrade to normal mode.

The request body is inspected only inside the extension worker. It is not exported, logged as public provenance, rewritten, fulfilled synthetically, or converted into a CWA-created private product request.

## 2. Dedicated Temporary product runtime

Durable and Temporary finality have intentionally different implementations.

### Normal/durable path

```text
BrowserOwnedProductWriteRuntime
    + canonical preflight
    + page-owned product write
    + browserless canonical HTTP finality/readback
```

This path is unchanged by PR8.13.

### Temporary path

```text
TemporaryProductWriteRuntime
    + bridge preflight
    + explicit conversation_mode="temporary"
    + process-local lifecycle authority
    + pre-write Fetch proof
    + page-owned revision-safe final assistant stream
    + no ordinary canonical conversation GET finality claim
```

Temporary provenance reports:

```text
write_plane   = BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_WRITE
readback_plane = BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_STREAM
session_plane = LIVE_TEMPORARY_PRODUCT_LIFECYCLE
completion.source = TRANSPORT_RETURN
canonical_completion_proven = false
```

This distinction is deliberate. A true Temporary conversation was already characterized in PR8.7 as returning ordinary canonical direct-id `404 / NOT_FOUND` while live and after source close.

## 3. Temporary final answer collection

PR8.13 reuses the production PR8.9/PR8.12 normalized event stream rather than adding a second response parser.

The collector accepts only the existing safe assistant text events:

```text
assistant_text_snapshot
assistant_text_delta
assistant_text_revision
```

PR8.9 already excludes hidden/tool-directed assistant content. PR8.12 may additionally classify assistant messages as `commentary` or `final`.

Selection rule:

```text
explicit channel=final wins
otherwise latest visible non-commentary assistant message wins
```

Any sequence gap or incomplete delivery fails the Temporary readback instead of silently returning a possibly truncated answer. Since ordinary canonical GET cannot reconcile a true Temporary turn, such a failure is classified as ambiguous/reconciliation-required and is never automatically retried.

## 4. Live lifecycle authority

A Temporary product conversation id is identity, not write authority.

PR8.13 creates an opaque lifecycle token for a fresh Temporary lifecycle. The token is:

- process-local;
- retained only by `TemporaryProductWriteRuntime` and the live extension worker;
- never included in public execution provenance;
- never persisted as a reconstructible lifecycle credential;
- bound to one CWA-owned Temporary tab and, after the first write, one Temporary conversation id.

Continuation requires all of the following:

```text
same process/runtime instance
same live lifecycle token
same CWA-owned Temporary tab
same Temporary conversation id
state == LIVE
```

Therefore:

```text
Temporary conversation id alone      != continuation authority
stored Temporary tab id alone         != continuation authority
runtime reassembly                    != lifecycle recreation
service-worker recreation             != lifecycle recreation
post-close /c/<id> route visibility   != continuation authority
```

A stored Temporary tab id is retained only so a later fresh lifecycle can clean up an orphaned CWA-owned tab. It does not restore the module-live token.

## 5. Explicit lifecycle end

`ChatGPTProductRuntime.end_temporary_chat()` delegates to the browser-owned Temporary lifecycle boundary.

A successful explicit end:

```text
LIVE -> ENDED
revoke live write authority
close the CWA-owned Temporary tab
clear stored cleanup tab id
clear process-local lifecycle token/conversation binding
```

After end, attempting to continue using only the previous Temporary conversation id must fail locally with:

```text
PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE
write_may_have_been_submitted = false
reconciliation_required       = false
```

No product POST may be attempted in that state.

## 6. Browser Authority and model-profile compatibility

Temporary turns retain the existing Browser Authority lease fencing surface. Each turn receives a fresh lease id and the provider is fenced for that turn.

PR8.10 model-profile selection remains upstream of the page submit. The PR8.13 live gate validates that the requested semantic profile is strictly proven before each Temporary write:

```text
FAST     -> INSTANT
BALANCED -> MEDIUM
DEEP     -> HIGH
```

Standalone CWA keeps `DEEP` as its default, so:

```powershell
cwa send "..." --temporary
```

means a fresh one-shot Temporary Chat turn with the proven product `HIGH` profile unless the caller explicitly selects another supported profile.

## 7. Standalone CLI semantics

Supported one-shot surfaces:

```powershell
cwa send "Reply with exactly: HELLO" --temporary
cwa send "..." --temporary --stream
cwa send "..." --temporary --stream --final-only
cwa send "..." --temporary --json
```

Standalone `--temporary` is intentionally fresh and one-shot. The CLI explicitly ends the Temporary lifecycle after the returned execution.

This is rejected:

```powershell
cwa send "..." --temporary --conversation <id>
```

because an external conversation id cannot carry the process-local lifecycle authority required for Temporary continuation.

Same-lifecycle multi-turn continuation is an SDK/runtime surface:

```python
runtime = assemble_product_runtime()

first = runtime.send_text_observed(
    "first",
    conversation_mode="temporary",
    model_profile="DEEP",
)

second = runtime.send_text_observed(
    "second",
    conversation=first.response.conversation.conversation_id,
    conversation_mode="temporary",
    model_profile="DEEP",
)

runtime.end_temporary_chat()
```

## 8. PR8.7 graduation blockers closed by implementation

PR8.7 T13 denied `AVAILABLE` because eight production pieces were missing. PR8.13 maps them as follows:

| PR8.7 blocker | PR8.13 production mechanism |
| --- | --- |
| 1. no mode-aware Temporary ProductWriteTransport route | browser-owned transport explicitly dispatches `conversation_mode="temporary"` to `TemporaryProductWriteRuntime` |
| 2. no pre-mutation observed Temporary proof | CDP Fetch pauses the page-generated POST and proves `history_and_training_disabled=true` before continuing it |
| 3. no same-lifecycle continuation authority | process-local token + exact conversation id + exact live Temporary tab binding |
| 4. no `PRODUCT_MODE_OBSERVATION` provenance | successful Temporary executions emit proven requested/observed `TEMPORARY` mode provenance |
| 5. no proven LIVE lifecycle provenance | successful executions emit `ProductTemporaryLifecycleProvenance(state=LIVE, live_write_authority_proven=true)` |
| 6. no Temporary-specific finality | PR8.9/PR8.12 page-owned revision-safe final assistant stream, no canonical GET claim |
| 7. no lifecycle disposal/loss transition | explicit end, tab-close invalidation, turn-failure authority invalidation |
| 8. no integrated live production validation | dedicated `temporary_chat_production_live_gate_pr8_13` two-turn graduation gate |

## 9. Dedicated production live gate

The gate performs **exactly two intended product writes** in one fresh runtime/lifecycle.

Run:

```powershell
python -m chatgpt_web_adapter.temporary_chat_production_live_gate_pr8_13 `
  --acknowledge-live-writes
```

Default profile is `DEEP -> HIGH`.

The gate proves this matrix:

```text
T1 fresh Temporary product turn
   exact expected answer
   exactly one paused conversation POST
   history_and_training_disabled=true pre-write proof
   requested/observed TEMPORARY provenance
   LIVE lifecycle provenance
   page-owned non-canonical finality
   strict DEEP/HIGH selection before write

T2 same-runtime continuation
   same Temporary product conversation id
   same live lifecycle authority
   exact continuation request identity proof
   fresh Browser Authority lease
   exact expected answer
   strict DEEP/HIGH selection before write

while lifecycle LIVE
   ordinary canonical direct-id read = 404 / NOT_FOUND

explicit lifecycle end
   state becomes NOT_ESTABLISHED locally
   live token absent
   owned Temporary tab closed

after source close
   ordinary canonical direct-id read = 404 / NOT_FOUND

controlled third continuation attempt
   blocked before product write
   PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE
   write_may_have_been_submitted=false
   reconciliation_required=false
```

Successful summary must include:

```text
fresh_temporary_prewrite_proven              = true
same_lifecycle_continuation_proven           = true
same_temporary_conversation_identity_proven  = true
canonical_while_live_not_found               = true
canonical_after_close_not_found              = true
explicit_lifecycle_end_proven                = true
post_end_continuation_blocked_before_write   = true
page_owned_temporary_finality_proven          = true
durable_fallback                             = false
automatic_write_retry                        = false
```

## 10. Focused regression gate

Before interpreting live evidence, run the PR8.13 and neighboring invariants:

```powershell
python -m pytest `
  tests/test_temporary_product_extension_pr8_13.py `
  tests/test_temporary_product_runtime_pr8_13.py `
  tests/test_temporary_chat_production_no_durable_fallback.py `
  tests/test_revision_safe_text_delivery_pr8_9.py `
  tests/test_standalone_send_cli.py `
  -q
```

Then run the full suite:

```powershell
python -m pytest -q
```

Do not classify PR8.13 as fully green until these results are actually observed.

## 11. Graduation decision rule

The implementation itself is not sufficient to claim `AVAILABLE`.

Graduation requires:

```text
focused regression gate PASS
full suite PASS
dedicated two-turn production live gate PASS
normal durable send regression PASS
```

After those gates, review the browser-owned capability declaration and change:

```text
temporary_chat = UNKNOWN
```

to:

```text
temporary_chat = AVAILABLE
```

only if the observed evidence matches the contract above.

## 12. Safety properties retained

PR8.13 does not weaken the ordinary product bridge:

```text
normal durable canonical preflight/readback remains unchanged
normal mode never inherits Temporary identity/lifecycle/token
Temporary mode never inherits normal/durable authority
Temporary failure never silently retries a product write
Temporary mode has no durable fallback
page-generated request body remains browser-local
CWA does not synthesize a private Temporary backend request
conversation id remains identity, not authority
```

The PR8.7 rule remains the core invariant:

```text
identity != permission
```

PR8.13 converts that governance rule into an actual production execution boundary.
