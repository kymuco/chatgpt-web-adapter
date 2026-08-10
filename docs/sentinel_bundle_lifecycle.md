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

This establishes a rolling finalized-bundle model. The browser may prefetch the
next bundle concurrently with the current turn, but the sync adapter does not need
to reproduce that timing to preserve the credential lifecycle.

The same capture also established that:

- `/backend-api/sentinel/req` produced distinct tokens and is not the observed
  source of the `/f/conversation` requirements header for these turns;
- `conversation/prepare` can be issued for context/window changes before the
  final user message exists;
- a browser `partial_query.id` is therefore **not** required to equal the final
  user-message id;
- the browser reused one `x-oai-turn-trace-id` across a conversation prepare and
  its eventual `/f/conversation` write.

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
conversation/prepare
  -> require status=ok + conduit token
  -> reserve/acquire one finalized Sentinel bundle
  -> consume bundle irreversibly
  -> POST /f/conversation
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
cache one bundle without sending a conversation turn. PR7.11c does not schedule
this automatically. When no unexpired prefetched bundle exists, a prepared write
can acquire one synchronously:

```text
POST /sentinel/chat-requirements/prepare
  -> validate observed structure
  -> prepare_token
  -> PoW descriptor
  -> Turnstile descriptor
  -> SO descriptor

existing local PoW computation
+ legitimate supplied browser Turnstile evidence

POST /sentinel/chat-requirements/finalize
  {
    prepare_token,
    proofofwork,
    turnstile
  }
  -> token + expiry
```

`SO` remains structural evidence only because the observed successful finalize
request did not carry an `so` field. `/sentinel/req` also remains out of this
write transaction until independently characterized.

PR7.11c only has live finalize evidence for the current policy where both
`turnstile.required` and `proofofwork.required` are true. Other combinations fail
closed with `SENTINEL_FINALIZE_POLICY_UNOBSERVED` instead of guessing whether the
field should be omitted, null, or empty.

## Turnstile capability boundary

The adapter does not solve or synthesize Turnstile challenges. A non-empty
`auth.turnstile_token` supplied from a legitimate active browser/session can enter
one finalize transaction. It is cleared from `AuthData` immediately when admitted
and is never restored, including when finalize fails or has an unknown outcome.

If the current Sentinel prepare requires Turnstile and no legitimate supplied
evidence exists, the adapter stops before finalize and before the conversation
write with `SENTINEL_TURNSTILE_EVIDENCE_REQUIRED`.

If future evidence shows that browser Turnstile evidence is cryptographically
bound to a challenge generated by the same prepare call and cannot be supplied to
this boundary, that becomes a separate browser-capability integration problem; it
must not be addressed by replay or bypass logic in this transaction layer.

## Expiry

The server-provided `expire_after` value is validated at finalize time. It is not
hard-coded. The adapter converts it to a monotonic deadline and subtracts a small
safety margin so wall-clock changes cannot revive an expired credential and a
bundle is not consumed at the exact server expiry boundary.

## Turn trace and conversation prepare

PR7.11c creates one turn trace id before `conversation/prepare` and sends the same
value on the final `/f/conversation` request. The adapter continues to use its
live-accepted synchronous `x-conduit-token: no-token` prepare model.

The adapter may still intentionally reuse its locally created user-message id in
`partial_query` and in the final payload, but this is an implementation choice,
not a browser contract invariant.

## Unchanged paths

The following remain on the legacy requirements/send behavior pending independent
evidence:

- new-chat `ChatGPTWebClient.send()`;
- existing-conversation media sends;
- approval flows.

Automatic post-write Sentinel refill, `/sentinel/req` integration, browser
automation, Turnstile solving/bypass, and PR7.12 WebSocket work are explicit
non-goals of PR7.11c.
