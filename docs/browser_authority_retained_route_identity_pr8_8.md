# PR8.8 — Retained Runtime-Tab Route Identity Forensics, Conversation-Mismatch Characterization and Zero-Write Evidence Preservation

## Status

Follow-up to the retained failed-picker forensic slice.

Live evidence after extension reload proved:

```text
canonical_status = completed
runtime_tab_id = 1949460340
lease_id_present = true
```

but the existing surface-forensics probe failed before debugger attach with:

```text
PR8_8_RETAINED_PICKER_FORENSICS_CONVERSATION_MISMATCH
```

That means Browser Authority resource identity survived while the retained tab's current ChatGPT product route no longer matched the expected durable conversation.

This slice characterizes that state instead of treating it as an opaque failure.

## Architectural rule

```text
Browser Authority runtime-tab identity
!=
current ChatGPT product-conversation route identity
```

A retained tab can remain a valid ChatGPT Browser Authority resource while no longer being on the expected `/c/<conversation_id>` route.

Therefore route identity must be observed before DOM/Accessibility picker evidence is interpreted.

## Additive layering

The previously published retained-picker forensic worker is not rewritten.

```text
service_worker_observability.js
  -> service_worker_phase_timing_pr8_8.js
  -> service_worker_instant_mode_pr8_8.js
  -> service_worker_instant_selection_repair_pr8_8.js
  -> service_worker_retained_picker_forensics_pr8_8.js
  -> service_worker_retained_route_identity_pr8_8.js
```

The new layer wraps only two new characterization RPCs:

```text
characterizeRetainedRouteIdentitySupport
characterizeRetainedRouteIdentity
```

All ordinary writes and all prior forensic RPCs delegate unchanged.

## Route-only probe

The route probe performs:

```text
stored runtime-tab lookup
chrome.tabs.get(runtime_tab_id)
ChatGPT-origin validation
safe route classification
second chrome.tabs.get(runtime_tab_id)
route-stability comparison
stored lease metadata read
```

It deliberately does **not** perform:

```text
chrome.debugger.attach
Runtime.evaluate
Accessibility.getFullAXTree
Input.dispatchMouseEvent
Input.insertText
submitOfficialPageTurn
chrome.tabs.update
chrome.tabs.remove
```

So route mismatch evidence is preserved without navigation, reload, DOM inspection, picker interaction, close, or product write.

## Safe route identity

The worker classifies the current route into:

```text
ROOT
CONVERSATION
OTHER_CHATGPT
```

It exports only:

```text
route_kind
observed_conversation_id = <id> | null
expected_conversation_id
conversation_matches_expected
route_identity_status
```

Statuses:

```text
EXPECTED_CONVERSATION_MATCH
OTHER_CONVERSATION
ROOT_ROUTE
OTHER_CHATGPT_ROUTE
```

Privacy boundary is explicit:

```text
raw_url_exported = false
query_exported = false
fragment_exported = false
```

No raw URL, arbitrary path string, query, hash, cookies, DOM text, prompt text, response text, or auth material is returned.

## Why conversation_write_count is null

This route-only probe intentionally does not attach the debugger and therefore does not install the network conversation-write observer.

The truthful report is:

```text
zero_product_writes = true
conversation_write_guard_observed = false
conversation_write_count = null
```

`zero_product_writes=true` means this characterization path itself has no product-write operation. It does not falsely claim that unrelated external activity was observed and counted.

## Route mismatch behavior

If:

```text
conversation_matches_expected = false
```

then the runner returns a successful forensic characterization:

```text
ok = true
surface_forensics_performed = false
route_mismatch_characterized = true
retained_tab_left_untouched = true
```

The old DOM/Accessibility surface-forensics runner is **not called**.

This prevents picker topology from another/root ChatGPT route being misrepresented as evidence for the expected durable conversation.

## Exact-match behavior

Only when:

```text
route_kind = CONVERSATION
observed_conversation_id == expected_conversation_id
conversation_matches_expected = true
```

may the new runner delegate to the existing retained-picker surface-forensics runner.

That old runner then preserves its already-published contract:

```text
bounded DOM topology
bounded Accessibility topology
conversation-write network guard
no picker mutation
no product write
```

The route layer does not duplicate or replace that logic.

## Reconciliation-close governance

On route mismatch, even explicit:

```text
--reconcile-close-after-forensics
```

fails closed with:

```text
PR8_8_ROUTE_MISMATCH_CLOSE_FORBIDDEN
```

The evidence-bearing retained tab and lease remain intact.

On an exact expected-conversation match, the flag delegates to the existing surface-forensics runner, which may use the already-proven exact tab + stored lease fenced `release_runtime_tab` operation.

No automatic retry is introduced.

## Support preflight

After extension Reload:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_retained_route_identity_pr8_8 import RetainedRouteIdentityProvider; import json; p=RetainedRouteIdentityProvider(); print(json.dumps(p.retained_route_identity_support(), indent=2))"
```

Required:

```text
retained_route_identity_supported = true
retained_route_identity_schema_version = 1
retained_existing_tab_route_probe_supported = true
conversation_mismatch_characterization_supported = true
route_mismatch_dom_ax_suppression_supported = true
raw_route_redaction_supported = true
exact_match_surface_forensics_delegation_supported = true
zero_product_writes = true
```

## Current retained specimen command

Do not manually navigate or close tab `1949460340` before the probe.

```powershell
python -m chatgpt_web_adapter.browser_authority_retained_route_identity_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --expected-runtime-tab-id 1949460340 `
  --timeout 10
```

There is no live-write acknowledgment flag because product-write budget is zero.

For the currently observed state, an informative result is expected to contain one of:

```text
route_identity_summary.route_kind = ROOT

or

route_identity_summary.route_kind = CONVERSATION
route_identity_summary.observed_conversation_id != expected conversation

or

route_identity_summary.route_kind = OTHER_CHATGPT
```

with:

```text
route_identity_summary.conversation_matches_expected = false
route_identity_summary.route_mismatch_characterized = true
surface_forensics_performed = false
write_attempts = 0
write_completions = 0
```

If instead the route has returned to the exact expected conversation, the same command automatically delegates to the existing DOM/AX surface-forensics path.

## Local regression

```powershell
python -m pytest `
  tests/test_browser_authority_retained_route_identity_pr8_8.py `
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

## Decision boundary

If the retained tab is `ROOT` or `OTHER_CHATGPT`, the next investigation is **route drift/recovery semantics**, not picker-option selection.

If it is another `CONVERSATION`, the next investigation is **cross-conversation route drift**.

Only if it is the exact expected conversation should the earlier question resume:

```text
what DOM/AX structure represents Instant in the open picker?
```

No further real product write should be attempted until the retained route identity is understood.
