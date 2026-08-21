# PR8.11.1 — Early Product-Completion Signal Characterization and Network-Tail Boundary

Status: CLOSED — PASS.

## Trigger

PR8.11 reduced the measured post-visible-answer tail from 7753 ms to 5158 ms without weakening canonical finality.

The first post-PR8.11 production split was:

```text
last visible assistant text -> Network.loadingFinished       2922 ms
Network.loadingFinished -> native completion                  279 ms
native completion -> canonical finality                      1956 ms
last visible assistant text -> runtime return                5158 ms
```

PR8.11 also proved:

```text
canonical_payload_read_count = 1
canonical_payload_reused_for_attach = true
```

The remaining dominant browser-side region was the interval between the last visible assistant-text update and `Network.loadingFinished`.

PR8.11.1 characterized terminal product signals inside that interval, rejected unsafe early candidates, and then implemented a fail-closed early browser completion boundary.

## Characterization live evidence

The characterization gate produced:

```text
first assistant text observed                   = 8388 ms
last assistant text observed                   = 12047 ms
assistant finish_reason=stop observed          = 12047 ms
assistant end_turn=true observed               = 12047 ms
assistant metadata is_complete=true observed   = 12047 ms
first composer-ready after text                = 14664 ms
second consecutive composer-ready              = 14766 ms
[DONE]                                          = 15524 ms
Network.loadingFinished                        = 15702 ms
official page-turn complete                    = 15968 ms
```

The measured browser tail was:

```text
last text -> Network.loadingFinished            = 3655 ms
Network.loadingFinished -> native complete       = 267 ms
last text -> native complete                    = 3921 ms
```

Characterization health:

```text
composer_probe_error_count       = 0
characterization_error_count     = 0
```

### False-terminal finding

A generic message status:

```text
finished_successfully = 6935 ms
```

appeared before the first visible assistant text at 8388 ms.

Therefore a completed-looking status alone is not a safe current-answer terminal boundary. PR8.11.1 excludes any candidate terminal timestamp that predates the first visible assistant text from `earliest_terminal_signal`.

The current-answer terminal evidence instead appeared together with the final visible assistant text:

```text
finish_reason = stop
end_turn = true
is_complete = true
```

## Why composer readiness is not the production boundary

The characterization disproved the planned conjunction:

```text
terminal signal AND two consecutive composer-ready observations
```

as the best latency boundary.

On the live characterization run:

```text
last text -> second composer-ready = 2719 ms
second composer-ready -> Network.loadingFinished = 935 ms
```

Requiring composer readiness would recover only the final ~935 ms of the 3.655 s network tail.

Composer readiness is also not required to prove finality of the current response. The next turn performs its own bounded `waitForComposerReady()` before writing. Current-turn correctness remains governed by canonical HTTP readback after browser-native completion.

## Production repair

The eligible product terminal proof is deliberately stronger than a single field:

```text
visible assistant text observed
AND
current visible assistant finish_reason observed
AND
(current assistant end_turn=true OR metadata is_complete=true)
```

The conjunction is evaluated only after the established PR8.9 SSE/patch parser and PR8.11.1 characterization layer fully process the current SSE block.

The page turn accepts this candidate only when all of the following are already true:

```text
conversation POST was observed
HTTP response was observed
response status == 200
current ChatGPT tab resolves to /c/<conversation_id>
```

If every condition is proven:

```text
assistant terminal conjunction
  -> early browser-native completion
  -> synchronous listener/debugger cleanup
  -> mandatory canonical HTTP readback
```

If any condition is not proven, the path falls back unchanged to:

```text
Network.loadingFinished
  -> optional response-body safe metadata extraction
  -> bounded two-sample composer-ready wait
  -> synchronous cleanup
  -> mandatory canonical HTTP readback
```

There is no automatic retry and no second write.

## Why early detach is bounded

The early boundary does not claim that the underlying browser network request has physically ended. It only stops CWA from blocking the caller on response-stream housekeeping after the bounded terminal conjunction and response/identity proofs are complete.

Detaching the CDP debugger stops CWA observation; it does not cancel the already-delegated page request.

Correctness remains protected because `browser_native_client.py` still requires canonical conversation payload finality before returning the assistant response. If canonical finality is not yet available, the bounded canonical poll continues. Stream text is never promoted to final response authority.

On an accepted early boundary, `Network.getResponseBody` is intentionally skipped because the response may still be streaming. Response-body-derived metadata such as `turn_exchange_id` may therefore be absent; this field is optional and is not canonical-finality authority.

## Final live repair gate

The production repair run produced:

```text
local last_text_event_ms               = 20964
local write_completed_ms               = 20987
local canonical_finalized_ms           = 23183
local runtime_return_ms                = 23183

last_text_to_write_completed           = 23 ms
write_completed_to_canonical_finalized = 2196 ms
last_text_to_runtime_return            = 2219 ms
```

Browser-local evidence:

```text
last_assistant_text_observed_ms        = 20939
native_complete_ms                     = 20940
last_text_to_native_complete_ms        = 1 ms
network_complete_ms                    = null
last_text_to_network_complete_ms       = null
network_complete_to_native_complete_ms = null
```

Terminal evidence on the same run:

```text
assistant_finish_reason                = stop
assistant_finish_reason_observed_ms    = 20939
assistant_end_turn_observed_ms         = 20939
assistant_is_complete_observed_ms      = 20939
earliest_terminal_signal_kind          = assistant_finish_reason
earliest_terminal_signal_ms            = 20939
last_text_to_earliest_terminal_signal_ms = 0
```

The generic completed status again arrived too early:

```text
assistant_completed_status             = finished_successfully
assistant_completed_status_observed_ms = 15595
first_assistant_text_observed_ms       = 17473
```

and was correctly excluded from terminal authority.

The repair did not wait for later housekeeping signals:

```text
done_sentinel_observed_ms              = null
first_composer_ready_after_text_ms      = null
consecutive_composer_ready_after_text_ms = null
network_complete_ms                    = null
```

This is the intended result: the browser-native blocking tail collapsed from the earlier 3921 ms measurement to 1 ms while canonical finality remained mandatory.

## Canonical readback evidence

The final live run retained the PR8.11 one-payload canonical path:

```text
canonical_payload_read_count = 1
canonical_payload_reused_for_attach = true
```

The remaining approximately 2.2 seconds after the browser phase were therefore canonical authoritative readback latency, not artificial browser completion waiting.

## Regression evidence

Focused PR8.11/PR8.11.1 regression before the full suite:

```text
44 passed in 0.23s
```

The first full-suite run then exposed two compatibility failures in the legacy `_wait_for_new_final_assistant()` return contract. That regression was repaired without changing the early completion boundary or single-payload canonical production path.

Compatibility regression after the fix:

```text
8 passed in 0.50s
```

Final full suite:

```text
1186 passed in 25.59s
```

No failures remained.

## Data boundary

The PR8.11.1 timing surface stores only bounded timestamps, counts, lease identity, and small terminal enums. It does not persist or export:

- prompt text;
- assistant text;
- raw SSE;
- response bodies;
- headers;
- cookies or credentials;
- DOM or HTML.

## Final classification

PR8.11.1 = PASS.

Proven outcomes:

- generic completed status can occur before the current visible answer and is not safe terminal authority;
- visible assistant `finish_reason` plus `end_turn` or `is_complete` provides a bounded current-answer terminal conjunction on the characterized production route;
- early completion additionally requires observed POST, HTTP 200, and resolved `/c/<conversation_id>` identity;
- fail-closed fallback to `Network.loadingFinished` remains available when those proofs are absent;
- browser-native post-text completion collapsed from 3921 ms to 1 ms on the live repair gate;
- end-to-end post-text runtime tail improved to 2219 ms on that run;
- canonical HTTP finality remained authoritative;
- canonical happy-path readback remained one payload and was reused for attach;
- no automatic retry or second write was introduced;
- focused compatibility gate: `8 passed in 0.50s`;
- final full suite: `1186 passed in 25.59s`.

PR8.11 and PR8.11.1 are closed. The next standalone runtime feature can proceed independently.
