# PR8.11.1 — Early Product-Completion Signal Characterization and Network-Tail Boundary

Status: REPAIR IMPLEMENTED — live repair gate pending.

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

The remaining dominant browser-side region was therefore the interval between the last visible assistant-text update and `Network.loadingFinished`.

PR8.11.1 first characterized terminal product signals inside that interval and now implements a fail-closed early boundary selected from the live evidence.

## Live characterization evidence

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

The run had clean characterization health:

```text
composer_probe_error_count       = 0
characterization_error_count     = 0
```

### Important false-terminal finding

A generic message status:

```text
finished_successfully = 6935 ms
```

appeared **before** the first visible assistant text at 8388 ms.

Therefore a completed-looking status alone is not a safe current-answer terminal boundary. PR8.11.1 repairs the classifier so any candidate terminal timestamp that predates the first visible assistant text is excluded from `earliest_terminal_signal`.

The current-answer signals that matter were instead observed together with the final visible assistant text:

```text
finish_reason = stop
end_turn = true
is_complete = true
```

## Why composer readiness is not the production boundary

The characterization also disproved the planned conjunction:

```text
terminal signal AND two consecutive composer-ready observations
```

as the best latency boundary.

On the live run:

```text
last text -> second composer-ready = 2719 ms
second composer-ready -> Network.loadingFinished = 935 ms
```

Requiring composer readiness would therefore recover only the final ~935 ms of the 3.655 s network tail.

More importantly, composer readiness is not required to prove finality of the current response. The next turn already performs its own bounded `waitForComposerReady()` before writing. Current-turn correctness remains governed by canonical HTTP readback after browser-native completion.

## Production repair

PR8.11.1 now adds a fail-closed early browser completion race.

The eligible product terminal proof is deliberately narrower than the full characterization surface and stronger than a single field:

```text
visible assistant text observed
AND
current visible assistant finish_reason observed
AND
(current assistant end_turn=true OR metadata is_complete=true)
```

The conjunction is evaluated only after the established PR8.9 SSE/patch parser and PR8.11.1 characterization layer have fully processed the current SSE block. On the live run all three terminal signals were observed at the same `12047 ms` boundary, so this strengthening should not add measurable latency.

The page turn accepts this candidate only when all of the following are already true:

```text
conversation POST was observed
HTTP response was observed
response status == 200
current ChatGPT tab already resolves to /c/<conversation_id>
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

The early boundary does not claim that the underlying browser network request has physically ended. It claims only that CWA no longer needs to block the caller on the remaining response-stream housekeeping once all early-boundary conditions are proven.

Detaching the CDP debugger stops CWA observation; it does not cancel the page's already-delegated network request.

Correctness remains protected after return from the extension because `browser_native_client.py` still requires canonical conversation payload finality before returning the assistant response to the caller.

If canonical finality is not yet available, the existing bounded canonical poll continues. Stream text is never promoted to final response authority.

## Optional metadata tradeoff

On an accepted early boundary, `Network.getResponseBody` is intentionally skipped because the response is still streaming.

Therefore response-body-derived metadata such as `turn_exchange_id` may be absent on that turn. This field is already optional in `BrowserNativeTurnResult` and is not used as canonical finality authority.

Conversation and final assistant identity continue to come from the canonical conversation payload.

## Characterization surface

The existing PR8.11.1 timing record still reports bounded timestamps for:

```text
first / last assistant text mutation
assistant finish_reason
assistant end_turn=true
assistant metadata is_complete=true
assistant completed/finished message status
message_marker
stream_handoff
[DONE]
first composer-ready observation after assistant text
second consecutive composer-ready observation after assistant text
Network.loadingFinished
official page-turn completion
```

It stores no prompt text, assistant text, raw SSE, response bodies, headers, credentials, cookies, DOM, or HTML.

## Required repair gate

After pulling the repair and reloading the unpacked extension, run focused regression first:

```powershell
python -m pytest `
  tests/test_early_product_completion_repair_pr8_11_1.py `
  tests/test_early_product_completion_pr8_11_1.py `
  tests/test_post_answer_tail_latency_pr8_11.py `
  tests/test_revision_safe_text_delivery_pr8_9.py `
  tests/test_browser_native_client.py `
  tests/test_standalone_send_cli.py `
  -q
```

Then run the same live response shape:

```powershell
cmd /d /s /c 'cwa send "Produce exactly 12 numbered plain-text lines about computing, each around 12 words." --stream --timings 2> pr8_11_1_repair.json'

Get-Content pr8_11_1_repair.json
```

### Required semantic invariants

```text
streamed assistant response remains complete
canonical_payload_reused_for_attach = true
canonical final text remains authoritative
no automatic retry
no debugger attachment leak
```

### Expected evidence if the fresh-chat route is resolvable early

The accepted early path should make the PR8.11 browser timing look approximately like:

```text
last_assistant_text_observed_ms ~= native_complete_ms
network_complete_ms = null
last_text_to_network_complete_ms = null
last_text_to_native_complete_ms << previous 3921 ms
```

and the repaired terminal classifier should report:

```text
earliest_terminal_signal_kind = assistant_finish_reason
last_text_to_earliest_terminal_signal_ms ~= 0
```

`write_completed_ms` should move close to the last visible text, causing canonical readback to begin several seconds earlier.

If the fresh new-chat URL has not yet resolved to `/c/<id>` when the terminal conjunction arrives, PR8.11.1 must fail closed to the old network path. In that case the timing report will still contain `network_complete_ms`, and no early-boundary success is claimed.

## Claim boundary

Until the repair live gate passes, PR8.11.1 claims:

> Live characterization proved that current visible assistant finish_reason, end_turn and is_complete arrive with the final text while generic completed status can appear too early. CWA now implements a fail-closed conjunctive assistant-terminal completion race that preserves HTTP-200 proof, resolvable conversation identity, synchronous cleanup, and mandatory canonical finality; measured production latency improvement remains pending the explicit live repair gate.
