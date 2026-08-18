# PR8.8 — Model-Picker Trigger Identity, Click-Actuation Verification, Per-Poll Menu-Materialization Timeline and False-Open Surface Dealiasing Governance

## Motivation

Live evidence for `instant_option_missing` established a clean target route and a pre-input failure, but the exact failure-time popup probe returned `NO_MODE_POPUP_FOUND`. A later zero-write retained probe on the same tab reported `picker_surface_open=true` only because generic `role=group` surfaces existed; every such surface had `descendantKnownModeCount=0`, while DOM and AX recognized no model modes.

Therefore:

```text
generic popup-like surface present
!=
model-picker menu materialized
```

This slice characterizes the first picker click itself. It does not broaden the Instant selector.

## Existing mutation, new observation

The production characterization still performs the same single product-UI picker click and the same 100 ms Instant-option polling. Three additive workers observe that existing path:

```text
picker point resolved
→ PRE_CLICK trigger snapshot
→ existing raw CDP picker click exactly once
→ POST_CLICK_IMMEDIATE snapshot
→ existing Instant-option poll loop
   → OPTION_POLL snapshot after every poll
→ persist bounded timeline under the same lease on failure
→ rethrow the exact original error object
```

No new click, retry, navigation, tab creation/close, debugger attach, prompt insertion, submit, response-body read, cookie access, or raw DOM/text export is added.

## Trigger identity

The already-resolved mode-bearing picker point is re-associated with the nearest matching visible `button/[role=button]`. The probe exports only bounded structure: tag, role, rect, direct/subtree mode enums, `aria-haspopup`, `aria-expanded`, `data-state`, disabled/pointer state, child count, plus the nearest ancestor carrying menu/open-state semantics and its hop distance.

This separates:

```text
HIGH-bearing display/control
!=
proven menu trigger
```

## Per-poll materialization timeline

Each bounded sample records:

```text
phase / poll_index / elapsed_ms
option_found / option_candidate_count
picker candidate + nearest trigger state
generic popup surface count
generic menu count
mode-bearing popup surface count
recognized model-mode enums
max known-mode descendants
mode_picker_materialized
false_open_generic_only
```

Best-seen evidence preserves first/last mode-bearing popup time, first trigger-open signal, trigger-state transition, maximum mode-bearing surfaces/known descendants, recognized modes, and best selected mode surface. A short-lived picker cannot be erased by the final timeout state.

Outcomes:

```text
MODE_BEARING_PICKER_MATERIALIZED
TRIGGER_ACTUATED_WITHOUT_MODE_PICKER
CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION
PICKER_CLICK_NOT_CONFIRMED
```

For the target `instant_option_missing`, `NO_MODE_POPUP_FOUND` is valid evidence rather than a runner failure. The target still requires a captured picker point, completed existing click dispatch, and `PRE_CLICK`, `POST_CLICK_IMMEDIATE`, and `OPTION_POLL` phases.

## False-open dealiasing

The existing retained field is preserved as `legacy_picker_surface_open`, while the new report derives:

```text
generic_popup_surface_count
mode_bearing_popup_surface_count
mode_bearing_picker_surface_open
false_open_generic_only
```

So `legacy_picker_surface_open=true` with zero mode-bearing surfaces is no longer described as a proven open model picker.

## Persistence and privacy

The timeline is stored under the same private Browser Authority lease and is returned only through the existing exact-lease failure-record lookup. The lease token remains redacted. `raw_url_exported`, `raw_text_exported`, `raw_html_exported`, and `lease_id_exported` remain false; `zero_product_writes=true` and `automatic_retry=false` are required.

Support adds:

```text
pickerTriggerIdentitySupported
clickActuationVerificationSupported
perPollMenuMaterializationTimelineSupported
falseOpenSurfaceDealiasingSupported
triggerTimelinePersistenceSupported
rawTriggerTextRedactionSupported
```

The previously published fresh-failure CLI is unchanged. This slice has a dedicated live runner.

## Live gate

Start from:

```text
runtime_tab_id = null
lease_id_present = false
```

After extension Reload, run once:

```powershell
python -m chatgpt_web_adapter.browser_authority_picker_trigger_timeline_live_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --acknowledge-live-writes `
  --confirm-instant-auto-switch-disabled `
  --timeout 150 `
  --forensics-timeout 20
```

Do not blind-retry after `write_attempts=1`.

Decisive fields are `picker_trigger_timeline.timeline_samples`, `picker_trigger_timeline.best_seen`, `picker_trigger_timeline.materialization_outcome`, the trigger-state summary, and the false-open-dealiased topology summary.
