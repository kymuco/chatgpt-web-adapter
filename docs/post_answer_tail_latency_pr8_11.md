# PR8.11 — Post-Answer Tail Latency Attribution and Completion-Path Repair

Status: CLOSED — PASS.

## Trigger

Standalone revision-safe streaming is visibly useful, but a manual production run exposed a post-answer latency tail: ChatGPT's UI and the terminal stream could already show the completed assistant answer while `cwa send` remained blocked afterwards.

The relevant completion chain was:

```text
last visible assistant stream event
  -> conversation network completion
  -> browser-native page-turn completion
  -> canonical HTTP finality/readback
  -> runtime return
  -> CLI return
```

PR8.11 attributed that tail and removed redundant work without weakening canonical finality.

## Pre-repair live evidence

Focused regression before the live timing run:

```text
24 passed in 0.25s
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

This established three distinct post-visible-text regions:

```text
last text -> network complete        3032 ms
network complete -> native complete   784 ms
native complete -> canonical final   3937 ms
```

The result disproved the narrower hypothesis that the whole tail was only the known 500 ms fixed sleep.

## Repair A — remove redundant fixed browser delay

Before PR8.11 repair, the page-turn path performed:

```text
Network.loadingFinished
  -> Network.getResponseBody (optional safe metadata)
  -> sleep(500 ms)
  -> waitForComposerReady()
```

`waitForComposerReady()` already performs bounded polling and requires two consecutive ready observations. PR8.11 removed only the fixed 500 ms sleep.

The following remained unchanged:

- two consecutive composer-ready observations on the network-complete fallback path;
- bounded polling;
- synchronous debugger cleanup;
- Browser Authority release semantics;
- no background cleanup;
- no automatic write retry.

## Repair B — collapse serial canonical reads to one payload

Before repair, the happy path performed serially:

```text
get_status()          -> canonical conversation payload read #1
get_messages()        -> canonical conversation payload read #2
attach_conversation() -> canonical conversation payload read #3
```

All three ultimately read the same canonical conversation payload.

PR8.11 changed the production path to use one canonical payload per polling iteration and derive from it:

```text
ConversationStatus
assistant message candidates
finish reason / final-message identity
conversation title / attach metadata
```

The canonical payload remains authoritative. Revision-safe browser streaming is not finality authority.

Normal happy-path evidence:

```text
canonical_payload_read_count = 1
canonical_payload_reused_for_attach = true
```

Lightweight/custom clients without `_get_conversation_payload` retain the compatibility path.

## First post-repair live evidence

The first PR8.11 repair run produced:

```text
last text -> network complete         2922 ms
network complete -> native complete    279 ms
native complete -> canonical final    1956 ms
last text -> runtime return           5158 ms
```

Compared with the pre-repair run:

```text
network -> native        784 ms -> 279 ms
native -> canonical     3937 ms -> 1956 ms
last text -> return     7753 ms -> 5158 ms
```

This removed approximately 2.6 seconds of post-visible-answer latency while keeping canonical finality intact.

The remaining dominant browser-side delay was then isolated to the interval between the final visible assistant text and `Network.loadingFinished`; that region was delegated to PR8.11.1 for a separately proven completion boundary.

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

Assistant text remains on stdout. Diagnostic timing data is printed to stderr.

The report includes:

```text
canonical_readback.canonical_payload_read_count
canonical_readback.canonical_payload_reused_for_attach
```

## Compatibility repair discovered by full regression

After the latency optimization, full regression found two legacy helper-contract failures. `_wait_for_new_final_assistant()` had changed from returning the final message directly to returning a readback tuple.

The compatibility repair restored the default historical contract:

```text
_wait_for_new_final_assistant(...)
  -> message
```

while production explicitly requests the optimized readback tuple internally:

```text
_wait_for_new_final_assistant(..., include_readback=True)
  -> (message, canonical_payload, canonical_payload_read_count)
```

Therefore the public/internal legacy behavior is preserved without losing the one-payload production optimization.

Compatibility regression after the fix:

```text
8 passed in 0.50s
```

## Final regression gate

Final full suite:

```text
1186 passed in 25.59s
```

No failing tests remained.

## Final classification

PR8.11 = PASS.

Proven outcomes:

- post-visible-answer latency was decomposed into browser/network/native/canonical phases;
- the fixed 500 ms browser delay was removed;
- serial canonical reads were collapsed to one authoritative payload on the production happy path;
- legacy helper compatibility was restored after full-suite detection;
- canonical finality remained authoritative;
- revision-safe streaming remained functional;
- no automatic retry or second product write was introduced;
- final full suite: `1186 passed in 25.59s`.

The remaining network-tail problem was not hidden or weakened; it was isolated and then repaired separately by PR8.11.1.
