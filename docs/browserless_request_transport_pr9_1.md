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

CWA already contains a substantial authenticated ChatGPT web request client. PR8
correctly stopped treating that compatibility client as the production writer and
moved ordinary product writes behind browser-owned authority.

PR9.1 does not reverse that decision. It makes direct requests a distinct,
explicit transport under the PR9.0 contract so that:

- applications do not depend on private browser implementation details;
- browserless behavior can be tested without weakening browser-owned production;
- protocol drift can be classified independently;
- working direct-request behavior does not silently become production support;
- protected browser challenges remain a hard boundary rather than an incentive to
  add bypass machinery.

## External implementation review

Before implementing PR9.1 we compared current public ChatGPT-web projects and
protocol notes, including:

- `openweb-org/openweb`;
- `Octo-Lex/ChatGPT-Web2API`;
- `SyntaxSmith/rosetta`;
- `diegosouzapw/OmniRoute`;
- `gin337/ChatGPTReversed`;
- historical `revChatGPT` / web-session wrappers;
- direct wrappers which emulate fingerprints, proof-of-work, or Turnstile.

The common 2026 pattern is important:

1. canonical reads are comparatively easy to perform with authenticated HTTP;
2. product writes are guarded by rapidly changing Sentinel requirements;
3. current browser-driven implementations deliberately let the official page
   obtain/solve browser-bound challenge evidence;
4. direct wrappers that remain fully browserless typically reproduce fingerprint,
   proof-of-work, Turnstile, Arkose, or related protection behavior;
5. write sequencing and endpoint shapes drift over time, including one-step and
   two-phase Sentinel variants plus conversation prepare/conduit stages.

CWA borrows the useful protocol/failure taxonomy from these projects. It does not
copy protection-bypass behavior.

## Non-negotiable protection boundary

`browserless-request` never:

- opens Chrome as a fallback;
- starts the browser-native bridge;
- requests a Sentinel browser bundle;
- solves or synthesizes Turnstile evidence;
- generates a proof token for a protected write;
- emulates a browser fingerprint for the purpose of satisfying protection;
- replays one-shot protected credentials;
- retries an ambiguous write automatically;
- silently switches to `browser-owned`.

Before a direct write the transport performs a requirements preflight. If the
server reports any top-level challenge descriptor with `required=true`, including
an unknown future descriptor, the transport stops before conversation write and
raises an explicit challenge-boundary error.

This is deliberate even when another public project demonstrates a way to solve
that challenge.

## Initial direct-request path

The PR9.1 implementation reuses CWA's existing authenticated HTTP, conversation
prepare, SSE, and canonical read machinery, but places a new transport boundary
around it.

High-level flow:

```text
saved legitimate ChatGPT session
        |
        v
browserless requirements preflight
        |
        +-- protected / unknown required challenge
        |       -> CHALLENGE_BOUNDARY
        |       -> no conversation write
        |
        v
unprotected requirements token
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
canonical message readback
        |
        v
final response + reconciliation event
```

The preflight result is execution-local and one-shot. It is bound directly to the
request path so the compatibility client's historical proof-generation fallback
cannot run underneath PR9.1.

## Finality

SSE is provisional observation, never canonical finality.

A successful browserless execution requires:

1. a conversation identity;
2. canonical status `completed`;
3. canonical current-branch assistant text;
4. reconciliation of provisional stream text against that canonical text.

The returned response uses canonical text. The normalized event stream ends with
`canonical_text_finalized`.

If the write may have been submitted but canonical completion cannot be proven,
the transport does not retry. It raises a reconciliation-required error.

## Ambiguous write rules

```text
requirements/preflight failure
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

conversation prepare failure before write
    -> write_may_have_been_submitted = false
    -> reconciliation_required = false

stream/write outcome unknown
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false

canonical readback failure after write
    -> write_may_have_been_submitted = true
    -> reconciliation_required = true
    -> automatic retry = false
```

## Capability surface in PR9.1

Initial browserless states:

### AVAILABLE

- text turns;
- new chat;
- continuation;
- canonical readback;
- conversation attach/read/status;
- provisional text streaming with canonical reconciliation.

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

- images in the PR9.1 transport;
- approval continuation;
- multimodal continuation.

Images/files/multimodal belong to PR9.2 rather than expanding PR9.1 sideways.

## Model and Temporary semantics

PR9.1 intentionally does not claim that private backend model slugs are equivalent
to the frozen ChatGPT product modes `INSTANT`, `MEDIUM`, and `HIGH`.

Therefore browserless `MODEL_SELECTION` and `REASONING_SELECTION` begin as
`UNKNOWN`. Explicit product-profile selection fails before write until there is
transport-specific evidence.

Temporary Chat also begins as `UNKNOWN`. A request for Temporary mode fails before
write rather than silently creating a durable conversation.

## CLI

The transport is explicitly selectable for product-runtime inspection and the
experimental runtime send surface:

```text
cwa capabilities --transport browserless-request --json
cwa status --transport browserless-request --json
cwa runtime send --transport browserless-request "hello"
```

The default transport remains `browser-owned`.

The top-level `cwa send` command retains browser-owned product-profile policy. The
experimental browserless path should be exercised through the product-runtime
surface until transport-specific profile semantics are proven.

## Health semantics

A browserless new-chat health result can be locally `ready` while stating that
challenge preflight is still pending. This means the runtime has the required
local direct-request/canonical surfaces; it is not a claim that the server will
allow an unprotected write at that moment.

Per-write server policy is authoritative.

## Live gate outcomes

The bounded PR9.1 live gate performs at most one product write attempt and accepts
four explicit classifications:

- `DIRECT_WRITE_COMPLETED` — unprotected direct write plus canonical finality;
- `CHALLENGE_BOUNDARY` — current session requires protected browser evidence;
- `PROTOCOL_DRIFT` — current private protocol no longer matches bounded assumptions;
- `RECONCILIATION_REQUIRED` — a write may have occurred but finality is not proven.

`CHALLENGE_BOUNDARY` is a valid safety outcome. It does not graduate browserless
write availability and it does not trigger a browser fallback.

## Support promise

PR9.1 freezes the following relationship, not private endpoint details:

```text
ChatGPTProductRuntime
    -> explicit transport selection
    -> no silent fallback
    -> no ambiguous retry
    -> provisional stream != canonical finality
    -> protected challenge == explicit boundary
```

Because ChatGPT's private web protocol is undocumented and dynamically deployed,
`browserless-request` remains `EXPERIMENTAL` even after successful live writes.
