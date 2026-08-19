# PR8.8 — High-Level Product-Runtime Browser Authority Live Integration Gate

_Status: runner and isolated regression harness implemented; real two-write Windows/Chrome execution pending_

_Date: 2026-08-17_

_Base high-level plumbing commit: `db62af7bfa44a7f3a1ce6996d57a6246bf9cea1f`_

## Goal

This gate proves the PR8.8 Browser Authority policy plumbing through the public `ChatGPTProductRuntime` surface rather than re-testing the lower lease implementation directly.

The intended live path is:

```text
ChatGPTProductRuntime.send_text_observed(
    browser_authority_policy="TURN_SCOPED",
    browser_authority_ttl_ms=0,
)
        ↓
BrowserOwnedProductTransport
        ↓
BrowserOwnedProductWriteRuntime
        ↓
Browser Authority Lease release
        ↓
runtime tab disappears
        ↓
ChatGPTProductRuntime.send_text_observed(... same conversation ...)
        ↓
no per-turn Browser Authority override
        ↓
default PERSISTENT policy
        ↓
new runtime tab created
        ↓
canonical finality proven
```

The gate therefore tests the high-level policy surface, default preservation, same-conversation continuity, and browser-authority recreation in one bounded experiment.

## Write budget

The happy path performs exactly two real ordinary ChatGPT product writes.

```text
write budget          = 2
automatic write retry = false
```

The runner requires:

```text
--acknowledge-live-writes
```

If phase 1 is ambiguous, canonical finality is not proven, or runtime-tab CLOSE cannot be confirmed, phase 2 is not attempted.

## Phase 0 — high-level preflight

Before any write the runner checks two independent surfaces.

Extension/runtime support:

```text
characterization support      = true
runtime-tab release support   = true
```

Public product-runtime governance:

```text
browser_authority_policy_high_level_surface = true
browser_authority_selected_transport_policy_support = true
browser_authority_effective_runtime_default_policy = PERSISTENT
browser_authority_effective_runtime_default_ttl_ms = null
browser_authority_policy_contract_scope = RESOURCE_LIFECYCLE_ONLY
canonical_readback_required = true
automatic_write_retry = false
temporary_mode_production_enabled = false
```

Any failure here is a zero-write failure.

## Phase 1 — high-level TURN_SCOPED override

The first product mutation is made only through:

```python
ChatGPTProductRuntime.send_text_observed(...)
```

with:

```text
conversation_mode = normal
browser_authority_policy = TURN_SCOPED
browser_authority_ttl_ms = 0
```

The returned high-level execution must prove:

```text
ProductExecutionProvenance present
completion.completed = true
completion.canonical_completion_proven = true
requested conversation mode = NORMAL
observed conversation mode = NORMAL
observed mode proven = true
```

The transport observation must independently show:

```text
write event observed = true
Browser Authority release proven = true
browser_authority_policy = TURN_SCOPED
browser_authority_ttl_ms = 0
browser_authority_disposal_action = CLOSE
lease id present
runtime tab id present
```

The gate does not inspect `runtime._writer`, does not call `lifecycle_snapshot()`, and does not trigger `release_runtime_tab()` itself.

## Phase 1b — observe CLOSE externally

After the successful high-level return, the runner polls only the provider status surface.

CLOSE is considered externally confirmed only when:

```text
bridge available = true
extension connected = true
runtime_tab_id = null
```

A missing bridge is not treated as evidence that CLOSE succeeded.

If absence is not confirmed within the bounded wait window, the second product write is not attempted.

## Phase 2 — default PERSISTENT continuation

The second mutation again uses only:

```python
ChatGPTProductRuntime.send_text_observed(...)
```

against the conversation id returned by phase 1.

Crucially, this call supplies **no** Browser Authority policy/TTL override.

That makes the second turn a direct live check that the high-level compatibility default remains:

```text
PERSISTENT
```

The returned observation must show:

```text
browser_authority_policy = PERSISTENT
browser_authority_ttl_ms = null
browser_authority_disposal_action = KEEP
runtime_tab_created_for_turn = true
new runtime tab id != phase-1 runtime tab id
```

The returned provenance must again prove canonical normal-mode completion.

The conversation id must remain identical across both turns.

Finally, provider status must show the recreated runtime tab still present, which verifies that phase 2 really used the preserved PERSISTENT default rather than another disposal policy.

## What this gate does not prove

This is deliberately not another full PR8.8 resource characterization.

It does not re-measure:

```text
idle CPU proxy
idle JS heap
IDLE_TTL behavior
lease-duration distributions
cold/warm latency distributions
foreground-disturbance distributions
```

Those belong to the earlier five-write characterization and later independent replication/default-policy review.

This gate also does not alter or validate Temporary production enablement. The retained invariant is:

```text
Browser Authority recreation != Temporary Lifecycle recreation
```

## Command

After pulling the gate commit, keep Chrome running and logged in.

No extension reload is required because this slice changes only Python/tests/docs.

Run:

```powershell
python -m chatgpt_web_adapter.product_runtime_browser_authority_live_gate `
  --acknowledge-live-writes `
  --timeout 150
```

Optional existing ordinary durable conversation:

```powershell
python -m chatgpt_web_adapter.product_runtime_browser_authority_live_gate `
  --conversation <conversation-id> `
  --acknowledge-live-writes `
  --timeout 150
```

For the cleanest gate, omit `--conversation`; phase 1 will create a new ordinary durable test conversation and phase 2 will continue it.

## Success criteria

A successful report must contain:

```text
ok = true
write_budget = 2
write_attempts = 2
write_completions = 2
automatic_write_retry = false
failure_phase = null
failure = null
```

and summary gates:

```text
high_level_turn_scoped_override_observed = true
turn_scoped_close_confirmed = true
canonical_finality_preserved_for_turn_scoped_send = true
same_conversation_continued_after_close = true
browser_authority_recreated_for_next_high_level_turn = true
default_persistent_policy_preserved = true
canonical_finality_preserved_for_post_close_turn = true
final_persistent_runtime_tab_retained = true
runtime_tab_id_changed_after_close = true
write_budget_respected = true
automatic_write_retry_attempted = false
```

A single pass closes the missing empirical proof for high-level plumbing. It still does not justify changing the library default away from `PERSISTENT`.
