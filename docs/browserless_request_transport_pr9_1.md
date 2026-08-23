# PR9.1 — Experimental Browserless Request Transport

_Last updated: 2026-08-23_

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

Transport support tier and capability state remain independent. A browserless
capability can be `AVAILABLE` while the transport itself remains `EXPERIMENTAL`.

## Why this exists

CWA already contains substantial authenticated ChatGPT-web request, SSE and
canonical-read machinery. PR8 correctly stopped treating the historical
compatibility client as the production writer and moved ordinary product writes
behind browser-owned authority.

PR9.1 does not reverse that decision. It introduces direct requests as a distinct,
explicit transport under the PR9.0 contract so that:

- applications do not depend on browser implementation details;
- browserless behavior can evolve without weakening browser-owned production;
- protocol drift has its own failure class;
- a working private-protocol path does not silently acquire production support;
- protected browser challenges remain a hard boundary rather than a reason to add
  challenge-bypass machinery.

## External implementation review

Before and during PR9.1 we compared current public ChatGPT-web implementations and
protocol notes, including `openweb`, `ChatGPT-Web2API`, `Rosetta`, `OmniRoute`,
`ChatGPTReversed`, historical `revChatGPT`-style wrappers, and direct wrappers that
reproduce browser fingerprint / proof-of-work / Turnstile behavior.

The useful common pattern is:

1. authenticated canonical reads are comparatively straightforward;
2. product writes are guarded by dynamically deployed Sentinel policy;
3. modern browser-backed implementations let the official page obtain current
   browser-bound challenge evidence;
4. fully direct wrappers often reproduce fingerprint, PoW, Turnstile, Arkose or
   similar protection behavior;
5. the private write protocol drifts, including conversation prepare/conduit and
   Sentinel sequencing changes.

CWA uses these projects as protocol/failure references. It does **not** copy their
protection-bypass behavior.

## Current Sentinel protocol decision

CWA already contains live evidence that the current protected write contract is a
two-phase Sentinel sequence:

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

Historical CWA compatibility code still contains a legacy single-step
`chat-requirements` path. PR9.1 does **not** use it and does not silently fall back
to it.

Canonical PR9.1 governance therefore states:

```text
browserless_sentinel_protocol = TWO_PHASE_PREPARE_FINALIZE
browserless_legacy_single_step_requirements_fallback = false
```

This matters because a direct transport should fail when the current protocol is
not representable, rather than appearing healthy only because an older endpoint
happens to return something.

## Non-negotiable protection boundary

`browserless-request` never:

- opens Chrome as a fallback;
- starts the browser-native bridge;
- requests a Sentinel browser bundle;
- solves or synthesizes Turnstile evidence;
- generates proof-of-work for a protected write;
- emulates a browser fingerprint to satisfy protection;
- replays one-shot protected credentials;
- retries an ambiguous conversation write automatically;
- silently switches to `browser-owned`;
- silently switches to the historical single-step requirements path.

The transport performs current Sentinel `prepare` first. Every observed challenge
block must expose a boolean `required` flag. Any current or future top-level
challenge descriptor with `required=true` stops the operation **before Sentinel
finalize and before conversation mutation**.

That stop is `BROWSERLESS_CHALLENGE_BOUNDARY`, not an invitation to solve the
challenge.

## Challenge-free finalize

Only when the current prepare response explicitly reports no required challenge
does PR9.1 attempt Sentinel `finalize`.

The finalize request contains:

```text
prepare_token = server-issued prepare token
proofofwork   = null
turnstile     = null
```

Those `null` fields are deliberate: they represent absence of required evidence,
not fabricated credentials.

If the server rejects challenge-free finalize, PR9.1 does not invent proof data or
fall back to another protocol. A 403 is classified as a protection boundary;
other incompatible current shapes are classified as protocol drift.

A successful finalize yields the one-shot server-issued requirements token used by
exactly one direct conversation write attempt.

## Direct-request path

```text
saved legitimate ChatGPT session
        |
        v
current Sentinel prepare
        |
        +-- any required challenge
        |       -> CHALLENGE_BOUNDARY
        |       -> no finalize
        |       -> no conversation write
        |
        v
challenge-free Sentinel finalize
        |
        +-- incompatible/rejected shape
        |       -> CHALLENGE_BOUNDARY or PROTOCOL_DRIFT
        |       -> no conversation write
        |
        v
server-issued one-shot requirements token
        |
        v
canonical attach (continuation only)
        |
        v
exactly one direct conversation write attempt
        |
        v
provisional SSE text
        |
        v
canonical completed status
        |
        v
canonical current-branch assistant readback
        |
        v
final response + reconciliation event
```

The finalized token is bound execution-locally to the compatibility request/SSE
machinery. During that turn the historical requirements/proof path cannot run
underneath PR9.1.

## Continuation identity rule

For continuation, PR9.1 resolves the current parent through canonical attach before
network mutation.

After a returned direct write, canonical readback must advance beyond that
pre-write parent identity. Seeing `completed` while the latest assistant identity
is still the old parent is **not** accepted as success; it becomes
reconciliation-required.

This prevents stale canonical state from being mistaken for confirmation of the
new write.

## Finality

SSE is provisional observation, never canonical finality.

A successful browserless execution requires:

1. a durable conversation identity;
2. canonical status `completed`;
3. a canonical assistant message identity newer than the continuation parent when
   applicable;
4. canonical assistant text;
5. reconciliation of provisional stream text against that canonical text.

The returned response uses canonical text and identity. The normalized event
stream ends with `canonical_text_finalized`.

If a conversation write may have been submitted but canonical completion cannot be
proven, the transport does not retry.

## Ambiguous-write rules

```text
Sentinel prepare/finalize failure before conversation write
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

conversation prepare failure proven before final write
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

stream/write outcome unknown
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false

canonical readback/finality failure after returned write
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false
```

## Capability surface

### AVAILABLE

- text-turn implementation;
- new-chat implementation;
- continuation implementation;
- canonical readback;
- conversation attach/read/status;
- provisional text streaming with canonical reconciliation.

`AVAILABLE` means the transport implements and evidence-backs that capability
contract. It does not mean every current session is allowed an unprotected write;
per-turn Sentinel policy can still yield `CHALLENGE_BOUNDARY`.

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

Images/files/multimodal are PR9.2 work rather than an expansion of PR9.1.

## Model and Temporary semantics

PR9.1 does not claim that private backend model slugs are equivalent to the frozen
ChatGPT product modes `INSTANT`, `MEDIUM`, and `HIGH`.

Therefore browserless model/reasoning product-profile selection begins as
`UNKNOWN`. Explicit product-profile selection fails before any browserless network
work until transport-specific evidence exists.

Temporary Chat also begins as `UNKNOWN`; a Temporary request fails before write
rather than silently creating a durable conversation.

## CLI

The experimental transport is selectable through product-runtime inspection and
the low-level runtime send surface:

```text
cwa capabilities --transport browserless-request --json
cwa status --transport browserless-request --json
cwa runtime send --transport browserless-request "hello"
```

The default remains `browser-owned`.

Top-level `cwa send` retains the browser-owned product-profile policy; PR9.1 does
not pretend those profile semantics are already proven on browserless.

## Health semantics

A new-chat browserless health result may be locally `ready` while explicitly
stating that Sentinel preflight is pending. That means the runtime has the local
direct-request and canonical surfaces needed to attempt a turn; it is not a claim
that current server policy will permit an unprotected write.

Per-turn Sentinel policy is authoritative.

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

`CHALLENGE_BOUNDARY` is a valid safety result. It proves the boundary worked; it
does not prove direct-write availability.

## Support promise

PR9.1 freezes this relationship rather than private endpoint details:

```text
ChatGPTProductRuntime
    -> explicit transport selection
    -> browserless support tier = EXPERIMENTAL
    -> current two-phase Sentinel only
    -> no legacy protocol fallback
    -> no browser fallback
    -> no challenge solving
    -> no ambiguous write retry
    -> provisional stream != canonical finality
    -> protected challenge == explicit boundary
```

Because ChatGPT's private web protocol is undocumented and dynamically deployed,
`browserless-request` remains `EXPERIMENTAL` even after successful live writes.
