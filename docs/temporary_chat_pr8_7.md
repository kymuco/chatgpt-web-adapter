# PR8.7 — Temporary Chat target production semantics and lifecycle governance

_Status: target contract derived from live characterization; production Temporary Chat remains capability-gated_

_Date: 2026-08-16_

_Base evidence: `docs/temporary_chat_pr8_7_live_characterization.md`_

## 1. Goal

PR8.7 defines how Temporary Chat should eventually appear in `ChatGPTProductRuntime` without forcing it into ordinary durable-chat semantics.

The desired caller-facing shape remains:

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

but production Temporary Chat is **not enabled by this document**.

Current capability:

```text
temporary_chat = UNKNOWN
production conversation_mode="temporary" = NOT ENABLED
```

The remaining work is governance, provenance, isolation, and lifecycle hardening, not another attempt to reinterpret Temporary as a normal durable conversation.

## 2. Evidence-backed product model

Live characterization established this lifecycle:

```text
TRUE TEMPORARY SOURCE SESSION
        |
        +-- turn #1 -> HTTP 200
        +-- turn #2 -> HTTP 200
        +-- same Temporary product conversation ID
        +-- visible-turn state grows 0 -> 2 -> 4
        +-- exact ID remains absent from ordinary history
        |
        v
SOURCE LIFECYCLE ENDS
        |
        +-- ordinary canonical GET /conversation/<id> -> 404
        +-- direct product /c/<id> may stably recover completed turns
        +-- controlled continuation write -> HTTP 404
```

Therefore Temporary is:

```text
a live multi-turn product conversation
with lifecycle-bounded write authority
```

It is **not**:

```text
a one-shot turn
an ordinary durable history conversation
an ordinary canonical-conversation resource
a post-close attach/reopen-write handle
```

## 3. Core production invariant

Production must model authority separately from identity.

```text
temporary_product_conversation_id
        !=
temporary_live_write_authority
```

A remembered Temporary product conversation ID may identify product state, but live evidence shows that identity alone is not sufficient to continue after the original Temporary lifecycle ends.

The production rule is:

> A Temporary continuation is authorized only while the runtime still owns a live, mode-proven Temporary lifecycle for that conversation. The ID alone is never enough.

## 4. Target lifecycle state machine

The runtime should reason about Temporary using a lifecycle state machine, not ordinary durable-conversation assumptions.

```text
REQUESTED_TEMPORARY
        |
        | prove Temporary mode before first mutation
        v
LIVE_TEMPORARY
        |
        | zero or more sequential page-owned turns
        | same Temporary product conversation identity
        | each write individually finalized
        |
        +-----------------------------+
        | source disposal / loss      |
        | lifecycle expiry            |
        | browser/runtime recreation  |
        | mode proof lost             |
        v                             |
TEMPORARY_LIFECYCLE_ENDED <-----------+
        |
        +-- write authority = NONE
        +-- ordinary canonical read = NOT PROMISED
        +-- history visibility = NOT PROMISED
        +-- attach/reopen continuation = NOT PROMISED
```

A separate diagnostic observation may exist:

```text
POST_CLOSE_PRODUCT_ROUTE_RECOVERABLE
```

because `/c/<id>` was observed to hydrate completed turns after close. That is an **observed product state**, not a production authority state.

The production state machine therefore must not transition from `TEMPORARY_LIFECYCLE_ENDED` back to writable merely because `/c/<id>` displays old content.

## 5. First Temporary send

A future explicit request:

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

must use a dedicated Temporary lifecycle boundary.

Before the first write:

```text
requested_mode = TEMPORARY
        |
        v
obtain/select Temporary-capable page context
        |
        v
prove observed product mode
        |
        +-- cannot prove -> FAIL CLOSED, ZERO WRITE
        |
        v
perform exactly one page-owned write
        |
        v
prove response/finality through the live page-owned turn path
        |
        v
return Temporary provenance + live continuation handle/state
```

Forbidden behavior:

```text
Temporary selection uncertain
        ->
send ordinary durable chat anyway
```

No hidden fallback is allowed.

## 6. Live multi-turn continuation

Temporary is explicitly multi-turn while the lifecycle remains live.

A production continuation should conceptually be equivalent to:

```python
runtime.send(
    next_prompt,
    conversation=temporary_ref,
    conversation_mode="temporary",
)
```

where `temporary_ref` carries or resolves to both:

```text
temporary product conversation identity
+
live Temporary lifecycle binding
```

The exact public type is still an implementation decision. It may be an ordinary-looking `ConversationRef` with additional provenance/lifecycle metadata, or a dedicated Temporary reference. What matters is the invariant:

```text
same ID without live lifecycle binding -> NOT AUTHORIZED
```

A live continuation must prove, before mutation:

```text
requested_mode = TEMPORARY
observed_mode  = TEMPORARY
lifecycle      = LIVE
conversation identity matches the bound live session
```

Then the runtime may perform the next page-owned turn.

## 7. Lifecycle termination is a write-authority boundary

Live evidence shows:

```text
source open:
    sequential continuation -> HTTP 200

source closed:
    controlled continuation -> HTTP 404
```

Production therefore must treat loss/termination of the live Temporary source as an authority boundary.

After `TEMPORARY_LIFECYCLE_ENDED`:

```text
runtime.send(... same temporary id ...)
```

must not automatically:

```text
open /c/<id>
reattach
retry as normal chat
create a durable replacement
create a new Temporary chat under the old identity
```

Instead the operation fails closed with an explicit lifecycle/continuation error unless a future independent product contract proves a supported recreation mechanism.

## 8. Identity semantics

The current probe field name `ephemeral_backend_conversation_id` is historically useful but semantically too narrow.

Live evidence supports the conceptual name:

```text
temporary_product_conversation_id
```

because the same ID:

```text
survived multiple live turns
identified a stable direct product route after close
recovered all completed turns after close
```

However it must **not** be promoted to:

```text
ordinary_canonical_conversation_id
```

because the existing ordinary canonical conversation endpoint returned `404` both while live and after source close.

Recommended production provenance:

```text
conversation_identity.kind = "temporary_product_conversation"
conversation_identity.value = <id>
conversation_identity.ordinary_canonical_readable = false/unknown
```

Exact field names remain implementation work for T9; the semantic distinction is mandatory.

## 9. Finality and observation

Ordinary durable-chat finality currently relies heavily on the canonical observation plane.

Temporary cannot require the same mechanism because:

```text
GET /backend-api/conversation/<temporary-id> -> 404
```

while the live page-owned turn itself succeeds and visibly completes.

Therefore production Temporary finality must be based on the browser-owned page turn lifecycle unless a separate authoritative Temporary observation endpoint is later discovered.

Required separation:

```text
WRITE AUTHORITY
    page-owned Temporary product context

LIVE TURN FINALITY
    page-owned response/composer/turn evidence

ORDINARY CANONICAL CONVERSATION READ
    unsupported/not promised for Temporary
```

Temporary success must not synthesize canonical-read evidence that was not observed.

## 10. Ordinary history semantics

Live evidence repeatedly showed:

```text
exact /c/<temporary-id> ordinary history enumeration
    = STABLE_ABSENT
```

including while a two-turn Temporary conversation was actively writable.

Production therefore promises:

```text
NO ordinary-history persistence guarantee
```

and should treat unexpected ordinary durable-history materialization as a mode-isolation failure requiring review.

This is stronger than merely hiding a sidebar entry in the adapter. The runtime must not intentionally create a normal durable fallback conversation to simulate Temporary behavior.

## 11. Post-close product-route recovery is not a production reopen contract

PR8.7 observed:

```text
/c/<temporary-product-conversation-id>
    -> exact route
    -> old completed turns hydrate
    -> STABLE_RECOVERED
```

after the source lifecycle ended.

This is valuable characterization evidence, but production must not expose it as:

```text
attach_conversation()
reopen()
continue()
durable recovery
```

because the same post-close state rejected a controlled continuation with `HTTP 404`.

Correct production interpretation:

```text
post-close route recovery = diagnostic/read recovery evidence only
post-close write authority = NONE
```

No retention duration or availability SLA is inferred from the observed recovery.

## 12. `attach_conversation()` boundary

Until separately proven, Temporary must not support the ordinary durable-chat attach contract.

Fail-closed rule:

```text
attach_conversation(temporary_product_conversation_id)
    -> UNSUPPORTED / UNKNOWN
```

It must not silently translate to:

```text
open /c/<id> and assume writable
```

The direct route is not sufficient authority.

## 13. Requested versus observed mode provenance

T9 must make mode provenance first-class.

Every Temporary send result should eventually distinguish at least:

```text
requested_conversation_mode = TEMPORARY
observed_conversation_mode  = TEMPORARY | NORMAL | UNKNOWN
mode_proof                   = explicit evidence record
lifecycle_state              = LIVE | ENDED | UNKNOWN
```

Success is allowed only when:

```text
requested = TEMPORARY
observed  = TEMPORARY
lifecycle = LIVE
```

If the runtime observes `NORMAL` or cannot prove Temporary before the write, the write must not proceed.

A post-write Temporary-looking title, URL fragment, tooltip, or notice is not enough to retroactively authorize a mutation.

## 14. No durable fallback

T8 is a hard production invariant:

```text
request TEMPORARY
    |
    +-- Temporary mode proven -> Temporary write
    |
    `-- Temporary mode not proven -> ERROR
```

Never:

```text
request TEMPORARY
    |
    `-- selection uncertain -> ordinary durable write
```

The earlier automated activation experiment demonstrated why this must be enforced: a Temporary-looking activation path can produce an ordinary durable conversation.

## 15. Mode isolation

T10 and T11 must prove both directions.

### TEMP -> NORMAL

After a Temporary lifecycle is used or terminated:

```text
next NORMAL request
```

must not inherit:

```text
Temporary query state
Temporary page/session state
Temporary identity
Temporary lifecycle binding
Temporary mode proof
```

### NORMAL -> TEMP

A prior normal runtime tab/conversation must not cause a Temporary request to:

```text
reuse a durable normal conversation
inherit normal route identity
skip Temporary mode proof
```

Isolation must be explicit even if the product UI appears to manage it automatically.

## 16. Browser Authority Lease versus Temporary Lifecycle

PR8.8 introduces Browser Authority Lease / Turn Lifecycle / TTL-disposal governance. PR8.7 must define the Temporary-specific semantic input to that work.

The important distinction is:

```text
Browser Authority Lease
    permission/ownership to use a browser execution context

Temporary Lifecycle
    product-mode-specific writable lifetime for one Temporary conversation
```

They may overlap, but they are not identical.

Losing the Temporary lifecycle must revoke Temporary write authority even if a browser tab or direct `/c/<id>` route still exists.

Likewise, recreating generic browser authority must not automatically recreate a terminated Temporary lifecycle.

## 17. Capability semantics

Until T8-T12 pass, capability remains:

```text
temporary_chat = UNKNOWN
```

Graduation to `AVAILABLE` requires evidence that production can reliably:

```text
1. prove Temporary mode before first write;
2. create a live Temporary conversation without durable fallback;
3. continue multiple turns while the same Temporary lifecycle is live;
4. surface requested/observed mode provenance;
5. terminate write authority when the lifecycle ends;
6. avoid promising ordinary canonical readability;
7. avoid promising ordinary history persistence;
8. avoid promising attach/reopen continuation;
9. isolate TEMP -> NORMAL;
10. isolate NORMAL -> TEMP;
11. behave safely across cold/warm/runtime-tab recreation.
```

If any required mechanism cannot be proven, capability remains `UNKNOWN` or becomes explicitly `UNSUPPORTED`; it must not be guessed as `AVAILABLE`.

## 18. HDE-facing contract

HDE should not need to know browser selectors, Temporary control labels, `/c/<id>` hydration quirks, or canonical endpoint differences.

The product runtime boundary should eventually expose semantics equivalent to:

```text
runtime.send(...)
    requested mode
    observed mode
    product conversation identity
    lifecycle state
    finality
    bounded provenance
```

HDE policy can then decide whether a Temporary lifecycle should stay open for another turn or be explicitly released.

HDE must not be asked to reconstruct write authority from a raw Temporary conversation ID.

## 19. Current architecture decision

The existing high-level split still survives:

```text
HDE / terminal / Python
        |
ChatGPTProductRuntime
        |
        +-- ordinary durable read/status -> canonical HTTP plane
        |
        `-- writes -> BrowserOwnedProductTransport
```

Temporary adds an important specialization:

```text
Temporary live write/finality
        -> browser-owned product lifecycle

Temporary ordinary canonical read
        -> not available through current conversation endpoint

Temporary post-close direct route
        -> diagnostic recovery evidence, not write authority
```

This does not yet require PR9.0. It does require PR8.7/PR8.8 to model lifecycle authority explicitly rather than equating identity with continuation permission.

## 20. Remaining PR8.7 gates

Core Temporary lifecycle characterization is no longer open. Remaining gates are production governance:

```text
T8  no normal durable fallback in production path
T9  requested/observed conversation-mode provenance
T10 TEMP -> NORMAL isolation
T11 NORMAL -> TEMP isolation
T12 lifecycle / cold-warm / runtime-tab recreation governance
T13 capability UNKNOWN -> AVAILABLE only after review
```

Until those gates are closed:

```text
production Temporary send = DISABLED
temporary_chat capability  = UNKNOWN
```
