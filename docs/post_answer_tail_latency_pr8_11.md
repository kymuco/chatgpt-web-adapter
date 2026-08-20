# PR8.11 — Post-Answer Tail Latency Attribution and Completion-Path Repair

Status: ATTRIBUTION IMPLEMENTED — live timing gate pending.

## Trigger

Standalone revision-safe streaming is now visibly useful, but a manual production run exposed a post-answer latency tail: ChatGPT's UI and the terminal stream can already show the completed assistant answer while `cwa send` remains blocked for roughly another 2–3 seconds.

This is not model-generation latency. The relevant completion chain is:

```text
last visible assistant stream event
  -> conversation network completion
  -> browser-native page-turn completion
  -> canonical HTTP finality/readback
  -> runtime return
  -> CLI return
```

PR8.11 first attributes that tail before changing completion semantics.

## Existing known fixed delay

The proven browser-native page turn currently performs this after `Network.loadingFinished`:

```text
Network.getResponseBody (optional safe metadata)
  -> sleep(500 ms)
  -> waitForComposerReady()
```

`waitForComposerReady()` already performs bounded polling and requires two consecutive ready observations separated by a 250 ms poll interval. Therefore the explicit 500 ms sleep is a known candidate for redundant latency, but PR8.11 does not remove it until the live attribution surface confirms the rest of the tail.

## Browser-local timing surface

The new extension overlay is observability-only. For one ordinary leased product turn it records numeric boundaries only:

```text
writeDelegatedMs
lastAssistantTextObservedMs
networkCompleteMs
nativeCompleteMs
lastTextToNetworkCompleteMs
networkCompleteToNativeCompleteMs
lastTextToNativeCompleteMs
assistantTextObservationCount
```

The record is fenced by the exact Browser Authority lease id.

It does not persist or export:

- assistant text;
- prompt text;
- raw SSE;
- request/response bodies;
- cookies;
- credentials;
- DOM/HTML.

It does not change write authority, model selection, submit behavior, retry behavior or canonical finality.

## CLI timing surface

Use:

```powershell
cwa send "<prompt>" --stream --timings
```

The assistant stream remains on stdout. After runtime return, a JSON diagnostic is printed to stderr.

The local callback timeline includes:

```text
turn_started_ms
first_text_event_ms
last_text_event_ms
write_completed_ms
canonical_finalized_ms
readback_completed_ms
runtime_return_ms
```

Derived local deltas include:

```text
last_text_to_write_completed
write_completed_to_canonical_finalized
canonical_finalized_to_readback_completed
readback_completed_to_runtime_return
last_text_to_runtime_return
```

The same JSON includes the browser-local record, allowing the visible tail to be split into:

```text
last text -> network complete
network complete -> native complete
native complete/write-complete -> canonical finality
```

## Required live attribution gate

After pulling this slice and reloading the unpacked extension once, run a response long enough to make the final streamed event visually obvious:

```powershell
cwa send "Produce exactly 12 numbered plain-text lines about computing, each around 12 words." --stream --timings
```

The diagnostic should contain:

```text
browser_tail_timing.available = true
assistant_text_observation_count > 0
last_text_to_network_complete_ms != null
network_complete_to_native_complete_ms != null
last_text_to_native_complete_ms != null
local_tail_deltas_ms.last_text_to_runtime_return != null
```

## Repair decision

The next edit in PR8.11 is selected directly from the live split:

- if `network_complete_to_native_complete_ms` contains the expected fixed ~750 ms floor, remove the redundant explicit 500 ms delay while preserving the existing bounded consecutive-readiness proof;
- if most latency is `last_text_to_network_complete_ms`, investigate an earlier safe product-completion boundary rather than weakening canonical finality;
- if most latency is after browser-native write completion, overlap or tighten canonical readback only with evidence that final identity/status remain authoritative.

No automatic retry is introduced in any case.

## Claim boundary

Until the live timing gate is run, PR8.11 claims only:

> A bounded numeric attribution surface now measures the post-answer completion tail without changing the proven product write or canonical-finality path.
