# Prefetched Two-Phase Sentinel Bundle Lifecycle

PR7.11c integrates the current browser-observed two-phase Sentinel lifecycle into
prepared ordinary-text writes to an existing conversation. It deliberately does
**not** add a Turnstile solver, browser challenge bypass, or blind credential
replay.

## Two-turn browser evidence

A privacy-safe two-turn capture on 2026-08-10 established the following value
relationships without retaining the credential values themselves:

```text
Sentinel prepare #1
  -> prepare_token A
Sentinel finalize #1
  request.prepare_token == A
  request.proofofwork: string
  request.turnstile: string
  -> finalized requirements token #1
/f/conversation #1
  requirements header == finalize #1 token
  proof header        == finalize #1 proofofwork
  turnstile header    == finalize #1 turnstile
```

While `/f/conversation #1` was in flight, the browser immediately performed a
second Sentinel prepare/finalize cycle. The resulting three-value bundle was then
used unchanged by `/f/conversation #2`:

```text
finalize refill after write #1
  requirements token ----┐
  proof string -----------+--> /f/conversation #2
  turnstile string -------┘
```

This establishes a rolling finalized-bundle model. The adapter reserves the next
bundle before conversation prepare and starts one best-effort background refill
after the current bundle is consumed for write-header construction.

The same capture also established that:

- `/backend-api/sentinel/req` produced distinct tokens and is not the observed
  source of the `/f/conversation` requirements header for these turns;
- `conversation/prepare` can be issued for context/window changes before the
  final user message exists;
- a browser `partial_query.id` is therefore **not** required to equal the final
  user-message id;
- the browser reused one `x-oai-turn-trace-id` across a conversation prepare and
  its eventual `/f/conversation` write.

The capture did **not** establish that a Turnstile token obtained for one Sentinel
prepare can be replayed into another prepare/finalize transaction. Frontend code
inspection additionally establishes that required SO collector work is started
fire-and-forget after prepare and is not awaited by finalize.

## Production bundle model

`FinalizedSentinelBundle` keeps the three values required by a current prepared
write only in memory:

```text
requirements_token
proof_token
turnstile_token
acquired_monotonic
expires_monotonic
```

The credential fields are excluded from `repr` and comparison. Generic HTTP trace
capture is suppressed around Sentinel prepare/finalize, and the replacement trace
contains only status, structural keys, required/presence booleans, and explicit
`raw_*_recorded=false` markers.

A `SentinelBundleStore` is a thread-safe single-slot lifecycle:

```text
EMPTY
  -> install
AVAILABLE
  -> reserve
RESERVED
  -> release before consumption -> AVAILABLE
  -> consume                    -> EMPTY
```

A second prepared send cannot reserve the same bundle concurrently. Expired
bundles are discarded before reservation, and a bundle that expires while reserved
cannot be consumed.

## Consumption boundary

The public prepared existing-text path still crosses the existing internal
`_get_ready_requirements()` hook so established metrics remain intact, but PR7.11c
wraps that hook with an execution-local prepared-send gate. Inside that context it
consumes a finalized two-phase bundle and **does not reach** the legacy
`/backend-api/sentinel/chat-requirements` endpoint. Legacy callers outside the
prepared context remain unchanged.

The path is:

```text
reserve/acquire one finalized Sentinel bundle
  -> conversation/prepare
  -> require status=ok + conduit token
  -> select the reserved bundle
  -> consume bundle irreversibly at final write-header construction
  -> POST /f/conversation
  -> best-effort background refill for the next write
```

Once `consume()` succeeds, any network attempt or unknown outcome permanently
burns that bundle. A connection reset, timeout, 403, or other ambiguous write
result is not permission to restore or replay the same Sentinel credentials.
Read-only conversation recovery remains allowed because it does not repeat the
write.

The adapter still clears old legacy warmup requirements state before/after a
prepared turn so a client instance cannot accidentally retain two competing
requirements models.

## Two-phase acquisition

An explicit `ChatGPTWebClient.prefetch_sentinel_bundle()` call can acquire and
cache one bundle when either a complete browser-bundle provider or the lower-level
current-prepare challenge provider has been installed. After a prepared write
consumes a bundle, the adapter schedules one best-effort refill automatically.
The next send blocks on the same acquisition lock if that refill is still running.

When no unexpired prefetched bundle exists, the protocol layer is:

```text
POST /sentinel/chat-requirements/prepare
  -> validate observed structure
  -> prepare_token
  -> PoW descriptor
  -> Turnstile descriptor (dx)
  -> SO collector/snapshot descriptors

current-prepare challenge provider
  receives the exact prepare input p, prepare_token, persona,
  and Turnstile/SO descriptors
  must return Turnstile evidence bound to the current transaction

existing local PoW computation

POST /sentinel/chat-requirements/finalize
  {
    prepare_token,
    proofofwork,
    turnstile
  }
  -> token + expiry
```

The observed successful finalize request contains no `so` field. The browser
starts the SO collector asynchronously immediately after prepare and does not
await it before PoW/Turnstile finalize. The adapter therefore exposes SO
descriptors to the provider context but does not use an invented SO-completion
boolean as a finalize gate. `/sentinel/req` remains outside this write transaction.

PR7.11c only has live finalize evidence for the current policy where
`turnstile.required`, `proofofwork.required`, and `so.required` are all true.
Other combinations fail closed with `SENTINEL_FINALIZE_POLICY_UNOBSERVED` instead
of guessing request semantics.

## Browser challenge capability boundary

The adapter does not solve or synthesize Turnstile or SO challenges. The two-phase
transaction no longer reads `AuthData.turnstile_token` at all. That field remains
legacy compatibility material only and cannot authorize a two-phase finalize,
including after a process restart reloads `auth_data.json`.

The preferred boundary accepts a complete, unused `FinalizedSentinelBundle`
captured from the official page's own prepare/finalize transaction. The optional
`ZendriverSentinelBundleProvider` implements this path without submitting a chat
message or persisting one-shot credentials:

```python
from chatgpt_web_adapter import (
    ChatGPTWebClient,
    ZendriverSentinelBundleProvider,
)

client = ChatGPTWebClient(auth_file="auth_data.json")
client.set_sentinel_bundle_provider(ZendriverSentinelBundleProvider())
client.prefetch_sentinel_bundle()
```

Install it with `pip install "chatgpt-web-adapter[browser]"`. The provider uses an
isolated temporary browser profile seeded from `client.auth.cookies`, observes the
official finalize request/response in memory, synchronizes ordinary ChatGPT cookies
(including `oai-did`) back into the in-memory client, and closes the browser. It may open
a visible browser window because `headless=False` is the safe default for browser
challenge execution.

The lower-level current-prepare evidence boundary remains available for custom
integrations. It receives a `SentinelChallengeContext` containing the exact
prepare input `p`, current `prepare_token`, persona, Turnstile `dx`, and SO
collector/snapshot descriptors. It returns `SentinelChallengeEvidence` that
echoes the prepare/Turnstile bindings and provides a Turnstile token.

Fail-closed outcomes include:

- no provider: `SENTINEL_BROWSER_CHALLENGE_PROVIDER_REQUIRED`;
- stale prepare/Turnstile binding: `SENTINEL_CHALLENGE_BINDING_MISMATCH`;
- missing Turnstile evidence: `SENTINEL_TURNSTILE_EVIDENCE_REQUIRED`.

Provider context/evidence and finalized bundle credentials are memory-only and
excluded from `repr`/comparison. Evidence is consumed only inside the current
acquisition call and is not stored for retry or restart. A provider failure or
finalize failure therefore cannot resurrect evidence through `AuthData`.

The browser-bundle provider is intentionally separate from the transaction
layer: the page performs the challenge and finalize, while the SDK only validates,
reserves, consumes, and redacts the resulting one-shot bundle. Replay or bypass
logic remains out of scope.

## Expiry

The server-provided `expire_after` and `expire_at` values are validated at finalize
time. The earlier of the relative and absolute deadlines is converted to a
monotonic deadline with a small safety margin, so clock changes or inconsistent
TTL fields cannot extend a credential beyond either server limit.

## Turn trace and conversation prepare

The adapter creates one turn trace id before `conversation/prepare` and sends the
same value on the final `/f/conversation` request. Existing-conversation text
prepares use the live-accepted initial `x-conduit-token: no-token`. New-chat and
multimodal prepares use the separately observed shape without an initial conduit
header or `partial_query`; their final write uses the conduit returned by prepare.

The adapter may still intentionally reuse its locally created user-message id in
`partial_query` and in the final payload, but this is an implementation choice,
not a browser contract invariant.

## Remaining unchanged paths

New-chat and multimodal `ChatGPTWebClient.send()` writes now share the finalized
bundle transaction when a Sentinel provider is installed. Approval flows remain
on their existing behavior pending independent evidence.

`/sentinel/req` integration, Turnstile/SO bypass, and PR7.12 WebSocket work remain
outside this transaction-layer change.
