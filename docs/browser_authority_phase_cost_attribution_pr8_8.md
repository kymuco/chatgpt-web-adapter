# PR8.8 — Browser Authority Phase-Level Cost Attribution

Status: implementation + deterministic harness prepared; live evidence required.

This PR8.8 slice follows the independent 3-cycle warm-retention/cold-recreation
replication. That replication proved lifecycle reproducibility but also showed
that full product-turn latency is too noisy to estimate browser recreation cost:
ChatGPT generation and canonical readback can move by many seconds.

The purpose of this slice is therefore narrower:

> measure Browser Authority acquisition/recreation cost at the phase where it
> actually occurs, without changing product semantics or any policy default.

## Non-goals

This slice does **not**:

- change the `PERSISTENT` library default;
- select an HDE assembly policy automatically;
- change Temporary Chat production availability;
- change canonical finality rules;
- change product-write routing, retry, submit, or recovery semantics;
- expose cookies, auth material, raw SSE, response bodies, prompt text, or DOM;
- treat a timing threshold as a correctness gate.

Policy decision remains a human architectural review after evidence collection.

## Why end-to-end timing was insufficient

The previous replication measured total high-level turns in roughly the
30–50-second range. A product turn includes several independent components:

```text
runtime-tab acquire/recreate
    ↓
stale-UI readiness/recovery checks
    ↓
page readiness + composer/input/submit
    ↓
official conversation request / product generation
    ↓
post-network page settling + debugger detach
    ↓
Browser Authority release
    ↓
browserless canonical finality/readback
```

The desired policy variable is primarily the first box. Comparing complete
turns cannot reliably identify a sub-second or low-second recreation premium
when product generation/readback itself varies by tens of seconds.

## Extension observability wrapper

The active manifest entry remains unchanged:

```text
service_worker_temporary_chat_route_reopen_probe.js
version = 0.1.13
```

The existing import chain still reaches `service_worker_observability.js`. That
file now imports:

```text
service_worker_phase_timing_pr8_8.js
```

which in turn imports the previously proven `service_worker_recovery.js` before
adding timing wrappers.

So the new timing layer sits **below** the existing provisioning-observability,
Browser Authority Lease, and PR8.7 Temporary wrappers. The established outer
semantics remain authoritative and the manifest/Temporary entrypoint does not
change.

### Semantic-preservation rule

The timing wrapper is observability-only.

It does not replace:

- `ensureRuntimeTab()` behavior;
- stale-UI recovery;
- `executeOfficialPageTurn()` behavior;
- submit strategy;
- Browser Authority lease handling;
- Temporary probes;
- Native Messaging routing.

If optional timing persistence fails after a successful page turn, that failure
is deliberately ignored by the extension so observability cannot convert a
successful product write into an extension write failure.

The later read-only timing query may then fail, causing the **experiment** to
stop, but never causing a blind retry of the product write.

## Safe timing record

Each ordinary lease-fenced product write may persist one bounded record:

```text
browserAuthorityLeaseId
phaseTimingSchemaVersion = 1

runtimeTabResolveCallCount
runtimeTabFirstResolveMs
runtimeTabResolveTotalMs
runtimeTabResolveMaxMs

pageTurnElapsedMs
tabReadyToWriteDelegatedMs
writeDelegatedToNetworkCompleteMs
networkCompleteToNativeCompleteMs
writeDelegatedToNativeCompleteMs

nativeTurnElapsedMs
runtimeReloaded
runtimeReloadMs
otherNativeOverheadMs
```

No product text or raw product response is stored.

The record is read back only by expected Browser Authority lease ID. A timing
record from a different turn therefore fails closed rather than being silently
misattributed.

## Exact phase meanings

### `runtimeTabFirstResolveMs`

Duration of the **first** `ensureRuntimeTab()` call for the product turn.

For this live gate every cycle starts with the runtime tab proven absent and
targets the same already-completed durable conversation:

- cold: first resolve includes runtime-tab creation + exact route load;
- warm: first resolve is live stored-tab lookup/reconciliation.

This is the primary cold-recreation acquisition metric.

It is intentionally named *resolve* rather than pure `tabs.create()` cost:
creation and page load are part of the usable Browser Authority acquisition
that policy retention avoids.

### `runtimeTabResolveTotalMs`

Sum of all `ensureRuntimeTab()` calls during the native turn.

Continuation stale-UI recovery can perform an additional resolve before the
core write path. Recording first, total, max, and call count prevents that
existing behavior from being mistaken for a single acquisition.

### `tabReadyToWriteDelegatedMs`

From entry into the proven page-owned turn to observation of the official
conversation POST (`Network.requestWillBeSent`).

This includes debugger attach, page/composer readiness, input, and submit
acknowledgement.

### `writeDelegatedToNetworkCompleteMs`

From the official conversation POST to its `Network.loadingFinished`.

This is dominated by the actual product request/stream lifecycle and is not a
Browser Authority recreation cost.

### `networkCompleteToNativeCompleteMs`

From `Network.loadingFinished` until the page-owned runtime finishes its
post-response settling/readiness work and returns through the existing
`executeOfficialPageTurn()` boundary.

### `writeDelegatedToNativeCompleteMs`

Direct delegated → page-native-complete duration.

It provides an accounting cross-check:

```text
writeDelegatedToNetworkCompleteMs
+ networkCompleteToNativeCompleteMs
≈ writeDelegatedToNativeCompleteMs
```

and:

```text
tabReadyToWriteDelegatedMs
+ writeDelegatedToNativeCompleteMs
≈ pageTurnElapsedMs
```

Small rounding tolerance is allowed; inconsistent phase records fail the
experiment.

### `runtimeReloadMs`

The already-existing stale-UI reload metric. It stays separate from runtime-tab
resolution so a genuine recovery reload is not mislabeled as cold recreation.

### `otherNativeOverheadMs`

Residual:

```text
nativeTurnElapsedMs
- runtimeTabResolveTotalMs
- pageTurnElapsedMs
- runtimeReloadMs (if any)
```

It includes existing native-turn work not represented by the major measured
phases, such as stale-UI readiness probing and wrapper/bridge-side overhead.

### canonical readback

The Python runner continues to derive:

```text
post_release_canonical_return_ms
```

from the Browser Authority release timestamp to the completed high-level
`ChatGPTProductRuntime.send_text_observed()` return.

This keeps canonical finality clearly outside Browser Authority acquisition.

## Preflight support gate

A new dedicated read-only support RPC advertises:

```text
characterizeBrowserAuthorityPhaseTimingSupport = true

→ phaseTimingSupported = true
→ phaseTimingSchemaVersion = 1
```

A separate support RPC is used deliberately so the existing PR8.8 status schema
does not need to widen and the timing layer can remain below the current lease
wrapper.

The phase-cost runner requires this **before any product write**.

Therefore running the new Python code against an old/unreloaded extension
produces:

```text
write_attempts = 0
write_completions = 0
PR8_8_PHASE_COST_EXTENSION_RELOAD_REQUIRED_BEFORE_WRITES
```

This is intentional. Do not start a write merely to discover that timing
observability is unavailable.

## Live experiment design

The runner requires an existing completed durable `--conversation`.

This removes the new-chat/root-page confound from cycle 1.

Default experiment:

```text
3 cycles × 3 writes = 9 maximum real product writes
```

Each cycle:

```text
runtime tab proven absent

1. PERSISTENT cold continuation
   → exact existing conversation
   → new runtime tab created
   → phase timing fetched by lease ID

2. PERSISTENT warm continuation
   → same conversation
   → same runtime tab reused
   → phase timing fetched by lease ID

3. TURN_SCOPED ttl=0 continuation
   → same runtime tab
   → canonical completion
   → CLOSE
   → stable tab-absent window
```

There is no automatic product-write retry.

Any write failure or post-write timing/reconciliation failure stops later
writes.

## Phase characterization report

The report includes paired cold/warm values for:

```text
runtime_tab_first_resolve_ms
runtime_tab_resolve_total_ms
page_turn_elapsed_ms
tab_ready_to_write_delegated_ms
write_delegated_to_network_complete_ms
network_complete_to_native_complete_ms
write_delegated_to_native_complete_ms
native_turn_elapsed_ms
other_native_overhead_ms
post_release_canonical_return_ms
```

For each phase it reports cold, warm, and paired cold-minus-warm distributions.

No assertion says cold must be slower than warm. Timing is descriptive.

## Policy decision governance

The runner records:

```text
library_default_policy = PERSISTENT
library_default_change_performed = false
hde_assembly_policy_change_performed = false
phase_cost_threshold_applied = false
decision_scope = RESOURCE_LIFECYCLE_ONLY
decision_requires_human_review = true
```

The experiment can make the policy decision evidence-ready. It cannot mutate
the decision.

A later architectural review can compare the measured recreation premium
against the already-characterized retention resource cost.

## Deterministic regression coverage

The isolated harness covers:

1. manifest routes through the new timing wrapper;
2. phase support/schema and lease-fenced readback parsing;
3. repeated cold/warm/close attribution;
4. exact per-turn policy call shape remains unchanged for cold/warm;
5. stale/unreloaded extension stops before write 1;
6. missing phase data after a completed write stops without retry;
7. internally inconsistent phase accounting stops without retry;
8. explicit live-write acknowledgement and fixed conversation are required.

## Local commands

After pulling the commit, **reload the unpacked Chrome extension once** because
this slice changes an imported service-worker layer. The manifest entry/version
remain unchanged, so the explicit Reload action is required to activate the new
code.

Regression gate:

```powershell
python -m pytest `
  tests/test_browser_authority_phase_cost_attribution_pr8_8.py `
  tests/test_browser_authority_policy_replication_pr8_8.py `
  tests/test_browser_authority_live_characterization.py `
  tests/test_browser_native_provider_pr8_8.py `
  tests/test_browser_owned_write_runtime_pr8_8.py `
  tests/test_product_runtime_browser_authority_pr8_8.py `
  -q
```

The live command should use one already-completed durable conversation and
start with no runtime tab:

```powershell
python -m chatgpt_web_adapter.browser_authority_phase_cost_attribution_pr8_8 `
  --acknowledge-live-writes `
  --conversation <COMPLETED_DURABLE_CONVERSATION_ID> `
  --replications 3 `
  --closed-stability-ms 1000 `
  --timeout 150
```

If a product write has been attempted and the run fails, do **not** blindly
rerun. Review `failure_phase`, write counters, ambiguity/reconciliation fields,
and the already-created conversation state first.
