# PR8.8 — Production Reasoning-Effort Selection Repair and Instant Working Path

## Purpose

This is the shipping transition for the PR8.8 Instant line.

The current ChatGPT web UI has been characterized sufficiently to stop treating
`Instant` as a button/menuitem. The current effort control opens a quick picker
containing a semantic ARIA slider. Live evidence established:

```text
current effort control = HIGH
aria-haspopup = menu
aria-expanded = true
data-state = open

role = slider
aria-valuemin = 0
aria-valuemax = 2
aria-valuenow = 2
```

The production repair uses that semantic control directly. It does not require
another geometry probe before use.

## Working path

For a leased write that explicitly requires `INSTANT`:

```text
prove current selected effort
→ if already INSTANT: continue
→ locate the unique current-effort composer control
→ open the quick picker through the existing product-UI click
→ require exactly one nearby visible semantic slider with:
     min = 0
     max = 2
     integral current value
     three discrete steps
→ focus the slider itself
→ dispatch the standard Home key
→ independently prove composer-selected mode == INSTANT
→ only then continue the existing prompt insertion / page-owned write
```

`Home` is deliberately preferred over guessed track coordinates. The slider is
an ARIA control and its observed DOM rect is thumb-sized, so coordinate selection
against an inferred visual track would be less stable.

## Fail-closed conditions

No prompt insertion is allowed if any of these fail:

- current selected mode is not proven;
- current-effort trigger is missing/ambiguous;
- picker identity does not match the pre-click selected mode;
- the quick picker does not expose one exact `0..2` semantic slider;
- slider focus is not proven;
- a conversation write is observed before selection completes;
- the UI does not settle to independently proven `INSTANT`;
- a still-visible slider does not reach its minimum after `Home`.

There is no fallback to the obsolete `Instant` menuitem selector and no automatic
write retry.

## Explicit non-goals

The repair does not:

- open `Advanced / Расширенные`;
- click a model control;
- click an effort row/value;
- mutate request JSON to choose a model;
- synthesize hidden product state;
- retry a possibly accepted product write.

The normal official-page conversation write remains unchanged after the
pre-input selection proof.

## Usable provider

`InstantEffortSelectionProvider` subclasses the existing Instant Browser
Authority provider. It can be passed directly to the product runtime:

```python
from chatgpt_web_adapter.browser_authority_instant_working_path_pr8_8 import (
    InstantEffortSelectionProvider,
)
from chatgpt_web_adapter.product_runtime import assemble_product_runtime

provider = InstantEffortSelectionProvider()
runtime = assemble_product_runtime(client=client, provider=provider)
```

Every real leased turn through that provider requests Instant and uses the
reasoning-effort slider repair before prompt insertion.

## One shipping smoke

After extension Reload, run one live smoke only:

```powershell
python -m chatgpt_web_adapter.browser_authority_instant_working_path_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --acknowledge-live-writes `
  --confirm-instant-auto-switch-disabled `
  --timeout 150 `
  | Tee-Object -FilePath .\instant-working-path-pr8_8.json
```

The smoke uses one `TURN_SCOPED` product write so the Browser Authority runtime
tab is disposed after release. Do not blind-retry after `write_attempts = 1`.

A successful result requires:

```text
selected_mode_after_selection = INSTANT
selection_mechanism = REASONING_EFFORT_SLIDER_HOME
effort_slider_candidate_count = 1
effort_slider_aria_value_min = 0
effort_slider_aria_value_max = 2
effort_slider_step_count = 3
effort_slider_focus_proven = true
effort_slider_home_dispatched = true
conversation_write_count_during_selection = 0
reasoning_route_observed = false
canonical_status = completed
```

If this single shipping smoke passes, further picker research is no longer a
prerequisite for using the adapter. Future UI variants should be handled as
compatibility failures discovered by real workloads.
