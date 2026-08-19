# PR8.8 — Browser Authority Lease live characterization runner

_Status: runner implemented; first real Windows/Chrome characterization passed 2026-08-17; independent replication still required before default-policy promotion_

_Date: 2026-08-17_

_Base foundation commit: `ea6a6cc76868bb61b3b9b21e475cb61e6b4df19b`_

## Goal

This runner turns the PR8.8 lease/lifecycle model into one bounded experiment on the real browser-native runtime. It does not change the compatibility default: `PERSISTENT` remains the production default.

The live run characterizes:

```text
warm runtime-tab reuse
post-CLOSE runtime-tab recreation
Browser Authority Lease duration
canonical finality lag
TURN_SCOPED ttl=0 disposal
IDLE_TTL disposal
runtime-tab idle activity/memory proxy
foreground disturbance
debugger cleanup
```

## First live result — 2026-08-17

The first real Windows/Chrome run completed the full bounded sequence:

```text
ok                      = true
write budget            = 5
write attempts          = 5
write completions       = 5
automatic write retry   = false
failure phase           = none
failure                 = none
```

All five turns remained in ordinary durable conversation:

```text
6a82bac1-d7d8-83eb-9b38-a719d91972d7
```

Observed sequence:

```text
persistent_initial
    tab 1949460203 created cold
    total 24196 ms
    lease 18435 ms
    canonical finality lag 5759 ms

persistent_warm
    tab 1949460203 reused
    total 21959 ms
    lease 13867 ms
    canonical finality lag 5314 ms

turn_scoped_close
    TURN_SCOPED ttl=0
    tab 1949460203 reused then CLOSED
    total 20276 ms
    lease 13039 ms
    canonical finality lag 4343 ms
    final state FINALIZED

post_close_recreation
    new tab 1949460207 created
    same conversation continued
    total 24034 ms
    lease 16075 ms
    canonical finality lag 5193 ms

idle_ttl_close
    IDLE_TTL ttl=5000
    tab 1949460207 reused then CLOSED
    total 23856 ms
    lease 13404 ms
    canonical finality lag 6732 ms
    final state FINALIZED
```

The run therefore provided direct live evidence that:

```text
Browser Authority Lease != Turn Lifecycle
runtime tab identity != durable conversation identity
```

Immediate CLOSE after proven Browser Authority release did not prevent later canonical finality. A newly created runtime tab then continued the same durable conversation.

The bounded idle resource sample reported:

```text
observed sample                = 5012 ms
main-thread task-time fraction = 0.0147073 (~1.47%)
max JS heap used               = 100910588 bytes
DOM documents                  = 6 -> 6
DOM nodes                      = 9136 -> 9095
event listeners                = 1290 -> 1288
debugger attached after        = false
tab activated during sample    = false
```

Every product write did observe foreground activation. The resource sample itself did not activate the already-active runtime tab.

This is one machine/browser/runtime window, not a default-policy promotion result.

## Safety and write budget

The happy path performs at most **five real ChatGPT product writes** and requires:

```text
--acknowledge-live-writes
```

There is no runner-level automatic product-write retry. If a phase fails, later writes are not attempted.

Fixed sequence:

```text
1. PERSISTENT      initial turn
2. PERSISTENT      warm continuation
3. TURN_SCOPED     ttl=0 immediate CLOSE experiment
4. PERSISTENT      continuation after runtime-tab recreation
5. IDLE_TTL        bounded delayed CLOSE experiment
```

All turns remain in one ordinary durable conversation. If `--conversation` is omitted, phase 1 creates a new ordinary durable test conversation.

## Zero-write extension preflight

The unpacked extension must be reloaded after installing the runner slice.

Before the first product write the runner sends a read-only support probe through the already serialized Native Messaging turn lane. The worker must prove:

```text
characterizationSupported = true
resourceSamplingSupported = true
runtimeTabReleaseSupported = true
```

If that proof is absent, the runner stops with:

```text
PR8_8_CHARACTERIZATION_EXTENSION_RELOAD_REQUIRED
write_attempts = 0
```

## Idle resource measurement

The runner does not report aggregate `chrome.exe` CPU/memory as though it belonged to the adapter runtime tab.

Instead the extension attaches read-only CDP authority to the exact validated runtime tab for a bounded idle window and samples:

```text
Performance.getMetrics
Memory.getDOMCounters
```

Reported fields include:

```text
TaskDuration start/end/delta
main-thread task-time fraction
JS heap used/total bytes
DOM documents/nodes/listeners
foreground activation evidence
debugger attached-after evidence
```

`task_time_fraction` is a runtime-tab **main-thread activity proxy**, not whole-machine or whole-Chrome CPU.

No page text, DOM content, cookies, request/response bodies, or conversation payloads are exported by the resource probe.

The sample window is bounded to:

```text
1000 ms <= sample <= 15000 ms
```

## Cold/warm interpretation

The runner records end-to-end turn duration together with:

```text
runtime_tab_preexisting
runtime_tab_created_for_turn
```

It therefore distinguishes a warm reused-tab turn from a post-CLOSE recreated-tab turn. The current instrumentation does not isolate pure tab-provisioning latency, so summary fields are deliberately named:

```text
warm_reuse_turn_total_ms
post_close_cold_recreation_turn_total_ms
```

rather than claiming a more precise browser-start component.

In the first run these values were:

```text
warm reuse turn total             = 21959 ms
post-CLOSE recreation turn total  = 24034 ms
observed difference               = 2075 ms (~9.5%)
```

This single comparison is not a stable performance estimate.

## TURN_SCOPED ttl=0 gate

Phase 3 selects:

```text
browser_authority_policy = TURN_SCOPED
browser_authority_ttl_ms = 0
```

The runner requires all of the following before phase 4:

```text
write event observed
Browser Authority Lease release proven
Turn Lifecycle FINALIZED
disposal result = CLOSED or ALREADY_ABSENT
provider runtime_tab_id = null
```

If CLOSE is not proven, the experiment stops.

The first live run satisfied this gate with `CLOSED` and still reached canonical `FINALIZED`.

## Post-CLOSE recreation gate

Phase 4 performs one ordinary `PERSISTENT` continuation after phase 3 proves the runtime tab is absent.

The runner requires:

```text
runtime_tab_created_for_turn = true
Turn Lifecycle = FINALIZED
```

This directly tests that browser-authority recreation does not break ordinary continuation.

The first live run created a different runtime-tab id and continued the same durable conversation successfully.

## IDLE_TTL gate

Phase 5 selects:

```text
browser_authority_policy = IDLE_TTL
browser_authority_ttl_ms = <positive configured value>
```

The runner waits only a bounded interval and requires the same fenced CLOSE evidence. No automatic write retry follows a failed TTL disposal.

The first live run used 5000 ms and confirmed `CLOSED` with no runtime tab remaining.

## Command

After pulling the runner commit and reloading the unpacked extension:

```powershell
python -m chatgpt_web_adapter.browser_authority_live_characterization `
  --acknowledge-live-writes `
  --idle-sample-ms 5000 `
  --idle-ttl-ms 5000 `
  --timeout 150
```

To reuse an existing ordinary durable conversation:

```powershell
python -m chatgpt_web_adapter.browser_authority_live_characterization `
  --conversation <conversation-id> `
  --acknowledge-live-writes `
  --idle-sample-ms 5000 `
  --idle-ttl-ms 5000 `
  --timeout 150
```

## Promotion rule

A successful single run is evidence for that machine/browser/runtime window only. The runner does not promote any default policy.

Before changing the default away from `PERSISTENT`, PR8.8 still needs independent review/replication of:

```text
warm reuse cost
vs
post-CLOSE recreation cost

idle runtime-tab resource cost
vs
CLOSE/recreation cost

foreground disturbance
vs
retention policy

Browser Authority Lease duration
vs
canonical finality safety
```

`TURN_SCOPED ttl=0` remains an explicit low-retention policy unless repeated live evidence justifies its recreation cost for the target HDE call class.
