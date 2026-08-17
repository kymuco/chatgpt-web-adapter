# PR8.8 — Fresh-Tab Instant Selection, Pre-Submit Model-State Materialization and Model-Selection Network Characterization

## Status

Repair/characterization slice following the first Instant-mode zero-write preflight.

This slice does **not** change:

- generic `ChatGPTProductRuntime`,
- the library Browser Authority default (`PERSISTENT`),
- HDE assembly policy,
- canonical finality,
- Temporary production semantics,
- automatic-write retry policy.

## Why this repair exists

The first Instant preflight invalidated one assumption.

The operator manually selected `Instant` in an already-open `/c/<conversation_id>` tab. The zero-write preflight then opened a **fresh background tab for the exact same durable conversation** and proved:

```text
selected_mode = HIGH
selected_mode_proven = true
conversation_write_count = 0
runtime_tab_id_after = null
probe_tab_closed = true
foreground_activation_observed = false
debugger_attached_after = false
```

Therefore:

```text
durable conversation identity
!=
guaranteed fresh-tab model-picker state
```

The previous Instant runner correctly failed before spending the write budget. The repair must no longer assume that a manually selected mode in one renderer/tab is inherited by another renderer/tab.

## New boundary

Fresh-tab mode is now **characterization evidence**, not a precondition that must already equal Instant.

For every real Instant characterization turn:

```text
runtime tab exists
  ↓
read composer-local selected mode
  ↓
if mode != INSTANT:
    open product model picker
    select Instant through product UI
    prove composer-local mode == INSTANT
  ↓
existing Instant observer independently snapshots mode
  ↓
only then existing page-owned write path inserts prompt text
  ↓
conversation POST
```

The repair never edits request JSON to manufacture a model choice.

The selected mode is materialized through the same visible ChatGPT picker a human uses.

## Extension layering

The manifest and PR8.7 Temporary entrypoint remain unchanged.

```text
service_worker_observability.js
  -> service_worker_phase_timing_pr8_8.js
  -> service_worker_instant_mode_pr8_8.js
  -> service_worker_instant_selection_repair_pr8_8.js
```

This ordering matters.

The new repair is loaded **after** the read-only Instant observer and wraps `locateAndFocusComposer`.

During a real leased Instant turn:

1. Browser Authority and phase timing are already active.
2. The fresh runtime tab already exists.
3. The repair selects Instant if necessary.
4. The prior Instant wrapper is called only after selection.
5. The prior Instant wrapper therefore independently observes the repaired `INSTANT` state before input.

This preserves the existing write semantics while making the selection cost part of the measured pre-write path.

## Why selection happens inside `locateAndFocusComposer`

Selecting Instant before `executeNativeTurn` would hide cold model-selection cost outside the existing phase timing.

Instead selection happens inside the page-turn phase:

```text
page_turn_elapsed_ms
└─ tab_ready_to_write_delegated_ms
   ├─ composer readiness
   ├─ fresh-tab mode observation
   ├─ HIGH/MEDIUM/... -> Instant picker materialization
   └─ existing composer focus / prompt insertion / submit readiness
```

Therefore the measured cold path now represents the real cost HDE would pay when a recreated runtime tab does not inherit Instant.

## Product-UI selection

The repair uses bounded browser-local geometry:

1. find the visible composer,
2. find the nearest visible model-mode control,
3. use raw CDP mouse input to open it,
4. require exactly one visible actionable `Instant` option,
5. click that option,
6. poll the existing Instant snapshot until:

```text
selected_mode = INSTANT
selected_mode_proven = true
```

The picker action intentionally uses:

```text
chrome.debugger.sendCommand(... Input.dispatchMouseEvent ...)
```

rather than the adapter's patched `sendCommand()` helper.

Reason: the proven submit hotfix interprets generic mouse-release activity as potential send-button interaction. A model-picker click must never enter that submit fallback ladder.

The repair does not:

- call `Input.insertText`,
- call `submitOfficialPageTurn`,
- click a send button,
- modify raw request payloads,
- export DOM text.

## Pre-submit network characterization

The user's observation suggested a useful hypothesis:

> model-picker selection may be tab-local UI state, with the actual model choice materialized only when the subsequent conversation request is submitted.

This slice does not assume that hypothesis is true.

For every **actual model selection** it opens a bounded network-classification window immediately before the picker click and keeps it open until the real conversation POST boundary.

Only normalized request classes are retained:

```text
CHATGPT_READ
CHATGPT_SETTING_LIKE_MUTATION
CHATGPT_MUTATION_OTHER
OTHER_ORIGIN
INVALID_URL
```

The real conversation POST is the boundary and is not counted as a model-selection mutation.

No raw URL, query string, request body, response body, SSE, cookie, or authentication material is exported.

### Setting-like mutation

A same-origin non-conversation mutating request is classified as `CHATGPT_SETTING_LIKE_MUTATION` only when its path has a bounded setting-like signal such as:

```text
setting
preference
model
config
```

Other same-origin POST/PUT/PATCH/DELETE requests become:

```text
CHATGPT_MUTATION_OTHER
```

This avoids pretending that any arbitrary background mutation is definitely model persistence.

## Materialization statuses

For each turn that required picker selection:

```text
SETTING_LIKE_BACKEND_MUTATION_OBSERVED
OTHER_CHATGPT_MUTATION_OBSERVED
NO_CHATGPT_MUTATION_OBSERVED
NO_NETWORK_ACTIVITY_OBSERVED
UNEXPECTED_CONVERSATION_WRITE_DURING_SELECTION
```

When the fresh tab was already Instant:

```text
NO_SELECTION_REQUIRED
```

These are descriptive characterization labels only.

## Hard no-write-during-selection boundary

Before selection completes:

```text
conversation_write_count_during_selection must equal 0
unexpected_conversation_write_before_selection_complete must equal false
```

For a turn that actually performed selection, the observer must later see the real conversation POST boundary:

```text
conversation_write_boundary_observed = true
```

If a conversation POST appears before Instant selection is proven, the completed experiment is rejected and no write is retried.

## Fresh-tab preflight semantics

The existing zero-write exact-conversation probe is retained, but its meaning changes.

Old assumption:

```text
fresh exact-conversation tab must already be INSTANT
```

New rule:

```text
fresh exact-conversation tab mode must be proven
but may be HIGH / MEDIUM / INSTANT / another recognized picker mode
```

Still required:

```text
conversation_write_count = 0
probe_tab_closed = true
runtime_tab_id_after = null
foreground_activation_observed = false
debugger_attached_after != true
```

The report preserves the observed fresh-tab mode.

If the same result repeats, for example:

```text
cold_fresh_tab_initial_mode_counts = {"HIGH": 3}
cold_selection_performed_count = 3
warm_selection_performed_count = 0
```

that becomes direct repeated evidence that:

- recreated tabs hydrate in High in this environment,
- the same tab retains Instant across warm turns,
- Browser Authority recreation must include mode materialization when HDE requires Instant.

No generic product rule is inferred from one environment.

## Dedicated provider

The new characterization-only provider is:

```text
InstantSelectionRepairProvider
```

It extends the previous `InstantModeLatencyProvider`.

New read-only RPCs:

```text
characterizeInstantSelectionRepairSupport
characterizeInstantSelectionRecord
```

The generic provider/public runtime interfaces remain unchanged.

## Per-lease selection record

Every leased Instant turn has a separate lease-fenced record:

```text
instant_selection_lease_id
instant_selection_schema_version

selected_mode_before_selection
selected_mode_before_selection_proven
selection_performed

selection_elapsed_ms
selection_mutation_elapsed_ms

picker_mode_before_click
picker_candidate_count
picker_nearest_distance_px
instant_option_candidate_count

selected_mode_after_selection
selected_mode_after_selection_proven
selection_complete

conversation_write_boundary_observed
unexpected_conversation_write_before_selection_complete
conversation_write_count_during_selection

network_request_count_during_selection
chatgpt_request_count_during_selection
chatgpt_mutating_non_conversation_request_count
setting_like_mutation_observed
request_classes
model_selection_materialization_status
```

The prior Instant lease record remains independent and must still prove:

```text
selected_mode_before_write = INSTANT
selected_mode_before_write_proven = true
conversation_request_observed = true
reasoning_route_observed = false
```

This gives two independent UI checkpoints:

```text
repair:
selected_mode_after_selection = INSTANT

existing observer:
selected_mode_before_write = INSTANT
```

## Latency interpretation

If cold fresh tabs require `HIGH -> INSTANT`, that UI-selection time naturally increases:

```text
tab_ready_to_write_delegated_ms
```

This is intentional.

The experiment now measures:

```text
cold Browser Authority recreation
+
fresh-tab model-state materialization
+
page readiness
+
Instant product write
+
canonical finality
```

while warm turns measure:

```text
same retained tab
+
normally no re-selection
+
Instant product write
+
canonical finality
```

The report also exposes `selection_mutation_elapsed_ms` separately, so the extra cold cost can still be decomposed.

## No automatic retry

Unchanged:

```text
automatic_write_retry = false
```

If:

- picker selection fails,
- the Instant option is ambiguous,
- selected mode does not settle to Instant,
- a conversation write occurs during selection,
- selection observability is missing after a completed turn,
- the existing Instant observer sees a non-Instant mode,
- reasoning-route evidence appears,

the runner stops.

It does not replay a possibly accepted product write.

## Local regression command

```powershell
python -m pytest `
  tests/test_browser_authority_instant_selection_repair_pr8_8.py `
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

## Extension Reload

This slice changes the service-worker import graph.

After pulling:

```text
chrome://extensions
→ ChatGPT Web Adapter Browser Native Bridge
→ Reload exactly once
```

Chrome does not need to be closed.

## Zero-write support check

```powershell
python -c "from chatgpt_web_adapter.browser_authority_instant_selection_repair_pr8_8 import InstantSelectionRepairProvider; import json; p=InstantSelectionRepairProvider(); print(json.dumps({'selection': p.instant_selection_support(), 'instant': p.instant_mode_support(), 'phase': p.phase_timing_support()}, indent=2))"
```

Required core result:

```text
instant_selection_repair_supported = true
instant_selection_schema_version = 1
product_ui_selection_supported = true
pre_submit_network_classification_supported = true
conversation_write_boundary_supported = true
```

This performs zero product writes.

## Zero-write fresh-tab mode probe

The same existing read-only probe can still be run:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_instant_selection_repair_pr8_8 import InstantSelectionRepairProvider; import json; p=InstantSelectionRepairProvider(); print(json.dumps(p.selected_mode_preflight('6a82dabf-65b8-83eb-b8d5-5a86c6ba635d'), indent=2))"
```

`HIGH` is now a valid characterization result.

Required safety fields remain:

```text
selected_mode_proven = true
conversation_write_count = 0
probe_tab_closed = true
runtime_tab_id_after = null
foreground_activation_observed = false
debugger_attached_after != true
```

Do **not** manually select Instant in another tab as a prerequisite. The whole purpose of this repair is to materialize Instant inside each real runtime tab.

## Live command

Keep Instant auto-switch disabled in ChatGPT settings, then run:

```powershell
python -m chatgpt_web_adapter.browser_authority_instant_selection_repair_pr8_8 `
  --acknowledge-live-writes `
  --confirm-instant-auto-switch-disabled `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --replications 3 `
  --closed-stability-ms 1000 `
  --timeout 150
```

Maximum happy-path budget:

```text
9 real product writes
0 automatic retries
```

## Expected successful evidence

Core:

```text
ok = true
write_attempts = 9
write_completions = 9

fresh_tab_mode_preflight_proven = true
instant_materialized_before_every_write = true
conversation_writes_during_model_selection = 0
fresh_tab_picker_state_not_assumed_from_conversation = true

instant_selected_before_every_write = true
positive_reasoning_route_observations = 0

all_cold_turns_created_new_runtime_tab = true
all_warm_turns_reused_same_runtime_tab = true
all_close_turns_reused_then_closed_runtime_tab = true
all_closed_windows_stable = true

automatic_write_retry_attempted = false
final_runtime_status.runtime_tab_id = null
```

Interesting characterization blocks:

```text
fresh_tab_mode_preflight
instant_selection_materialization
instant_latency_characterization
model_route_characterization
```

Especially:

```text
cold_fresh_tab_initial_mode_counts
cold_selection_performed_count
warm_selection_performed_count
selection_mutation_elapsed_ms
materialization_status_counts
setting_like_mutation_observed_count
request_classes_observed
```

## Policy status

Still unchanged:

```text
library default = PERSISTENT
HDE policy change = false
```

The correct next step after a successful repaired Instant run is to compare:

1. previous High/reasoning phase attribution,
2. repaired Instant cold/warm distributions,
3. explicit Instant picker-materialization cost,

before moving to Idle-TTL calibration.
