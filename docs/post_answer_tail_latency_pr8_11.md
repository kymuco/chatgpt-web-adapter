# PR8.11 — Post-Answer Tail Latency Attribution and Completion-Path Repair

Status: REPAIR IMPLEMENTED — post-repair live timing gate pending.

## Trigger

Standalone revision-safe streaming is visibly useful, but a manual production run exposed a post-answer latency tail: ChatGPT's UI and the terminal stream can already show the completed assistant answer while `cwa send` remains blocked afterwards.

The relevant completion chain is:

```text
last visible assistant stream event
  -> conversation network completion
  -> browser-native page-turn completion
  -> canonical HTTP finality/readback
  -> runtime return
  -> CLI return
```

PR8.11 attributes that tail and removes redundant work without weakening canonical finality.

## Pre-repair live evidence

Focused regression before the live timing run:

```text
24 passed in 0.25s
```

The live standalone run used:

```powershell
cwa send "Produce exactly 12 numbered plain-text lines about computing, each around 12 words." `
  --stream --timings
```

Observed local callback timing:

```text
first_text_event_ms                = 15729
last_text_event_ms                 = 21310
write_completed_ms                 = 25126
canonical_finalized_ms             = 29063
readback_completed_ms              = 29063
runtime_return_ms                  = 29063

first_text_to_last_text            = 5581 ms
last_text_to_write_completed       = 3816 ms
write_completed_to_canonical       = 3937 ms
last_text_to_runtime_return        = 7753 ms
```

Observed browser-local split:

```text
assistant_text_observation_count       = 24
write_delegated_ms                     = 12892
last_assistant_text_observed_ms        = 21281
network_complete_ms                    = 24313
native_complete_ms                     = 25097
last_text_to_network_complete_ms       = 3032
network_complete_to_native_complete_ms = 784
last_text_to_native_complete_ms        = 3816
```

This establishes three distinct post-visible-text regions:

```text
last text -> network complete        3032 ms
network complete -> native complete   784 ms
native complete -> canonical final   3937 ms
```

The result disproves the narrower hypothesis that the whole tail was only the known 500 ms fixed sleep.

## Repair A — remove redundant fixed browser delay

Before PR8.11 repair, the proven page-turn path performed:

```text
Network.loadingFinished
  -> Network.getResponseBody (optional safe metadata)
  -> sleep(500 ms)
  -> waitForComposerReady()
```

`waitForComposerReady()` already performs bounded polling and requires two consecutive ready observations separated by a 250 ms interval. The explicit 500 ms delay therefore added latency without adding an independent completion proof.

PR8.11 removes only the fixed sleep:

```text
Network.loadingFinished
  -> Network.getResponseBody (optional safe metadata)
  -> waitForComposerReady()
```

The following remain unchanged:

- two consecutive composer-ready observations are still required;
- polling remains bounded;
- debugger cleanup remains synchronous;
- Browser Authority release semantics remain unchanged;
- no background cleanup is introduced.

Expected direct saving on the measured run is approximately 500 ms from the 784 ms `network_complete_to_native_complete_ms` region.

## Repair B — collapse serial canonical reads to one payload

The larger post-native tail was traced to repeated reads of the same canonical conversation endpoint.

Before repair, the happy path performed serially:

```text
get_status()          -> canonical conversation payload read #1
get_messages()        -> canonical conversation payload read #2
attach_conversation() -> canonical conversation payload read #3
```

All three ultimately call `_get_conversation_payload(conversation_id)`.

The measured post-native/canonical tail was 3937 ms. Three serial payload reads make this consistent with roughly 1.3 s per canonical fetch on that run.

PR8.11 now uses one canonical payload per polling iteration and derives from that same payload:

```text
ConversationStatus
assistant message candidates
finish reason / final-message identity
conversation title / attach metadata
```

The canonical payload remains authoritative. The revision-safe browser stream is not promoted to finality authority.

On the normal happy path where the first canonical payload after browser completion is already final:

```text
canonical_payload_read_count = 1
canonical_payload_reused_for_attach = true
```

Custom/lightweight clients without `_get_conversation_payload` retain the previous compatibility path.

## Browser-local timing surface

The PR8.11 extension overlay records only bounded numeric timing metadata for one ordinary leased product turn:

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

It does not persist or export assistant text, prompt text, raw SSE, request/response bodies, cookies, credentials, DOM or HTML.

## CLI timing surface

Use:

```powershell
cwa send "<prompt>" --stream --timings
```

Assistant text remains on stdout. The diagnostic is printed to stderr.

The local report now also includes:

```text
canonical_readback.canonical_payload_read_count
canonical_readback.canonical_payload_reused_for_attach
```

This lets the post-repair live gate prove both latency improvement and single-payload canonical reuse.

## Required post-repair live gate

After pulling the repair and reloading the unpacked extension once, run the same shape of response:

```powershell
cwa send "Produce exactly 12 numbered plain-text lines about computing, each around 12 words." `
  --stream --timings 2> pr8_11_tail_after.json

Get-Content pr8_11_tail_after.json
```

Required semantic invariants:

```text
browser_tail_timing.available = true
assistant_text_observation_count > 0
canonical_readback.canonical_payload_read_count = 1
canonical_readback.canonical_payload_reused_for_attach = true
canonical final text remains authoritative
revision-safe streaming remains functional
no automatic retry
```

Expected latency changes, not hard pass thresholds:

```text
network_complete_to_native_complete_ms should lose the fixed ~500 ms component
write_completed_to_canonical_finalized should materially shrink when one canonical read is sufficient
```

`last_text_to_network_complete_ms` is intentionally not changed by this repair. The pre-repair run measured that server/network-tail region at 3032 ms; changing it would require a separate proof of an earlier safe completion boundary.

## Claim boundary

Until the post-repair live gate is run, PR8.11 claims:

> The post-answer tail is attributed into browser/network/native/canonical regions, and two redundant serial latency sources have been removed without weakening canonical finality or Browser Authority semantics.

It does not yet claim a measured post-repair latency improvement.