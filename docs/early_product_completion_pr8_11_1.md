# PR8.11.1 — Early Product-Completion Signal Characterization and Network-Tail Boundary

Status: CHARACTERIZATION IMPLEMENTED — live signal-ordering gate pending.

## Trigger

PR8.11 reduced the measured post-visible-answer tail from 7753 ms to 5158 ms without weakening canonical finality.

The post-repair production split was:

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

The remaining dominant browser-side region is therefore the approximately 2.9 second interval between the last visible assistant-text update and `Network.loadingFinished`.

PR8.11.1 characterizes product/UI terminal signals inside that interval before changing the completion boundary.

## Characterization surface

The new extension overlay is loaded after PR8.11 and wraps the existing PR8.9 SSE parser and browser turn only for observation.

It records bounded timestamps for:

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

The composer poll runs every 100 ms and is ignored until at least one assistant-text mutation has been observed. Therefore the initially idle composer before submit cannot be misclassified as response completion.

Two consecutive ready observations are recorded separately so the future repair can retain the same anti-transient principle used by the existing completion path.

## Data boundary

The characterization report contains only:

- timestamps/durations;
- counts;
- bounded terminal enums such as `finish_reason` and completed status;
- the name of the earliest recognized terminal signal.

It does not persist or return:

- prompt text;
- assistant text;
- raw SSE blocks;
- response bodies;
- headers;
- cookies or credentials;
- DOM or HTML.

It does not change prompt insertion, submit, model selection, Browser Authority, retry behavior, network lifetime, debugger cleanup, or canonical finality.

## Existing `--timings` integration

No new user-facing command is required.

After the extension is reloaded, the normal diagnostic:

```powershell
cwa send "<prompt>" --stream --timings
```

adds this nested record:

```text
post_answer_tail_timing
  browser_tail_timing
    early_product_completion
```

Important fields:

```text
earliest_terminal_signal_kind
earliest_terminal_signal_ms
last_text_to_earliest_terminal_signal_ms
assistant_finish_reason_observed_ms
assistant_end_turn_observed_ms
assistant_is_complete_observed_ms
assistant_completed_status_observed_ms
message_marker_observed_ms
stream_handoff_observed_ms
done_sentinel_observed_ms
first_composer_ready_after_text_ms
consecutive_composer_ready_after_text_ms
last_text_to_composer_ready_ms
earliest_terminal_signal_to_network_complete_ms
composer_ready_to_network_complete_ms
last_text_to_network_complete_ms
```

## Repair decision rule

PR8.11.1 does not yet use an early signal as completion authority.

A subsequent repair in the same PR is permitted only if live evidence shows a stable ordering such as:

```text
last assistant text
  -> explicit assistant terminal signal
  -> two consecutive composer-ready observations
  -> substantial stable lead
  -> Network.loadingFinished
```

The preferred future boundary is a conjunction, not a single heuristic:

```text
explicit product terminal evidence
AND
bounded consecutive composer-ready proof
```

The stream text alone is never sufficient.

`stream_handoff`, `[DONE]`, message markers, finish reason, or composer readiness are not assumed interchangeable until the live ordering is observed.

## Required live gate

After pulling this characterization slice and reloading the unpacked extension, run:

```powershell
cmd /d /s /c 'cwa send "Produce exactly 12 numbered plain-text lines about computing, each around 12 words." --stream --timings 2> pr8_11_1_completion.json'

Get-Content pr8_11_1_completion.json
```

Required characterization invariants:

```text
browser_tail_timing.available = true
early_product_completion.available = true
assistant_text_observation_count > 0
last_text_to_network_complete_ms != null
composer_probe_error_count = 0
characterization_error_count = 0
```

At least one recognized terminal signal should be reported if the product stream exposes one on this response shape.

The key decision values are:

```text
earliest_terminal_signal_kind
last_text_to_earliest_terminal_signal_ms
last_text_to_composer_ready_ms
earliest_terminal_signal_to_network_complete_ms
composer_ready_to_network_complete_ms
```

If an explicit terminal signal and the two-sample composer-ready proof both lead network completion by roughly the observed 2–3 second tail, the next edit can replace `Network.loadingFinished` as the blocking response-completion boundary while still preserving synchronous debugger/listener cleanup and canonical HTTP finality.

If they do not, no early-return behavior is introduced and the measured ordering determines the next experiment.

## Claim boundary

Until the live gate passes, PR8.11.1 claims only:

> CWA can characterize bounded product-terminal and composer-readiness signals inside the measured post-answer network tail without changing write or canonical-finality semantics.
