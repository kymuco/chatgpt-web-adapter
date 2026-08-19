# PR8.8 — In-Failure Open-Picker Popup-Subtree Capture, Mode-Label-to-Actionable-Ancestor Mapping, Candidate-Cap Dealiasing and Evidence-Persistence Governance

## Motivation

The fresh Instant failure reproduction proved the exact target route and isolated the failure before prompt insertion or submit:

```text
failure = OPTION_NOT_FOUND / instant_option_missing
selected_mode_before_selection = HIGH
instant_option_candidate_count = 0
conversation_write_count_during_selection = 0
```

The retained surface probe then showed an open mode-bearing popup with three known-mode descendants, while the exported global DOM and AX candidate arrays both hit their hard cap of 80. The global DOM summary therefore could not distinguish “Instant is absent” from “the relevant mode-bearing descendants are outside the first 80 exported candidates”.

This slice removes that ambiguity without broadening the selector.

## In-failure capture

A new additive worker is loaded after `service_worker_instant_failure_forensics_pr8_8.js`.

```text
existing Instant selector fails
→ prior failure worker persists pre-input failure record
→ new outer failure wrapper runs while picker + selection context still exist
→ reuse already-attached debugger
→ capture mode-bearing popup subtree only
→ persist bounded topology under the same Browser Authority lease
→ rethrow the exact original error object
```

There is no new product mutation, retry, navigation, tab creation/close, debugger attach, prompt insertion, submit, response-body read, cookie access, or raw DOM/text export.

## Popup-local traversal

The capture enumerates visible popup surfaces with roles:

```text
menu
listbox
radiogroup
dialog
group
```

Only surfaces containing recognized mode-bearing descendants are candidates. Role priority prefers a real `menu/listbox/radiogroup` over a generic group. The selected surface is traversed independently of the old global candidate arrays.

For each minimal mode-bearing label, the record contains only normalized evidence:

```text
mode
mode evidence source: OWN_TEXT / ARIA_LABEL / TITLE / TEST_ID / SUBTREE_TEXT
tag / role / rect
nearest actionable ancestor found?
ancestor hop count
actionable tag / role
aria checked / selected / expanded / haspopup
data-state / disabled / pointer-events
```

No raw label text is exported.

For every actionable descendant in the selected popup, the record also preserves:

```text
direct_modes
subtree_modes
mode_bearing_descendant_modes
mode_bearing_descendant_count
```

This directly tests the suspected geometry:

```text
mode label descendant
        ↓
non-actionable wrapper(s)
        ↓
nearest menuitem/button/option/radio ancestor
```

## Candidate-cap dealiasing

The old global probe may scan more than 1,000 visible page elements but exports at most 80 normalized DOM candidates and 80 AX candidates.

This slice does not raise those global caps. Instead it records totals for one selected popup subtree and exports bounded normalized evidence:

```text
candidate_surface_count                  total
popup_subtree_visible_element_count      total
mode_label_count                         total
mode_labels                              max 16
mode_labels_truncated                    explicit

actionable_descendant_count              total
actionable_descendants                    max 32
actionable_descendants_truncated          explicit

candidate_cap_dealiased = true
global_candidate_cap_used = false
```

Thus the existence and mode identity of popup-local labels no longer depends on their position in a page-global candidate list.

## Persistence and fencing

The new evidence is stored with the same private Browser Authority lease ID as the existing failure record. It is not exposed through a new unfenced API.

The existing RPC remains the only lookup:

```text
characterizeInstantFailureForensicsRecord(expectedBrowserAuthorityLeaseId)
```

The outer worker augments that response with `popupSubtree` only when the stored popup record matches the exact requested lease. The lease token itself remains redacted.

Support is exposed by augmenting the existing failure-forensics support response:

```text
popupSubtreeCaptureSupported
popupLocalTraversalSupported
modeLabelActionableAncestorMappingSupported
candidateCapDealiasingSupported
popupEvidencePersistenceSupported
rawPopupTextRedactionSupported
```

The production Python preflight requires all six capabilities. Older unit-test doubles that predate this slice may omit the keys; the real provider never omits them, so an old extension still fails closed before a live write.

## Target live evidence

For a reproduced `instant_option_missing`, the single-write runner should now include:

```text
in_failure_popup_subtree.capture_status = POPUP_SUBTREE_CAPTURED
in_failure_popup_subtree.route_kind = CONVERSATION
in_failure_popup_subtree.observed_conversation_id = exact target
in_failure_popup_subtree.candidate_cap_dealiased = true
in_failure_popup_subtree.global_candidate_cap_used = false
```

The decisive fields are:

```text
in_failure_popup_subtree.recognized_modes
in_failure_popup_subtree.mode_labels
in_failure_popup_subtree.actionable_descendants
summary.popup_instant_mode_label_present
```

If `INSTANT` is present as a popup-local label and maps to a nearby actionable ancestor, the next PR may repair the selector from direct evidence. If `INSTANT` remains absent even in this popup-local traversal, the correct next question is product-menu hierarchy/state rather than selector broadening.

## Live gate governance

The previously retained tab was manually closed, so first reconcile the resulting orphan Browser Authority lease and prove:

```text
runtime_tab_id = null
lease_id_present = false
```

After extension Reload, run the existing single-write fresh failure runner once. Do not blind-retry after `write_attempts = 1`.
