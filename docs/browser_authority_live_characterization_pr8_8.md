# PR8.8 — Browser Authority Lease live characterization runner

_Status: runner implemented; real Windows/Chrome evidence still required_

_Date: 2026-08-16_

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

The unpacked extension must be reloaded after installing this slice.

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

## Post-CLOSE recreation gate

Phase 4 performs one ordinary `PERSISTENT` continuation after phase 3 proves the runtime tab is absent.

The runner requires:

```text
runtime_tab_created_for_turn = true
Turn Lifecycle = FINALIZED
```

This directly tests that browser-authority recreation does not break ordinary continuation.

## IDLE_TTL gate

Phase 5 selects:

```text
browser_authority_policy = IDLE_TTL
browser_authority_ttl_ms = <positive configured value>
```

The runner waits only a bounded interval and requires the same fenced CLOSE evidence. No automatic write retry follows a failed TTL disposal.

## Command

After pulling the commit and reloading the unpacked extension:

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

Before changing the default away from `PERSISTENT`, PR8.8 still needs review of:

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
