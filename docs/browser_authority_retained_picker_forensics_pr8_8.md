# PR8.8 — Retained Failed-Picker Surface Forensics, DOM/Accessibility Instant-Option Topology Characterization and Zero-Write Reconciliation Governance

## Status

Forensic/reconciliation slice after the first fresh-tab Instant-selection repair failed at:

```text
PR8_8_INSTANT_SELECTION_OPTION_NOT_FOUND:instant_option_missing
```

The failed run spent one Browser Authority attempt but completed zero product writes. Canonical readback afterwards remained:

```text
canonical_status = completed
ready = true
```

and the failed cold runtime tab remained retained with Browser Authority lease metadata.

This slice does not retry that write and does not guess another picker selector.

## Goal

Use the retained failed runtime tab as a forensic specimen before changing model-selection logic:

```text
retained failed runtime tab
  -> exact tab + conversation fence
  -> canonical completed preflight
  -> attach debugger read-only
  -> capture bounded DOM picker topology
  -> capture bounded Accessibility topology
  -> count conversation writes during probe
  -> detach debugger
  -> prove exact tab still retained
  -> canonical completed recheck
```

Default probe behavior performs:

```text
product writes = 0
picker clicks = 0
model changes = 0
prompt insertion = 0
submit actions = 0
tab close = 0
```

## Why a dedicated forensic layer

The first repair successfully proved the fresh runtime tab was in `HIGH` and found the composer-local picker control. It then clicked that control, but its option search only considered a narrow actionable selector set and found zero `INSTANT` candidates.

That does not prove Instant is unavailable. It proves the current DOM/accessibility topology differs from the repair's selector model.

The next selector repair must therefore be derived from observed topology rather than another blind DOM guess.

## Extension layering

The manifest and PR8.7 Temporary top-level worker remain unchanged.

```text
service_worker_observability.js
  -> service_worker_phase_timing_pr8_8.js
  -> service_worker_instant_mode_pr8_8.js
  -> service_worker_instant_selection_repair_pr8_8.js
  -> service_worker_retained_picker_forensics_pr8_8.js
```

The new worker wraps only characterization RPC dispatch. Ordinary product-write semantics still delegate to the prior worker unchanged.

## DOM topology evidence

The forensic worker never exports raw DOM/HTML or unrestricted page text.

It returns bounded structural records for at most 80 visible candidates and 24 popup surfaces. Candidate fields include:

```text
tag
role
recognized mode enum(s)
mode evidence = DIRECT / SUBTREE / NONE
aria-checked
aria-selected
aria-expanded
aria-haspopup
bounded data-state enum
tabIndex
disabled
pointer-events enabled
rounded bounding rect
bounded ancestor roles
child element count
descendant actionable count
```

Known model labels are normalized only to bounded enums:

```text
INSTANT
MEDIUM
HIGH
EXTRA_HIGH
PRO_STANDARD
PRO_EXTENDED
REASONING_OTHER
PRO_OTHER
```

No arbitrary label text is exported.

## Accessibility topology evidence

The worker calls the Chrome DevTools Accessibility domain and records at most 80 relevant AX nodes.

Per-node evidence is bounded to:

```text
AX role
recognized model enum
mode evidence = NAME / DESCRIPTION / NONE
ignored
parent role
checked
selected
expanded
focusable
disabled
backendDOMNodeId presence
child count
```

Again, raw accessible names/descriptions are not exported; they are only used browser-locally to classify known model-mode enums.

This is specifically intended to reveal cases such as:

```text
DOM repair expected: role=menuitem/option/radio/button
actual AX topology:   role=menuitemradio
```

or a nested descendant carrying `Instant` while the actionable ancestor itself has no direct label.

## Retained-tab fencing

The probe requires the retained runtime tab to already exist.

The caller supplies:

```text
expected_runtime_tab_id
conversation_id
```

The extension requires:

```text
stored runtime tab == expected runtime tab
current tab is ChatGPT
/c/<conversation_id> == expected conversation
```

The Python runner additionally requires before the forensic probe:

```text
Browser Authority characterization supported
runtime-tab release supported
lease metadata present
runtime.health.ready = true
canonical_status = completed
runtime_tab_id == expected_runtime_tab_id
```

The same canonical completed state is checked again after the probe.

## Conversation-write guard

While debugger is attached, the worker observes network request boundaries and counts official conversation POSTs.

Required:

```text
conversation_write_count = 0
zero_product_writes = true
```

Any conversation write observed during the forensic probe rejects the probe.

The worker itself contains no:

```text
Input.dispatchMouseEvent
Input.insertText
submitOfficialPageTurn
chrome.tabs.remove
```

## Debugger / foreground governance

The retained tab is not activated by the probe.

Required:

```text
tab_activated_during_probe = false
debugger_attached_before != true
debugger_attached_after != true
```

The report preserves whether the retained tab happened to already be active, but a pre-existing active tab is not confused with activation caused by the probe.

## Stored lease evidence

The forensic worker returns the current stored Browser Authority lease ID as fencing metadata only.

This does not grant product authority and does not alter lease state. It exists so an explicitly requested reconciliation close can reuse the already-existing exact lease+tab fenced release mechanism.

## Reconciliation close

Default run does **not** close the retained tab.

An optional explicit CLI flag exists:

```text
--reconcile-close-after-forensics
```

Close is permitted only after:

```text
canonical completed before probe
exact retained tab proven
zero conversation writes
forensics completed
exact tab still retained
canonical completed after probe
stored lease ID available
```

Then the runner calls the existing non-retried provider operation:

```text
release_runtime_tab(
  expected_runtime_tab_id=<exact tab>,
  browser_authority_lease_id=<stored lease>
)
```

This is Browser Authority resource lifecycle only. It does not mutate durable conversation identity or send a ChatGPT product message.

For the current investigation, the first forensic run should **not** use the close flag. We want to inspect the topology report before deciding whether to preserve or close the specimen.

## Zero-write support check

After extension Reload:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_retained_picker_forensics_pr8_8 import RetainedPickerForensicsProvider; import json; p=RetainedPickerForensicsProvider(); print(json.dumps(p.retained_picker_forensics_support(), indent=2))"
```

Required:

```text
retained_picker_forensics_supported = true
retained_picker_forensics_schema_version = 1
retained_existing_tab_probe_supported = true
dom_topology_supported = true
accessibility_topology_supported = true
conversation_write_guard_supported = true
fenced_reconciliation_close_supported = true
zero_product_writes = true
```

## Forensic command for the currently retained specimen

Do not close the retained runtime tab before this command.

```powershell
python -m chatgpt_web_adapter.browser_authority_retained_picker_forensics_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --expected-runtime-tab-id 1949460340 `
  --timeout 20
```

No `--acknowledge-live-writes` flag exists because this runner has no product-write path.

Expected top-level properties:

```text
product_write_budget = 0
write_attempts = 0
write_completions = 0
reconcile_close_requested = false
reconcile_close_performed = false
```

Interesting evidence:

```text
forensics.picker_surface_open
forensics.recognized_modes
forensics.instant_dom_candidate_count
forensics.instant_ax_candidate_count
forensics.dom_topology.popup_surfaces
forensics.dom_topology.dom_candidates
forensics.accessibility_topology.candidates
topology_summary
```

## Optional later fenced close

Only after reviewing the forensic report:

```powershell
python -m chatgpt_web_adapter.browser_authority_retained_picker_forensics_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --expected-runtime-tab-id 1949460340 `
  --timeout 20 `
  --reconcile-close-after-forensics
```

If the expected tab or lease changed, the close fails closed. There is no automatic retry.

## Local regression command

```powershell
python -m pytest `
  tests/test_browser_authority_retained_picker_forensics_pr8_8.py `
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

## Decision boundary after the report

The next selector repair should use observed evidence only.

Examples:

```text
Instant found in DOM as role=menuitemradio
  -> target that exact semantic structure

Instant absent in DOM but present in AX with backendDOMNodeId
  -> resolve/click via AX-backed DOM node

picker_surface_open = false
  -> retained exception closed the picker; build a separate zero-write
     open-picker topology probe before attempting another selection
```

No additional real product write should be attempted until this topology is understood.
