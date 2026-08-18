# PR8.8 — Reasoning-Effort Slider Topology, Discrete Step-to-Mode Mapping, Quick-vs-Advanced Picker Dimension Separation and Zero-Write Interaction-Target Governance

## Motivation

Current ChatGPT web UI evidence shows that the composer control displaying the current effort (for example `Высокий`) opens a quick reasoning-effort surface. `Instant / Средний / Высокий` are presented as discrete slider states, while `Расширенные` navigates to an advanced surface separating `Модель` from `Усилие`.

The previous Instant repair assumed `Instant` would materialize as a button/menuitem. That assumption is no longer accepted.

## Scope

This slice does not select Instant, change model, change effort, insert prompt text, submit a turn, retry a turn, close a tab, or navigate the browser route.

Two optional UI-navigation actions are supported only with explicit opt-in:

1. click the unique current-effort composer control to open the quick picker;
2. click the unique `Advanced / Расширенные` navigation control.

No slider, model row, effort row, model value, or effort value is clicked. Conversation POST count must remain zero.

## Quick surface characterization

The probe records a bounded normalized topology:

- current effort control identity and nearest-composer distance;
- quick surface role/rect and recognized effort enum set;
- every visible `role=slider` or `input[type=range]` on the selected surface;
- slider orientation and bounded ARIA/native numeric state;
- discrete effort labels mapped to the nearest slider;
- normalized label position on the slider track;
- ordered discrete mapping;
- unique `Advanced` navigation target.

A complete three-step mapping requires all three enum values on one slider:

```text
INSTANT → MEDIUM → HIGH
```

The mapping is geometric evidence, not an assumption from label order in the DOM.

## Advanced surface characterization

If explicitly requested, the probe clicks only the unique `Advanced / Расширенные` target and then observes the advanced surface.

It proves dimension separation only when:

```text
MODEL control count  = 1
EFFORT control count = 1
MODEL target != EFFORT target
```

Visible values are exported only as enums:

```text
models: GPT_5_6_SOL / GPT_5_5 / O3
effort: INSTANT / MEDIUM / HIGH
```

If choices are not materialized on the advanced surface without another navigation click, the corresponding visible-values list remains empty. This slice does not click deeper dimension controls.

## Interaction governance

The extension support contract advertises:

```text
retainedExistingTabProbeSupported
sliderTopologySupported
discreteStepMappingSupported
quickAdvancedDimensionSeparationSupported
uiNavigationOptInSupported
selectionControlClickForbidden
conversationWriteGuardSupported
rawTextRedactionSupported
leaseIdExported = false
zeroProductWrites = true
automaticRetry = false
```

The probe is fenced to the retained runtime tab and exact durable conversation route. It preserves the existing Browser Authority lease and never exports the lease token.

## Live gate

After syncing and reloading the extension once, use an existing retained runtime tab for the target conversation.

Support:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_reasoning_effort_slider_pr8_8 import ReasoningEffortSliderProvider; import json; p=ReasoningEffortSliderProvider(); print(json.dumps(p.reasoning_effort_slider_support(), indent=2))"
```

If the quick picker is already open, perform a strictly read-only characterization:

```powershell
python -m chatgpt_web_adapter.browser_authority_reasoning_effort_slider_live_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d
```

If it is closed, explicitly allow only the quick-surface navigation click:

```powershell
python -m chatgpt_web_adapter.browser_authority_reasoning_effort_slider_live_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --open-quick-picker `
  --allow-ui-navigation
```

To characterize quick and advanced surfaces in one zero-product-write probe:

```powershell
python -m chatgpt_web_adapter.browser_authority_reasoning_effort_slider_live_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --open-quick-picker `
  --inspect-advanced-surface `
  --allow-ui-navigation
```

The advanced surface is intentionally left open for evidence preservation. Do not manually choose a model or effort while the probe is running.
