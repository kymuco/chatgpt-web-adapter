# PR9.1 — Experimental Browserless Request Transport

_Last updated: 2026-08-25_

## Status

`browserless-request` is an **EXPERIMENTAL** ChatGPT product transport below the
frozen `ChatGPTProductRuntime` application boundary.

It does not replace `browser-owned`, which remains the default **PRODUCTION**
transport.

```text
application
    |
    v
ChatGPTProductRuntime
    |
    +-------------------------------+
    |                               |
    v                               v
browser-owned                   browserless-request
PRODUCTION                      EXPERIMENTAL
browser/page-owned write        direct authenticated HTTP request
```

Transport support tier and capability state are intentionally independent. A
browserless capability can be `AVAILABLE` while the transport itself remains
`EXPERIMENTAL`, and per-turn Sentinel policy can still deny direct-write admission.

## Frozen PR9.1 boundary

PR9.1 implements one explicit direct-request transport under the PR9.0 product
runtime contract. The stable boundary is behavioral rather than tied to private
endpoint details:

```text
explicit browserless transport selection
    -> browser-owned remains default / PRODUCTION
    -> browserless-request remains EXPERIMENTAL
    -> current two-phase Sentinel only
    -> continuation parent resolved canonically before Sentinel preflight
    -> current conversation/prepare + conduit final-write path only
    -> no legacy requirements fallback
    -> no unprepared write fallback
    -> no browser fallback
    -> no challenge solving / proof generation
    -> no protected credential replay
    -> no automatic ambiguous-write retry
    -> one total invocation deadline
    -> provisional stream != canonical finality
    -> submitted assistant identity == completed-status identity == readback identity
```

## Why this exists

CWA already contains authenticated ChatGPT-web request, SSE and canonical-read
machinery. PR8 correctly stopped treating the historical compatibility client as
the production writer and moved ordinary product writes behind browser-owned
authority.

PR9.1 does not reverse that decision. It introduces direct requests as a distinct,
explicit transport so that:

- applications remain behind the product-runtime boundary;
- browserless behavior can evolve without weakening browser-owned production;
- private-protocol drift becomes an explicit failure class;
- a working direct path does not silently acquire production support;
- browser protection remains a hard boundary rather than a reason to add challenge
  bypass machinery.

## External protocol review

During PR9.1, current public ChatGPT-web implementations and protocol notes were
used as protocol/failure references. The recurring pattern was:

1. authenticated canonical reads are comparatively straightforward;
2. product writes are guarded by dynamically deployed Sentinel policy;
3. modern browser-backed implementations let the official page obtain current
   browser-bound challenge evidence;
4. fully direct wrappers frequently reproduce fingerprint, PoW, Turnstile, Arkose
   or similar protection behavior;
5. the private write protocol drifts, including Sentinel and
   conversation-prepare/conduit sequencing.

CWA uses that ecosystem only to understand protocol shape and failure modes. PR9.1
does **not** copy protection-bypass behavior.

## Current Sentinel protocol

PR9.1 uses the currently observed two-phase Sentinel sequence only:

```text
/backend-api/sentinel/chat-requirements/prepare
        |
        v
challenge descriptors + prepare_token
        |
        v
/backend-api/sentinel/chat-requirements/finalize
        |
        v
one-shot requirements token
```

The historical single-step `chat-requirements` compatibility path is not a PR9.1
fallback.

Canonical governance metadata therefore includes:

```text
browserless_sentinel_protocol = TWO_PHASE_PREPARE_FINALIZE
browserless_conversation_write_protocol = PREPARE_CONDUIT_FINAL_WRITE
browserless_legacy_single_step_requirements_fallback = false
browserless_legacy_unprepared_conversation_write_fallback = false
browserless_challenge_boundary = FAIL_CLOSED_BEFORE_WRITE
browserless_shared_client_binding_scope = EXECUTION_CONTEXT
browserless_shared_client_write_serialization = PER_CANONICAL_CLIENT
browserless_timeout_scope = EXECUTION_CONTEXT_TOTAL_DEADLINE
browserless_ephemeral_header_policy = STRIP_INHERITED_ALLOW_CURRENT_REQUIREMENTS_CONDUIT
```

## Non-negotiable protection boundary

`browserless-request` never:

- opens Chrome as a fallback;
- starts the browser-native bridge as a fallback;
- invokes configured Sentinel browser challenge/bundle providers for its write;
- solves or synthesizes Turnstile evidence;
- generates proof-of-work for a protected write;
- emulates a browser fingerprint to satisfy protection;
- replays inherited one-shot requirements/proof/Turnstile/conduit credentials;
- retries an ambiguous conversation write automatically;
- silently switches to `browser-owned`;
- silently switches to the historical single-step requirements path;
- silently switches to the historical unprepared conversation write path.

Challenge/bundle providers are checked at execution time as well as construction
boundaries. A provider added later cannot turn an already-assembled browserless
transport into a proof/browser path.

Every observed Sentinel challenge descriptor must expose a boolean `required`
field. A required current or future challenge stops the operation before Sentinel
finalize and before conversation mutation. Missing/non-boolean `required` metadata
is protocol drift rather than permissive interpretation.

That stop is `BROWSERLESS_CHALLENGE_BOUNDARY`, not an invitation to solve the
challenge.

## Challenge-free finalize

Only when every observed challenge is explicitly `required=false` does PR9.1
attempt Sentinel `finalize`.

The finalize request contains the server-issued `prepare_token` and no fabricated
protected evidence. If challenge-free finalize is rejected or its shape no longer
matches the bounded protocol, PR9.1 returns challenge boundary or protocol drift;
it does not invent proof data or fall back.

A successful finalize yields the one-shot server-issued requirements token used by
exactly one prepared conversation mutation attempt.

## Final direct-request transaction

For continuation, canonical parent resolution occurs before Sentinel preflight and
inside the same browserless mutation transaction. The final architecture is:

```text
saved legitimate ChatGPT session
        |
        v
acquire per-canonical-client mutation authority / lock
        |
        v
canonical attach + current parent resolution (continuation only)
        |
        v
current Sentinel prepare
        |
        +-- required challenge
        |       -> CHALLENGE_BOUNDARY
        |       -> no finalize
        |       -> no conversation mutation
        |
        +-- malformed/unknown descriptor
        |       -> PROTOCOL_DRIFT
        |       -> no conversation mutation
        |
        v
challenge-free Sentinel finalize
        |
        +-- incompatible/rejected shape
        |       -> CHALLENGE_BOUNDARY or PROTOCOL_DRIFT
        |       -> no conversation mutation
        |
        v
server-issued one-shot requirements token
        |
        v
conversation/prepare
        |
        v
server-issued conduit token
        |
        v
exactly one conduit-bound final conversation write
        |
        v
provisional SSE text
        |
        v
canonical completion polling for submitted assistant identity
        |
        v
canonical assistant readback for same submitted identity
        |
        v
final response + reconciliation event
```

The shared-client lock covers continuation attach, Sentinel prepare/finalize,
prepared mutation and canonical reconciliation. Ordinary mutation entrypoints on
the same canonical client participate in that same lock/freshness domain, so a
queued continuation cannot submit a stale parent after browserless advances the
conversation.

Nested/re-entrant mutation authority is fail-closed except for narrowly recognized
same-client internal delegation. Opposite-order nested cross-client mutation is
rejected before a second lock acquisition, preventing AB/BA deadlock.

## Shared-client isolation

Browserless request state is execution-local rather than a global mutation of the
shared canonical client's ordinary behavior.

The owner execution gets its browserless requirements/header/deadline behavior;
foreign callers using the same client continue to see ordinary caller-owned
headers and timeout semantics. Multiple `BrowserlessRequestTransport` instances
sharing one canonical client reuse the same per-client serialization domain.

Post-construction compatible-client mutation replacement remains fenced. The fence
preserves supported function and callable-object decorators, including
`functools.wraps`, slotted callable objects, inherited slots and list-form
`__slots__`, without treating copied metadata as package fence authority.

## Protected credential policy

Every browserless request strips inherited ephemeral write credentials
case-insensitively:

- requirements token;
- Sentinel proof token;
- Turnstile token;
- conduit token.

This applies to continuation attach, Sentinel prepare/finalize, conversation
prepare/final write, canonical reconciliation reads, and browserless conversation
health reads.

Only current server-issued values may be reintroduced at the exact permitted
stage: the current requirements token for the prepared write and the current
conduit token for the final conversation write. Protected proof/Turnstile evidence
is never replayed or synthesized.

## Total invocation deadline

The caller's browserless timeout is one total invocation deadline, not merely a
curl timeout. It covers:

- waiting for shared-client mutation authority;
- continuation attach;
- Sentinel prepare/finalize;
- conversation prepare and final write;
- synchronous recovery polling and its sleeps;
- WebSocket handoff/recovery when reached by compatibility machinery;
- canonical completion polling;
- canonical status/message network reads.

If the deadline expires before final mutation, the operation fails with proven
zero-write semantics. If it expires after the final write may have been submitted,
the result is conservatively reconciliation-required and is never retried.

## Canonical finality and turn identity

SSE is provisional observation, never canonical finality.

A successful browserless execution requires a non-empty assistant `message_id`
from the submitted direct turn. Finality then binds three identities:

```text
submitted assistant message_id
    == canonical completed-status message_id
    == canonical assistant readback message_id
```

Missing submitted identity fails closed before canonical evidence can be used to
manufacture success for an uncorrelated turn.

Canonical reads can briefly remain on a previously completed assistant after a
successful write. A stale/identity-less `completed` snapshot is therefore treated
as still pending for this one reconciliation invocation while deadline budget
remains. Polling stops as success only when `completed` identifies the submitted
assistant. The post-poll status and assistant readback checks repeat the exact
identity comparison as defense in depth.

For continuation, the submitted assistant must also advance beyond the prewrite
parent identity. A foreign concurrent branch, stale old parent, or branch switch
cannot supply finality for this turn.

The returned response uses canonical text and canonical assistant identity. The
normalized event stream ends with `canonical_text_finalized`.

## Ambiguous-write rules

```text
runtime assembly / auth / curl availability failure
    -> product_turn_invocations = 0
    -> conversation_write_attempts = 0
    -> write_may_have_been_submitted = false
    -> DIRECT_REQUEST_FAILED

continuation attach or Sentinel prepare/finalize failure
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

conversation/prepare failure proven before final write
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

final stream/write outcome unknown
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false

canonical readback/finality failure after returned write
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false
```

The mutation boundary is explicit: generic operational failure remains prewrite
until the final conversation endpoint has actually begun; after that point
ambiguity is conservative.

## Capability surface

### AVAILABLE

- text-turn implementation;
- new-chat implementation;
- continuation implementation;
- canonical readback;
- conversation attach/read/status;
- provisional text streaming with canonical reconciliation.

`AVAILABLE` is an implementation capability state. It does not mean every current
session is allowed an unprotected write; per-turn Sentinel policy can still yield
`CHALLENGE_BOUNDARY`.

### UNKNOWN

- general files;
- web search;
- Temporary Chat;
- product model-profile selection/preservation;
- reasoning selection/preservation;
- product memory/personalization behavior;
- tools/connectors;
- conversation branching.

### UNIMPLEMENTED

- images in PR9.1;
- approval continuation;
- multimodal continuation.

Images/files/multimodal remain later work rather than an expansion of PR9.1.

## Model and Temporary semantics

PR9.1 does not claim private backend model slugs are equivalent to the frozen
ChatGPT product modes `INSTANT`, `MEDIUM`, and `HIGH`.

Browserless model/reasoning product-profile selection therefore remains `UNKNOWN`.
Explicit product-profile selection fails before browserless network mutation until
transport-specific evidence exists.

Temporary Chat also remains `UNKNOWN`; a Temporary request fails before write
rather than silently creating a durable conversation.

## CLI and health semantics

The experimental transport is selectable through product-runtime inspection and
the low-level runtime send surface:

```text
cwa capabilities --transport browserless-request --json
cwa status --transport browserless-request --json
cwa runtime send --transport browserless-request "hello"
```

The default remains `browser-owned`. Top-level `cwa send` retains browser-owned
product-profile policy rather than pretending those semantics are proven on the
browserless transport.

A new-chat browserless health result may be locally `ready` while explicitly
stating Sentinel preflight is pending. Conversation-scoped health reads obey the
same no-replay header policy, but do not acquire mutation authority or invent a
write deadline. Per-turn Sentinel policy remains authoritative.

## Bounded live gate

`browserless_request_live_gate_pr9_1` performs at most one product-turn invocation
and has explicit outcomes:

- `DIRECT_WRITE_COMPLETED` — challenge-free finalize, one direct write, canonical
  finality and expected answer;
- `CHALLENGE_BOUNDARY` — current session requires protected browser evidence;
- `PROTOCOL_DRIFT` — current private protocol no longer matches the bounded
  assumptions;
- `RECONCILIATION_REQUIRED` — a conversation write may have occurred but finality
  is not proven;
- `DIRECT_REQUEST_FAILED` — a non-ambiguous operational failure before write.

The report exists before runtime assembly begins. Malformed/unreadable auth,
missing curl, capability materialization or contract materialization failures are
returned as structured `DIRECT_REQUEST_FAILED` JSON with
`request_stage="runtime_assembly"`, zero product-turn invocations and zero write
counters. Ordinary operational `Exception`s are normalized there; process-control
`KeyboardInterrupt` / `SystemExit` are intentionally not swallowed.

The report separates transport invocation from mutation evidence:

```text
product_turn_invocations
conversation_write_attempts
conversation_write_completions
```

A prewrite challenge boundary therefore reports one product-turn invocation and
zero conversation-write attempts. An ambiguous post-submit result reports one
conversation-write attempt and zero completions.

## Authenticated live observation — 2026-08-24

A user-run authenticated PR9.1 live gate reached current Sentinel prepare and
returned:

```text
outcome = CHALLENGE_BOUNDARY
required challenges = proofofwork, so, turnstile
product_turn_invocations = 1
conversation_write_attempts = 0
conversation_write_completions = 0
write_may_have_been_submitted = false
reconciliation_required = false
challenge_bypass_attempted = false
automatic_write_retry = false
fallback_transport = null
```

A repeat live run after the first safety-repair cycle reproduced the same protected
boundary. The tested session required browser-bound protection evidence and PR9.1
stopped before conversation mutation. There was no browser fallback, challenge
solver, protected credential replay, automatic retry or ambiguous write.

This evidence proves the fail-closed live boundary for the tested session. It does
**not** establish `DIRECT_WRITE_COMPLETED` availability for that account/session or
for future deployments.

## Deterministic validation

The final PR9.1 regression surface includes dedicated coverage for:

- current two-phase Sentinel and prepare/conduit sequencing;
- future/malformed challenge descriptor fail-closed behavior;
- execution-time provider isolation;
- continuation attach and prewrite failure classification;
- no protected credential replay across writes, reads and health;
- total deadline enforcement across queue, preflight, mutation and recovery;
- canonical submitted/status/readback identity correlation;
- stale completed-status eventual-consistency polling;
- missing submitted identity fail-closed behavior;
- shared-client mutation serialization and queued-parent freshness;
- callback reentrancy and cross-client deadlock prevention;
- dynamic mutation-method replacement and decorator composition;
- multiple browserless transports sharing one compatible client;
- runtime-assembly and CLI structured zero-write failure reporting;
- exact installed-wheel import/smoke behavior.

## Support promise

PR9.1 freezes the relationship below, not undocumented private endpoint details:

```text
ChatGPTProductRuntime
    -> explicit transport selection
    -> browserless support tier = EXPERIMENTAL
    -> browser-owned remains default / PRODUCTION
    -> current two-phase Sentinel only
    -> current prepare/conduit final-write path only
    -> per-canonical-client mutation serialization
    -> execution-local headers/deadline state
    -> no legacy/browser/proof fallback
    -> no protected credential replay
    -> no ambiguous write retry
    -> provisional stream != canonical finality
    -> exact submitted-turn identity required for finality
    -> protected challenge == explicit boundary
```

Because ChatGPT's private web protocol is undocumented and dynamically deployed,
`browserless-request` remains `EXPERIMENTAL` even after successful direct writes.
