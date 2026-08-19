# PR8.8 — Slider Thumb-vs-Track Geometry, ARIA Discrete-Range Semantics, Sibling/Tick Label Association and Advanced-Control Identity Dealiasing Governance

## Why this slice exists

The retained quick-picker specimen established the actual current-effort trigger and a real ARIA slider:

```text
current effort control = HIGH
aria-haspopup = menu
aria-expanded = true
data-state = open

role=slider
aria-valuemin = 0
aria-valuemax = 2
aria-valuenow = 2
rect = 28 x 28
```

The 28×28 slider rect is consistent with a thumb/handle rather than the full visual track. The previous geometry therefore produced a false `HIGH -> normalized_position=0` result by projecting labels against the thumb rectangle.

The same specimen also produced `advanced_button_count=2` for one visually observed `Расширенные` control, showing DOM identity aliasing.

This slice repairs only the observation model. It does not select Instant, move the slider, open/close quick or Advanced surfaces, change model/effort, insert prompt text, submit a turn, retry, navigate, or close a tab.

## Thumb vs track

The probe treats `role=slider` / `input[type=range]` as the semantic slider endpoint. Its rect is recorded as the thumb geometry; a track is searched independently among nearby parent/sibling component nodes.

Track candidates must be elongated on the slider axis, aligned with the thumb center, contain the thumb center along the axis, and not themselves classify as effort labels, Advanced controls, or buttons. Candidates are bounded and ranked; uncertainty is preserved if no plausible track is found.

## ARIA discrete range

The semantic range is read directly from ARIA/native numeric fields:

```text
min
max
now
step_count = max - min + 1
current_step_index = now - min
```

Only small integral ranges are classified as discrete. For the observed `0..2` range, `step_count=3`. `HIGH` is considered consistent with the current endpoint only when the current effort control is `HIGH` and `aria-valuenow == aria-valuemax`.

The probe does not infer `0=Instant` and `1=Medium` from the numeric range alone.

## Sibling / tick-label association

Effort labels are searched across the local visible component neighborhood rather than only descendants of the slider thumb. Minimal mode-bearing nodes are associated with the best track by bounded distance and projected onto the track axis.

A complete mapping is proven only when all three labels are observed geometrically in the order:

```text
INSTANT -> MEDIUM -> HIGH
```

and that ordering agrees with the integral ARIA range and the current `HIGH == max` state.

The resulting mapping is evidence, not a selector mutation.

## Advanced identity dealiasing

All visible `Advanced / Расширенные` DOM candidates are grouped into logical controls. Candidates belong to the same equivalence class when they are ancestor/descendant aliases, have near-identical geometry, or strongly overlap.

The probe distinguishes:

```text
DOM candidate count
!=
logical control count
```

A preferred target is exported only when one logical group contains a non-disabled pointer-enabled `button/[role=button]` candidate. No Advanced click is performed in this slice.

## Governance

Support advertises:

```text
thumbTrackSeparationSupported
ariaDiscreteRangeSemanticsSupported
siblingTickAssociationSupported
advancedControlDealiasingSupported
retainedExistingTabProbeSupported
selectionControlClickForbidden
uiNavigationClickForbidden
zeroProductWrites = true
automaticRetry = false
rawTextRedactionSupported
leaseIdExported = false
```

The topology probe is fenced to the exact retained runtime tab and durable conversation route. It attaches CDP only for `Runtime.evaluate` and detaches before returning. No Network domain, mouse/keyboard input, prompt, submit, tab lifecycle action, response body, cookie, raw text, URL, HTML, or lease token is exported.

## Shipping threshold

This slice is intentionally not another release blocker. Once the geometry contract can support a bounded selector repair, the adapter should move to real workloads rather than continue open-ended picker forensics.

A pragmatic repair may rely on:

1. the proven unique current-effort trigger;
2. the semantic discrete ARIA slider range;
3. a proven step mapping when available;
4. fail-closed behavior when the UI topology no longer matches the characterized contract.

Rare or changed layouts should become compatibility failures discovered and repaired from real usage, not a reason to indefinitely delay the usable product runtime.

No new live characterization run is required merely to land this PR.
