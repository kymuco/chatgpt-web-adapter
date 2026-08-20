# PR8.9.1 — Incremental Canonical Partial-Text Characterization and Revision-Safe Observation Contract

_Status: implementation-ready live characterization harness; production streaming remains disabled_

## Goal

PR8.9 begins with the least-coupled observation source from the reviewed post-PR8 roadmap:

```text
1. incremental canonical observation
2. safe browser response observation
3. rendered page observation
```

The first question is deliberately narrow:

> While one ordinary continuation turn is still in progress, does the existing canonical conversation read surface expose useful partial assistant text before canonical finality?

This slice does **not** change production `ChatGPTProductRuntime.send()` behavior and does not claim `streaming = AVAILABLE`.

## Why the probe is continuation-only

A known existing conversation ID lets the canonical observer begin before the page-owned write starts. New-chat characterization would mix two questions:

1. when does the new conversation identity become available;
2. when does canonical partial assistant text become visible.

PR8.9.1 isolates only question 2.

## Concurrency model

The harness performs exactly one product write and observes the canonical plane concurrently:

```text
main process
   |
   +-- write thread
   |      runtime.send_text_observed(... existing conversation ...)
   |      exactly one product write
   |      no automatic retry
   |
   `-- read-only observer
          get_status()
          get_messages(... assistant ...)
          bounded polling
```

The observer uses a separate `ChatGPTWebClient` instance created from a copied refreshed auth state so concurrent read-only curl operations do not share per-client mutable diagnostics with the writer.

No raw cookies, Authorization headers, browser response bodies, or protection material are exported by the report.

## Revision-safe observation model

PR8.9 must not assume append-only text. The tracker therefore classifies each changed canonical snapshot as:

```text
SNAPSHOT
    first non-empty text observed for a new assistant message identity

DELTA
    new snapshot strictly extends the previous text

REVISION
    new snapshot is not a prefix extension of the previous text
```

Repeated identical snapshots are deduplicated.

Each exported observation contains bounded preview/digest metadata rather than the full assistant response:

```text
sequence
kind
observed_at_ms
message_id / message_key
text_length
text_sha256
text_preview
delta_length / delta_sha256 / delta_preview
previous_text_sha256
canonical_status
canonical_status_message_id
finality_proven_at_observation
write_in_flight
pre_final
```

The tracker internally retains text only long enough to classify revisions and reconcile with the final `ChatResponse`.

## Finality rule

A partial assistant observation is not terminal evidence.

The probe uses the same strong finality relation as the existing browser-native client:

```text
status.status == completed
AND
status.message_id == candidate.message_id
```

Therefore a canonical payload may contain useful assistant text while:

```text
pre_final = true
write_in_flight = true
```

without being misreported as a completed turn.

## Reconciliation

The final canonical response is classified against the last matching observation as one of:

```text
EXACT_MATCH
CANONICAL_EXTENDS_STREAM
STREAM_REVISED_BY_CANONICAL
STREAM_INCOMPLETE
UNAVAILABLE
```

This is the first implementation of the revision-safe vocabulary required by the roadmap; it is still diagnostic and not yet a public streaming API.

## Metrics

The report captures:

```text
first_text_observed_ms / ttft_ms
last_text_observed_ms
last_pre_final_text_observed_ms
canonical_completion_observed_ms
finality_lag_ms
response_returned_ms
response_return_lag_ms
canonical_poll_count
canonical_poll_error_count
```

Existing runtime events are timestamped separately in `event_times_ms`; they are not relabeled as earlier product write-acceptance evidence.

## Safety and mutation boundaries

```text
product_write_budget = 1
automatic_write_retry = false
conversation must be completed before the probe
browser_authority_policy = PERSISTENT
canonical observer performs reads only
no private conversation POST
no protection-token work
no browser-response-body export
production streaming remains disabled
```

If the product write fails after delegation, the harness returns the existing ambiguous-write metadata and never retries the write.

Repeated canonical reads are observation sampling, not product mutation retries.

## Live command

After syncing the branch:

```powershell
python -m chatgpt_web_adapter.incremental_canonical_observation_pr8_9 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --acknowledge-live-writes `
  --timeout 150 `
  --poll-interval 0.25 `
  | Tee-Object -FilePath .\incremental-canonical-pr8_9.json
```

The controlled prompt requests 24 numbered neutral lines so the turn is long enough to give a 250 ms canonical poller a realistic chance to observe growth without creating an unnecessarily large response.

## Decision rule

Candidate A is considered supported for the first slice when at least one non-empty new assistant text observation is seen while:

```text
write_in_flight = true
finality_proven_at_observation = false
```

The report then emits:

```text
useful_incremental_canonical_observation_supported = true
candidate_a_incremental_canonical_observation = SUPPORTED
```

If no such observation is seen, the result is **NOT_PROVEN**, not `UNSUPPORTED` from one run. We should inspect the timing/evidence and, if the canonical surface is clearly final-only, move directly to Candidate B:

```text
SAFE_BROWSER_RESPONSE_OBSERVATION
```

without spending a long research sequence trying to force Candidate A.

## Architecture invalidation check

PR8.9.1 does not invalidate the current browser-owned write architecture.

It deliberately keeps:

```text
page-owned protected mutation
canonical read/status authority
Browser Authority Lease / Turn Lifecycle separation
no automatic retry after ambiguous writes
HDE/public surfaces free of Chrome/CDP/native-messaging details
```

The only new question is whether the canonical plane can also become the low-latency text observation owner.
