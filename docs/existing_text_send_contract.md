# Existing-Conversation Ordinary-Text Write Contract

PR7.11a introduced the live-observed ChatGPT Web prepare/conduit boundary for
ordinary text writes to an **existing** conversation. PR7.11c replaces the stale
legacy Sentinel portion of that path with the current finalized two-phase bundle
lifecycle established by PR7.11b and two-turn browser evidence.

The scope remains deliberately narrow. New-chat sends and multimodal sends keep
their previous transport until they receive independent live-contract evidence.

## Write sequence

For `send_to_conversation(..., media=None)` the adapter performs:

```text
discard any legacy warmup-prefetched requirements
  -> build one user message
  -> create one x-oai-turn-trace-id
  -> POST /backend-api/f/conversation/prepare
       x-conduit-token: no-token
       x-oai-turn-trace-id: <same turn id used by final write>
  -> require successful prepare + conduit token
  -> reserve an unexpired finalized Sentinel bundle
       or synchronously perform
       /sentinel/chat-requirements/prepare
       -> legitimate challenge boundary
       -> /sentinel/chat-requirements/finalize
  -> irreversibly consume that bundle
  -> POST /backend-api/f/conversation
       client_prepare_state: success
       x-conduit-token: <prepare response token>
       x-oai-turn-trace-id: <same turn id>
       openai-sentinel-chat-requirements-token: <bundle requirements token>
       openai-sentinel-proof-token: <same bundle proof>
       openai-sentinel-turnstile-token: <same bundle Turnstile evidence>
```

The adapter currently reuses its own user message id in `partial_query` and the
final message. This is a local implementation choice that the server has accepted;
two-turn browser evidence shows that same-id equality is **not** a required browser
architectural invariant because context-change prepares can precede the final
message and use a different `partial_query.id`.

## Credential lifecycle and privacy

Conduit and Sentinel credentials remain only in memory. Credential-bearing raw
conversation-prepare and Sentinel prepare/finalize responses are suppressed from
the generic HTTP tracer and replaced with structural traces containing only safe
status/key/presence state.

The following final-write headers are always redacted, even when ordinary local
debug sanitization is disabled:

- `x-conduit-token`;
- `openai-sentinel-chat-requirements-token`;
- `openai-sentinel-proof-token`;
- `openai-sentinel-turnstile-token`.

Lifecycle events likewise expose only token-presence/required state.

A finalized Sentinel bundle has a monotonic expiry and an exclusive single-slot
reservation. Once the bundle is consumed for a final write attempt it is never
restored, including after timeout, connection reset, HTTP rejection, or another
unknown write outcome. This prevents speculative credential replay.

Legacy warmup material is still invalidated before/after a prepared turn, but it
is no longer used to service prepared existing-text writes.

## Turnstile boundary

PR7.11c does not add a Turnstile solver or bypass. Current two-phase finalize
evidence requires a Turnstile string. If no legitimate browser-derived evidence
has been supplied, the adapter fails closed before finalize/write with
`SENTINEL_TURNSTILE_EVIDENCE_REQUIRED`.

Supplied Turnstile evidence is one-shot: it is cleared from `AuthData` when it
enters a finalize transaction and is never restored if finalize fails.

The currently observed finalize policy has both Turnstile and PoW required.
Unobserved required/optional combinations fail closed rather than guessing request
semantics.

## Diagnostics contract

The prepared existing-text path remains wrapped by the same expanded-send
instrumentation used by the legacy `send()` path. The existing requirements timing
hook now measures the execution-local finalized-bundle acquisition/consumption
boundary because the prepared context intercepts `_get_ready_requirements()` before
it can reach the legacy single-step network endpoint. The established
`requirements_ready` event remains structurally compatible with earlier callers.

Successful stream metadata is retained without forcing an additional conversation
fetch and without exposing raw SSE payloads. During the prepared stream, the
integration observes the real private `_parse_event()` state and copies only an
allowlist of `finish_reason`, `observed_model`, and
`observed_reasoning_effort`. A `stream_handoff` is retained only as a boolean
completion-risk signal. Resume tokens, conduit tokens, topic identifiers, handoff
options, and raw event payloads are not copied into this state.

Structured assistant-token events have one owner on the public prepared path: the
expanded-send instrumentation around `on_token`. The duplicate
`assistant_token` emitted by the lower-level stream transport is filtered for this
path, so one streamed token produces one public structured token event.

## Failure boundaries

The final conversation write must not occur when:

- conversation prepare is rejected;
- conversation prepare succeeds without a conduit token;
- no valid finalized Sentinel bundle can be reserved/acquired;
- current Sentinel prepare/finalize structure drifts from the observed contract;
- legitimate required Turnstile evidence is absent;
- the finalized bundle expires before consumption;
- another prepared send already reserves the single available bundle.

A successful prepare does not weaken the challenge boundary. It only establishes
one part of the short-lived transport material needed by the current web write.

## Streaming and recovery

The prepared write reuses the existing backend streaming parser. A stream that
contains `stream_handoff` is never considered complete merely because it already
contains an assistant message id and a text prefix. WebSocket transport
characterization remains out of scope; any observed handoff forces bounded
existing-conversation recovery using the already-known parent message as the
branch boundary.

If a prefix was already delivered through `on_token`, recovery returns the final
conversation text and emits only the missing suffix when the recovered text extends
that prefix. Recovery does not resend `/f/conversation`, so it does not violate the
one-shot Sentinel bundle boundary.

## Explicit non-goals

PR7.11c does not characterize or change:

- `ChatGPTWebClient.send()` for a new conversation;
- existing-conversation sends containing media;
- `/backend-api/sentinel/req` semantics;
- automatic post-write Sentinel refill/background threads;
- Turnstile solving or bypass;
- the WebSocket capability contract planned for PR7.12.

See `sentinel_bundle_lifecycle.md` for the evidence and detailed state machine.
