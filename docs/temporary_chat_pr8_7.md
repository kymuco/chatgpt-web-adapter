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

T9 closes **conversation-mode provenance**, not Temporary identity-kind typing. `ProductIdentityProvenance` must still not imply that a Temporary product conversation ID is an ordinary canonical conversation resource; explicit Temporary identity/lifecycle typing remains separate work.

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

T9 makes conversation-mode provenance first-class in `ProductExecutionProvenance` through a nested `ProductConversationModeProvenance` record:

```text
requested_conversation_mode
observed_conversation_mode
observed_mode_evidence_source
observed_mode_proven
proof_detail
```

T9 production implementation status:

```text
CLOSED / PASS
```

For the currently enabled ordinary path:

```text
requested_conversation_mode = NORMAL
observed_conversation_mode  = NORMAL
observed_mode_evidence_source = TRANSPORT_SEMANTICS_CONTRACT
observed_mode_proven = true
```

`TRANSPORT_SEMANTICS_CONTRACT` is deliberately narrower than a product UI observation. It means the request passed the runtime's explicit NORMAL gate and was dispatched through the current ordinary-mode-only `ProductWriteTransport`; it does **not** claim that a per-turn product UI marker was inspected.

A future successful Temporary execution must use stronger pre-write evidence:

```text
requested_conversation_mode = TEMPORARY
observed_conversation_mode  = TEMPORARY
observed_mode_evidence_source = PRODUCT_MODE_OBSERVATION
observed_mode_proven = true
```

The ordinary transport contract cannot be reused to manufacture Temporary observation proof.

For the currently blocked Temporary production request, T8 and T9 compose as:

```text
requested_conversation_mode = TEMPORARY
observed_conversation_mode  = UNKNOWN
observed_mode_evidence_source = NONE
observed_mode_proven = false
write_count = 0
```

`ProductConversationModeUnavailableError` carries that structured record, so a fail-closed request does not pretend that an unperformed product mutation established observed mode.

The provenance model rejects contradictory claims: an unproven mode must remain `UNKNOWN`, a proven mode requires a non-`NONE` evidence source, and transport-supplied provenance that contradicts the runtime request is rejected rather than normalized silently.

T9 intentionally did **not** synthesize `lifecycle_state`; requested/observed mode proof alone is not continuation authority. T12 now adds a separate `ProductTemporaryLifecycleProvenance` record so lifecycle authority remains structurally distinct from conversation-mode provenance.

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

T8 production implementation status:

```text
CLOSED / PASS

conversation_mode="normal"
    -> existing ProductWriteTransport dispatch

conversation_mode="temporary"
    -> PRODUCT_CONVERSATION_MODE_UNAVAILABLE
    -> fail closed before ProductWriteTransport dispatch
    -> fallback = none
    -> zero write
```

The fail-closed gate is intentionally independent of the current `temporary_chat`
capability state. Even an accidental or premature `UNKNOWN -> AVAILABLE` capability
change cannot enable Temporary writes by itself. A future implementation must add
an explicit mode-aware Temporary write route before this guard can be relaxed.

The existing `ProductWriteTransport` remains ordinary-mode-only in T8. PR8.7 does
not tunnel `conversation_mode="temporary"` through the ordinary transport and does
not synthesize Temporary semantics after an ordinary durable write.

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

T10 production implementation status:

```text
CLOSED / PASS
```

The production runtime now declares conversation-mode selection as request-scoped:

```text
conversation_mode_state_scope = REQUEST
conversation_mode_state_persisted = false
normal_mode_requires_fresh_request_resolution = true
```

The current fail-closed Temporary path is also proven not to mutate ambient runtime mode state. On the same `ChatGPTProductRuntime` instance, a denied Temporary request can be followed immediately by a NORMAL request, and that NORMAL request is resolved from its own caller input only.

Regression coverage proves:

```text
TEMP denied -> zero transport writes
TEMP denied -> default NORMAL -> fresh ordinary new-chat dispatch
TEMP denied with temporary ID -> NORMAL without ID -> temporary ID not inherited
TEMP denied with temporary ID -> NORMAL with ordinary ID -> ordinary ID preserved exactly
TEMP denial provenance -> following NORMAL provenance remains NORMAL-only
repeated TEMP denials -> NORMAL remains available and non-sticky
```

Machine-readable governance additionally fixes:

```text
temporary_mode_denial_mutates_runtime_mode_state = false
normal_mode_inherits_temporary_identity = false
normal_mode_inherits_temporary_lifecycle = false
normal_mode_inherits_temporary_provenance = false
```

T10 closes the current production TEMP -> NORMAL boundary without enabling Temporary writes. When a real mode-aware Temporary write route is introduced, these same invariants remain mandatory and must still hold for a completed or disposed live Temporary lifecycle before capability graduation.

### NORMAL -> TEMP

A prior normal runtime tab/conversation must not cause a Temporary request to:

```text
reuse a durable normal conversation
inherit normal route identity
skip Temporary mode proof
```

T11 production implementation status:

```text
CLOSED / PASS
```

The production boundary now fixes the reverse isolation rule explicitly: a successful ordinary request does not create, cache, or imply Temporary authority for any later request. `conversation_mode="temporary"` is resolved again from the new caller request and must still satisfy independent Temporary pre-write proof.

Regression coverage proves on the same `ChatGPTProductRuntime` instance:

```text
NORMAL success -> TEMP request -> zero additional transport writes
NORMAL continuation identity -> TEMP request -> ordinary identity is not reused
NORMAL observed provenance -> TEMP refusal -> observed mode remains UNKNOWN
ordinary runtime-tab metadata -> TEMP refusal -> tab presence is not mode proof
repeated NORMAL -> TEMP sequences -> every TEMP request remains fail-closed
```

Machine-readable governance fixes:

```text
temporary_mode_requires_fresh_request_resolution = true
normal_mode_success_mutates_temporary_authority = false
temporary_mode_inherits_normal_identity = false
temporary_mode_inherits_normal_lifecycle = false
temporary_mode_inherits_normal_provenance = false
ordinary_runtime_tab_is_temporary_mode_proof = false
ordinary_conversation_identity_is_temporary_mode_proof = false
```

This closes the current production NORMAL -> TEMP boundary without enabling Temporary writes. A future mode-aware Temporary implementation must still obtain fresh `PRODUCT_MODE_OBSERVATION` evidence and a live Temporary lifecycle; neither an ordinary conversation ID nor a pre-existing ordinary runtime tab may satisfy that gate.

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

T12 production implementation status:

```text
CLOSED / PASS
```

T12 makes lifecycle provenance first-class through `ProductTemporaryLifecycleProvenance`:

```text
temporary_lifecycle_state = NOT_ESTABLISHED | LIVE | ENDED | UNKNOWN
lifecycle_evidence_source
lifecycle_state_proven
live_write_authority_proven
proof_detail
```

The currently blocked production Temporary request now carries an explicit fail-closed lifecycle record:

```text
requested_conversation_mode = TEMPORARY
observed_conversation_mode  = UNKNOWN

temporary_lifecycle_state   = NOT_ESTABLISHED
lifecycle_evidence_source    = RUNTIME_GOVERNANCE_CONTRACT
lifecycle_state_proven       = true
live_write_authority_proven  = false
write_count                  = 0
```

`NOT_ESTABLISHED` is stronger and more accurate than pretending the runtime observed a product lifecycle. It states only that the current production gate blocked the request before any Temporary lifecycle could be established. A future successful Temporary execution must prove `LIVE` independently through product/lifecycle evidence; mode proof alone is insufficient.

Cold/warm and recreation governance is now explicit:

```text
temporary_lifecycle_authority_scope = LIVE_PRODUCT_LIFECYCLE
temporary_lifecycle_state_persisted_by_product_runtime = false

cold_runtime_implies_temporary_lifecycle = false
warm_runtime_implies_temporary_lifecycle = false
runtime_reassembly_preserves_temporary_lifecycle = false

runtime_tab_presence_implies_temporary_lifecycle = false
runtime_tab_recreation_restores_temporary_lifecycle = false
browser_authority_recreation_restores_temporary_lifecycle = false

temporary_lifecycle_requires_fresh_proof_after_runtime_recreation = true
temporary_lifecycle_requires_fresh_proof_after_tab_recreation = true
post_close_route_recovery_restores_temporary_lifecycle = false
```

Regression coverage proves the current production boundary across:

```text
cold runtime, no runtime tab -> TEMP remains fail-closed
warm ordinary runtime tab -> TEMP remains fail-closed
new ChatGPTProductRuntime over the same browser authority -> TEMP remains fail-closed
runtime tab 77 -> lost -> recreated as 88 -> TEMP remains fail-closed at every stage
NORMAL execution before runtime reassembly -> does not transfer Temporary authority
```

This is intentionally compatible with PR8.8: browser authority may be reacquired or a runtime tab may be recreated on demand for ordinary product writes, but those events never recreate a product-mode-specific Temporary lifecycle. If a live Temporary lifecycle is lost, production must require a new independently proven lifecycle rather than reconstruct authority from a tab ID, a raw conversation ID, a direct `/c/<id>` recovery route, or a newly assembled runtime object.

## 17. Capability semantics

T8-T12 are closed, but capability remains review-gated:

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

Core Temporary lifecycle characterization and production governance T8-T12 are closed:

```text
T8  no normal durable fallback in production path            CLOSED / PASS
T9  requested/observed conversation-mode provenance          CLOSED / PASS
T10 TEMP -> NORMAL isolation                                  CLOSED / PASS
T11 NORMAL -> TEMP isolation                                  CLOSED / PASS
T12 lifecycle / cold-warm / runtime-tab recreation governance CLOSED / PASS
```

Remaining gate is explicit capability review:

```text
T13 capability UNKNOWN -> AVAILABLE only after review
```

Until T13 explicitly reviews the accumulated evidence and production implementation boundary:

```text
production Temporary send = DISABLED
temporary_chat capability  = UNKNOWN
```

T12 does not itself graduate the capability. It closes lifecycle/recreation governance so T13 can decide whether the remaining gap is an implementation enablement step, further live production evidence, or continued `UNKNOWN`.
