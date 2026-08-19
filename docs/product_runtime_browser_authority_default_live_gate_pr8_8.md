# PR8.8 — High-Level Runtime-Default IDLE_TTL Live Integration, Per-Turn Override Precedence and Default-Restoration Governance

_Status: runner + isolated harness implemented; one bounded real Windows/Chrome execution required_

_Date: 2026-08-17_

_Base high-level plumbing/live gate: `4f106358a272841ab2c3f956922458022aae4db2`_

## Goal

This PR8.8 slice proves the remaining high-level policy-precedence contract through the public `ChatGPTProductRuntime` surface.

The configuration under test is:

```text
runtime default:
    browser_authority_policy = IDLE_TTL
    browser_authority_ttl_ms = 5000
```

The live sequence is intentionally only three writes:

```text
1. no per-turn override
   -> runtime-default IDLE_TTL 5000
   -> CLOSE

2. explicit per-turn PERSISTENT
   -> PER_TURN wins over RUNTIME_DEFAULT
   -> KEEP beyond the configured runtime TTL

3. no per-turn override
   -> runtime-default IDLE_TTL 5000 is restored
   -> reuse retained tab
   -> CLOSE
```

The claim being tested is:

```text
PER_TURN > RUNTIME_DEFAULT > TRANSPORT_DEFAULT
```

and, more specifically:

```text
a per-turn override does not mutate the configured runtime default
```

## Public-surface boundary

Product mutation is performed only through:

```text
ChatGPTProductRuntime.send_text_observed()
```

The gate does **not** call:

```text
runtime._writer
lifecycle_snapshot()
release_runtime_tab()
BrowserOwnedProductWriteRuntime
```

Runtime-tab presence/absence is observed through the existing read-only provider status surface.

This keeps the experiment focused on the high-level product-runtime plumbing rather than re-testing lower lease internals directly.

## Runtime assembly under test

The CLI assembles:

```python
runtime = assemble_product_runtime(
    client=client,
    provider=provider,
    browser_authority_policy="IDLE_TTL",
    browser_authority_ttl_ms=5000,
)
```

Before any write, governance must prove:

```text
browser_authority_effective_runtime_default_policy = IDLE_TTL
browser_authority_effective_runtime_default_ttl_ms = 5000
browser_authority_runtime_default_policy_source = RUNTIME_DEFAULT

browser_authority_policy_high_level_surface = true
browser_authority_selected_transport_policy_support = true
browser_authority_policy_contract_scope = RESOURCE_LIFECYCLE_ONLY

canonical_readback_required = true
automatic_write_retry = false
temporary_mode_production_enabled = false
```

If these are not true, the runner stops with zero writes.

## Turn 1 — runtime-default IDLE_TTL

The first write intentionally supplies no per-turn Browser Authority arguments.

Expected observation:

```text
browser_authority_policy = IDLE_TTL
browser_authority_ttl_ms = 5000
browser_authority_disposal_action = CLOSE
browser_authority_release_proven = true
canonical completion proven = true
```

The runner also requires:

```text
disposal_due_at - released_at = 5000
```

This proves the effective policy came from the configured runtime default and that its TTL remains anchored to Browser Authority release.

Before turn 2, external provider status must confirm:

```text
runtime_tab_id = null
```

If CLOSE is not confirmed, the runner stops and does not perform the override write.

## Turn 2 — explicit per-turn PERSISTENT

The second high-level call supplies only:

```python
browser_authority_policy="PERSISTENT"
```

It deliberately does not change the runtime assembly.

Expected observation:

```text
browser_authority_policy = PERSISTENT
browser_authority_ttl_ms = null
browser_authority_disposal_action = KEEP
runtime_tab_created_for_turn = true
canonical completion proven = true
```

Because turn 1 proved the previous runtime tab absent, turn 2 must recreate browser authority.

### Strong precedence proof

Seeing `PERSISTENT` in the write event is necessary but not sufficient.

The gate therefore waits:

```text
configured runtime TTL + retention margin
```

Default:

```text
5000 ms + 1000 ms
```

Throughout that interval the same runtime-tab ID must remain present.

This rules out a hidden runtime-default disposal timer surviving the per-turn override.

Only then does the gate claim:

```text
PER_TURN PERSISTENT > RUNTIME_DEFAULT IDLE_TTL
```

## Turn 3 — runtime-default restoration

The third write again supplies **no** per-turn Browser Authority arguments.

Because turn 2 kept the runtime tab, expected observation is:

```text
browser_authority_policy = IDLE_TTL
browser_authority_ttl_ms = 5000
browser_authority_disposal_action = CLOSE

runtime_tab_id = turn-2 runtime_tab_id
runtime_tab_preexisting = true
runtime_tab_created_for_turn = false

canonical completion proven = true
```

This proves both:

```text
the PERSISTENT override was turn-local
```

and:

```text
the configured IDLE_TTL runtime default was restored automatically
```

The final disposal must again be confirmed by external provider status:

```text
runtime_tab_id = null
```

## Conversation and semantic invariants

All three turns must remain in the same ordinary durable conversation.

Every observed execution must prove:

```text
requested conversation mode = NORMAL
observed conversation mode = NORMAL
observed mode proven = true
canonical completion proven = true
product semantics = ordinary-chatgpt
```

The Browser Authority policy remains resource-lifecycle control only.

This slice does not enable or recreate Temporary Chat lifecycle authority.

## Safety and write budget

Happy path:

```text
write_budget = 3
write_attempts = 3
write_completions = 3
automatic_write_retry = false
```

There is no runner-level product-write retry.

Failure stops all later phases.

In particular:

```text
initial IDLE_TTL CLOSE not proven
    -> stop after write 1

PERSISTENT retention not proven
    -> stop after write 2

restored IDLE_TTL observation/finality fails
    -> no retry of write 3
```

Any failure after a product write must be reviewed before a manual rerun.

## Expected successful summary

```text
runtime_default_idle_ttl_observed_on_initial_send = true
initial_idle_ttl_close_confirmed = true

per_turn_persistent_override_observed = true
per_turn_override_precedence_proven = true
persistent_override_retained_beyond_runtime_ttl = true

runtime_default_restored_after_override = true
restored_default_reused_retained_runtime_tab = true
restored_idle_ttl_close_confirmed = true

same_conversation_continued_across_all_three_turns = true
canonical_finality_preserved_across_all_three_turns = true
temporary_mode_boundary_preserved = true

write_budget_respected = true
automatic_write_retry_attempted = false
```

## Local regression command

```powershell
python -m pytest `
  tests/test_product_runtime_browser_authority_default_live_gate_pr8_8.py `
  tests/test_product_runtime_browser_authority_live_gate_pr8_8.py `
  tests/test_product_runtime_browser_authority_pr8_8.py `
  tests/test_product_runtime.py `
  tests/test_product_transport_protocol.py `
  -q
```

## Live command

No extension/native-host files are changed by this slice, so no extension reload is required.

```powershell
python -m chatgpt_web_adapter.product_runtime_browser_authority_default_live_gate `
  --acknowledge-live-writes `
  --idle-ttl-ms 5000 `
  --timeout 150
```

Do not manually close or manipulate the runtime tab during the run.

## Promotion boundary

Even a successful result does not change the library compatibility default:

```text
transport default = PERSISTENT
```

The experiment proves high-level runtime-default configuration and precedence semantics only.

A future HDE assembly may explicitly choose `IDLE_TTL`; that is separate from changing the library transport default.

After this gate passes, the remaining PR8.8 evidence should move to independent replicated warm/recreation/resource characterization rather than adding more policy semantics.
