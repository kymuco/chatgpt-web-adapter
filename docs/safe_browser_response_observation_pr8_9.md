# PR8.9.2 — Safe Browser Response Observation

_Status: implementation-ready characterization gate after Candidate A live closure_

_Date: 2026-08-19_

## 1. Candidate A live result

PR8.9.1 asked whether browserless canonical reads expose useful assistant text before canonical finality.

One existing-conversation production turn was observed with a 250 ms canonical polling interval.

Observed:

```text
write_attempts                              1
write_completions                           1
canonical_poll_count                       11
canonical_poll_error_count                  0

browser_native_turn_started_ms          14680
browser_native_write_completed_ms       40958
first_canonical_text_observed_ms         43715
canonical_completion_observed_ms         43715
browser_native_readback_completed_ms     48167
response_returned_ms                     53639

canonical observation count                  1
first canonical text length               2999
first canonical status                completed
finality proven at first observation       true
pre-final partial text observed            false
stream/canonical reconciliation      EXACT_MATCH
response return lag after canonical        9924 ms
```

Decision:

```text
Candidate A — INCREMENTAL CANONICAL OBSERVATION
    useful pre-final text = NOT PROVEN
    repeat characterization = NOT REQUIRED
    canonical plane remains authoritative for finality/reconciliation
```

The canonical endpoint returned the whole 2999-character assistant message only after it was already terminal. It therefore does not solve first-text latency on this observed product path.

The same run exposed a separate post-final optimization opportunity: the final canonical text was available about 9.9 seconds before the current high-level call returned. That is not the PR8.9.2 streaming source question and should not be conflated with it.

## 2. Candidate B question

The next source in the reviewed roadmap is safe browser response observation.

The narrow question is:

> Can the existing page-owned conversation response expose visible assistant text materially before `Network.loadingFinished`, without exporting raw protected browser traffic?

Chrome DevTools Protocol currently exposes the experimental `Network.streamResourceContent(requestId)` method. When enabled for one request, already-buffered bytes are returned as `bufferedData` and later `Network.dataReceived` events may include response data.

PR8.9.2 treats this as characterization only. It is not yet a production streaming dependency.

## 3. Safety boundary

The characterization worker:

- observes only the request already proven by `isConversationWrite(...)`;
- does not modify request JSON;
- does not call `Network.getRequestPostData`;
- does not call `Network.getResponseBody`;
- does not enable the `Fetch` interception domain;
- does not pause, fulfill, fail, replay, or retry the request;
- does not export request/response headers;
- does not export cookies, authorization material, Sentinel/Turnstile/protection material;
- does not return the raw SSE/network body to Python.

The browser-local reducer exports only bounded assistant-text metadata:

```text
message id/key
content type
SNAPSHOT / DELTA / REVISION
text length
SHA-256 digest
short text preview
delta length/digest/preview
finish reason when present
relative observation time
whether observation preceded network completion
```

At most 64 observations are exported.

## 4. Revision-safe rule

The reducer never assumes append-only output.

For the same assistant message:

```text
first visible text                       -> SNAPSHOT
new text starts with previous text       -> DELTA
new text replaces/rewrites prior text    -> REVISION
identical repeated snapshot              -> ignored
```

Only visible assistant `text` / `multimodal_text` content addressed to `all` is eligible. Explicitly hidden conversation messages and non-assistant/tool-directed content are excluded.

## 5. Live gate

Exactly one existing-conversation product write is allowed.

Success for Candidate B requires all of:

```text
conversation request observed
Network.streamResourceContent supported on the live Chrome target
at least one safe assistant-text observation
first assistant text observed before Network.loadingFinished
no decoding/processing failure that invalidates the observation
```

The canonical final `ChatResponse` remains authoritative.

If the last browser observation exactly matches canonical final text by length and SHA-256:

```text
stream_canonical_reconciliation = EXACT_MATCH
```

If early observations exist but the bounded metadata is insufficient to prove the exact final relationship:

```text
stream_canonical_reconciliation = STREAM_INCOMPLETE
```

No stronger reconciliation state is invented.

## 6. Decision after the live gate

If Candidate B succeeds:

```text
low-latency source = SAFE_BROWSER_RESPONSE_OBSERVATION
canonical plane    = FINALITY + RECONCILIATION

next work:
    production TextObservationEvent contract
    browser-to-local event delivery
    revision-safe HDE callback surface
    final canonical reconciliation
```

If Candidate B is not proven:

```text
do not repeatedly probe the same CDP method
move to Candidate C — RENDERED_PAGE_OBSERVATION
```

## 7. Architecture invalidation check

Nothing in PR8.9.1 invalidated the current browser-owned write architecture.

Candidate B deliberately reuses the browser authority already required for the product write. It does not widen protected mutation authority.

```text
Browser Authority Lease != Turn Lifecycle
Incremental Text Observation != Canonical Finality
```

Those distinctions remain unchanged.