# PR8.8 — Instant-Mode Phase-Level Latency Characterization, No-Reasoning Route Evidence, Warm-vs-Cold Browser Overhead Ratio and Cross-Mode Governance

## Status

Implementation/live-gate preparation only. This slice does **not** change the generic browser-authority default, HDE assembly policy, Temporary semantics, canonical finality, or automatic-retry policy.

## Why this slice exists

The previous PR8.8 phase-level run isolated Browser Authority recreation from the much larger end-to-end ChatGPT turn:

- cold `runtime_tab_first_resolve_ms` was about 1.5–2.1 s,
- warm lookup was approximately 0–1 ms,
- the cold path added roughly 2.6–3.4 s before the page-owned write was delegated,
- later network/native/canonical phases were much noisier.

Those measurements came from the model mode active during that run. They do not answer how large Browser Authority overhead feels when the product itself is configured for its fastest non-reasoning path.

This slice therefore measures the same fixed durable conversation under a manually prepared **Instant** configuration.

## Product-mode boundary

A visible `Instant` label alone is insufficient evidence for a reasoning-free baseline because ChatGPT can be configured to let Instant auto-switch to a deeper reasoning mode.

The live operator must therefore:

1. open ChatGPT settings,
2. disable the setting that allows Instant to auto-switch to deeper reasoning,
3. select `Instant` for the fixed durable conversation,
4. pass the explicit CLI confirmation flag.

The runner does not click the model picker and does not change product settings.

## Evidence model

The gate deliberately keeps three evidence channels separate.

### 1. Exact-conversation selected-mode preflight

Before any live write, a read-only extension probe:

- requires the Browser Authority runtime tab to be absent,
- opens the exact `/c/<conversation_id>` route in the dedicated background runtime tab,
- waits for the composer,
- inspects only visible composer-local mode controls,
- normalizes the selected mode to a bounded enum,
- performs no typing or submission,
- counts conversation-write network requests and requires exactly zero,
- detaches the debugger,
- closes the probe tab,
- verifies the runtime-tab baseline is absent again.

Required result:

```text
selected_mode = INSTANT
selected_mode_proven = true
conversation_write_count = 0
probe_tab_closed = true
runtime_tab_id_after = null
debugger_attached_after != true
foreground_activation_observed = false
```

If this cannot be proven, the runner stops with **zero product writes**.

### 2. Explicit operator confirmation

The CLI requires:

```text
--confirm-instant-auto-switch-disabled
```

This is an operator attestation, not browser-derived proof. It is intentionally represented as a distinct field in the report and is never silently upgraded into network proof.

### 3. Browser-local request/response route evidence

For each real product write, the extension observes only bounded model/reasoning metadata:

- the selected mode immediately before input,
- recognized model/mode keys in the conversation request,
- recognized model/reasoning keys in safe parsed response metadata.

The extension does **not** export:

- prompt text,
- assistant text,
- raw request JSON,
- raw SSE,
- raw DOM,
- cookies,
- authentication data.

Only normalized mode enums, short safe model identifiers, allowlisted metadata-key names, and boolean route conclusions are persisted.

The route classifier can report:

```text
INSTANT_MODEL_ROUTE_OBSERVED
NO_REASONING_EXPLICITLY_OBSERVED
REASONING_ROUTE_OBSERVED
INCONCLUSIVE
```

`REASONING_ROUTE_OBSERVED` is a hard contradiction and stops all later writes after the already-completed turn. It is never retried automatically.

`INCONCLUSIVE` is not promoted to network proof. The run may still characterize the operator-confirmed Instant baseline when:

- Instant is proven immediately before every write,
- the operator explicitly confirmed auto-switch disabled,
- no positive reasoning-route evidence is observed.

The report separately counts network-proven no-reasoning turns and inconclusive turns.

## Extension layering

The manifest and PR8.7 top-level Temporary worker remain unchanged.

Existing chain:

```text
Temporary wrappers
  -> runtime-tab reconciliation / Browser Authority lease
  -> provisioning observability
  -> phase timing
  -> stale-UI recovery
  -> proven browser-owned page write
```

This slice adds one imported layer inside existing provisioning observability:

```text
service_worker_observability.js
  -> service_worker_phase_timing_pr8_8.js
  -> service_worker_instant_mode_pr8_8.js
```

`service_worker_instant_mode_pr8_8.js` itself imports nothing. It is loaded only after the already-proven phase-timing layer, then wraps the same functions without replacing product-write semantics.

No manifest bump is required, but an unpacked-extension **Reload is required** after pulling the commit because the worker import graph changed.

## Dedicated provider boundary

The generic `BrowserNativeTurnProvider` and public `ChatGPTProductRuntime` APIs are not widened.

`InstantModeLatencyProvider` is a characterization-only subclass. It injects:

```text
requiredModelMode = INSTANT
requireNoReasoningRoute = true
```

only into leased real product-turn RPCs issued by this experiment.

It does not inject those fields into:

- ping/status,
- resource characterization,
- phase-timing queries,
- model-mode read-only probes,
- runtime-tab release.

## Live topology

Default run:

```text
fixed completed durable conversation
closed Browser Authority baseline

read-only exact-conversation Instant preflight
  -> zero writes
  -> close probe tab
  -> baseline closed again

cycle 1:
  cold PERSISTENT Instant
  warm PERSISTENT Instant
  TURN_SCOPED Instant close
  stable closed window

cycle 2:
  same

cycle 3:
  same
```

Maximum happy-path budget:

```text
3 cycles × 3 writes = 9 real product writes
```

No automatic product-write retry exists in the runner.

## Prompts

Each product turn is a short exact-reply baseline:

```text
Reply with exactly: SDK_PR8_8_INSTANT_LATENCY_01_COLD_OK
Reply with exactly: SDK_PR8_8_INSTANT_LATENCY_01_WARM_OK
Reply with exactly: SDK_PR8_8_INSTANT_LATENCY_01_CLOSE_OK
...
```

The task is intentionally trivial so model-side generation work is bounded and repeatable.

## Timing fields

The existing phase timing remains authoritative:

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
total_ms
```

The Instant runner additionally reports:

```text
cold_over_warm_total_ratio
cold_recreation_share_of_total
cold_prewrite_penalty_ms
cold_prewrite_penalty_share_of_warm_total
```

These make the policy question visible in relative terms. A ~2–3 s cold penalty can be negligible in a long reasoning turn but dominant in a very short Instant turn.

## Cross-mode governance

This run intentionally does not embed the earlier reasoning-mode JSON as a production constant.

The report therefore records:

```text
prior_reasoning_phase_report_embedded = false
cross_mode_numeric_verdict_performed = false
reasoning_reference_required_for_cross_mode_verdict = true
```

After the live Instant result exists, compare it against the prior phase-attribution report using the same phase names. Only then may a human review whether Browser Authority retention matters materially more for Instant.

No automated threshold changes:

```text
library default = PERSISTENT
library_default_change_performed = false
hde_assembly_policy_change_performed = false
```

## Hard invariants

Every successful run must preserve:

```text
same completed durable conversation across every pair
NORMAL -> NORMAL product semantics
canonical finality proven for every write
PERSISTENT for cold/warm
TURN_SCOPED ttl=0 for close
cold creates a runtime tab
warm reuses that exact tab
close reuses and then closes that exact tab
stable tab absence between cycles
unique Browser Authority lease IDs
strictly increasing Browser Authority generations
Temporary production mode remains disabled
no automatic write retry
final runtime_tab_id = null
```

## Fail-closed behavior

### Before any write

The runner stops with zero writes if:

- the new extension support surface is unavailable,
- phase timing support is unavailable,
- a runtime tab is already present,
- the fixed conversation is not canonically completed,
- runtime governance changed,
- exact-conversation selected Instant cannot be proven,
- the read-only mode probe performs any conversation write,
- the probe leaves a tab/debugger behind,
- the probe unexpectedly foreground-activates the runtime tab,
- the operator confirmation flag is absent.

### After a completed write

The runner stops and never retries if:

- phase timing is missing/inconsistent,
- the selected mode before that write is not proven Instant,
- the conversation request is not observed,
- positive reasoning-route evidence is observed,
- lease fencing mismatches,
- canonical conversation identity changes,
- warm reuse/close semantics fail.

A completed turn remains completed even if post-write observability rejects the measurement. The runner does not replay it.

## Local regression command

```powershell
python -m pytest `
  tests/test_browser_authority_instant_latency_pr8_8.py `
  tests/test_browser_authority_phase_cost_attribution_pr8_8.py `
  tests/test_browser_authority_policy_replication_pr8_8.py `
  tests/test_browser_authority_live_characterization.py `
  tests/test_browser_authority_lease_extension_assets.py `
  tests/test_browser_native_temporary_probe_extension.py `
  tests/test_browser_native_provider_pr8_8.py `
  tests/test_browser_owned_write_runtime_pr8_8.py `
  tests/test_product_runtime_browser_authority_pr8_8.py `
  tests/test_product_runtime.py `
  tests/test_product_transport_protocol.py `
  -q
```

## Required product preparation before live run

1. Keep Chrome running.
2. Open ChatGPT Settings -> General.
3. Disable the setting that allows Instant to auto-switch to a deeper reasoning mode.
4. Open the fixed durable conversation used by the previous phase-level experiment.
5. Select `Instant` in the model picker for that conversation.
6. Do not send a manual message after preparing it.
7. Pull this commit.
8. Reload the unpacked ChatGPT Web Adapter extension exactly once.
9. Leave the Browser Authority runtime tab absent before starting the runner.

The runner itself performs an exact-conversation zero-write probe before spending the live-write budget.

## Read-only support check

After extension Reload, before live writes:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_instant_latency_pr8_8 import InstantModeLatencyProvider; import json; p=InstantModeLatencyProvider(); print(json.dumps({'instant': p.instant_mode_support(), 'phase': p.phase_timing_support()}, indent=2))"
```

Expected core fields:

```json
{
  "instant": {
    "instant_mode_supported": true,
    "instant_mode_schema_version": 1,
    "selected_mode_probe_supported": true,
    "request_route_observation_supported": true,
    "response_route_observation_supported": true
  },
  "phase": {
    "phase_timing_supported": true,
    "phase_timing_schema_version": 1
  }
}
```

This check performs zero product writes.

## Optional exact-conversation zero-write mode probe

The runner performs this automatically, but it can be inspected first:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_instant_latency_pr8_8 import InstantModeLatencyProvider; import json; p=InstantModeLatencyProvider(); print(json.dumps(p.selected_mode_preflight('6a82dabf-65b8-83eb-b8d5-5a86c6ba635d'), indent=2))"
```

Expected:

```text
selected_mode = INSTANT
selected_mode_proven = true
conversation_write_count = 0
probe_tab_closed = true
runtime_tab_id_after = null
foreground_activation_observed = false
debugger_attached_after != true
```

If this is not proven, do not start the live run.

## Live command

```powershell
python -m chatgpt_web_adapter.browser_authority_instant_latency_pr8_8 `
  --acknowledge-live-writes `
  --confirm-instant-auto-switch-disabled `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --replications 3 `
  --closed-stability-ms 1000 `
  --timeout 150
```

## Expected successful summary

```text
instant_latency_characterization_completed = true
replication_count = 3
exact_conversation_instant_preflight_proven = true
instant_selected_before_every_write = true
manual_instant_auto_switch_disabled_confirmed = true
positive_reasoning_route_observations = 0
all_cold_turns_created_new_runtime_tab = true
all_warm_turns_reused_same_runtime_tab = true
all_close_turns_reused_then_closed_runtime_tab = true
all_closed_windows_stable = true
same_completed_conversation_used_for_every_pair = true
canonical_finality_preserved_across_all_writes = true
phase_timing_preserved_across_all_writes = true
cross_mode_verdict_deferred_until_reference_comparison = true
default_policy_change_performed = false
write_budget_respected = true
automatic_write_retry_attempted = false
```

Network-route evidence may be either proven or inconclusive. A successful report must always preserve:

```text
positive_reasoning_route_observations = 0
```

and reports exact counts for:

```text
network_no_reasoning_route_proven_count
network_route_inconclusive_count
```

## Interpretation after live PASS

The next analysis should compare the Instant distributions against the previous phase-level run, especially:

```text
warm total_ms
cold total_ms
runtime_tab_first_resolve_ms
tab_ready_to_write_delegated_ms
write_delegated_to_native_complete_ms
post_release_canonical_return_ms
cold recreation share of Instant total latency
cold pre-write penalty share of warm Instant latency
```

Only after that comparison should PR8.8 proceed to Idle-TTL calibration or HDE assembly policy selection.
