# PR8.8 — Independent Browser Authority Policy Replication

## Scope

This slice moves PR8.8 from one-off correctness gates to repeated live characterization.
It does **not** change production policy defaults, extension/native-host behavior, canonical
finality semantics, Temporary semantics, or retry policy.

The experiment is intentionally narrow:

```text
closed runtime-tab state
  -> default PERSISTENT cold creation
  -> default PERSISTENT warm reuse
  -> read-only retained-tab resource sample
  -> per-turn TURN_SCOPED ttl=0 close
  -> confirmed/stable closed window
  -> repeat
```

The default run performs three independent cycles. Each completed cycle performs exactly
three real ChatGPT product writes, so the default write budget is nine.

## Why this experiment exists

Earlier PR8.8 work already proved:

- Browser Authority Lease is separate from Turn Lifecycle;
- release may occur at `WRITE_COMPLETED` before canonical finality;
- `TURN_SCOPED ttl=0` can close browser authority without breaking canonical readback;
- a durable conversation can continue after runtime-tab recreation;
- high-level `ChatGPTProductRuntime` policy plumbing works;
- `PER_TURN > RUNTIME_DEFAULT > TRANSPORT_DEFAULT` works live;
- a per-turn override does not mutate the configured runtime default.

Those are correctness claims. They are not yet distributional evidence about the cost of
retaining browser authority versus recreating it.

This slice therefore asks a different question:

> Across repeated controlled cycles on the same durable conversation, what does warm
> PERSISTENT reuse cost relative to cold PERSISTENT recreation, and what observable
> foreground/resource behavior accompanies retained browser authority?

## Controlled baseline

The runner uses `assemble_product_runtime(client=..., provider=...)` with **no Browser
Authority runtime-default override**. Governance must therefore report:

```text
browser_authority_effective_runtime_default_policy = PERSISTENT
browser_authority_effective_runtime_default_ttl_ms = null
browser_authority_runtime_default_policy_source = TRANSPORT_DEFAULT
```

The runner also requires the initial runtime tab to be absent. If a runtime tab is already
present, preflight fails before any product write. This prevents the first "cold" sample
from being silently contaminated by a warm starting state.

A stale/retained lease token alone is not treated as live browser authority; the controlled
baseline is defined by runtime-tab absence.

## One replication cycle

For cycle `N`:

### 1. Cold PERSISTENT creation

The runner calls public:

```python
ChatGPTProductRuntime.send_text_observed(...)
```

without Browser Authority policy kwargs.

Required observation:

```text
policy                  PERSISTENT
ttl                     null
disposal                KEEP
runtime_tab_preexisting false
runtime_tab_created     true
canonical finality      proven
```

### 2. Warm PERSISTENT reuse

A second public high-level send is made on the same durable conversation, again with no
Browser Authority policy kwargs.

Required observation:

```text
policy                  PERSISTENT
ttl                     null
disposal                KEEP
runtime_tab_preexisting true
runtime_tab_created     false
runtime_tab_id           same as cold turn
canonical finality      proven
```

Cold and warm measurements therefore use the same policy and same conversation semantics.
The intended controlled difference is whether a runtime tab already exists.

### 3. Retained-resource sample

The already-characterized read-only provider surface samples the retained runtime tab.
The default sample window is 3000 ms.

Recorded fields include:

- task-duration delta and task-time fraction;
- JS heap used/total;
- document count;
- node count;
- JS event-listener count;
- whether the tab was active before/after;
- whether the sample itself activated the tab;
- foreground-disturbance evidence;
- debugger-attached state.

The sample is a measurement operation and must not itself activate the runtime tab or leak
a debugger attachment. Either condition fails the cycle before another write is attempted.

### 4. TURN_SCOPED close

A third public high-level send uses:

```text
browser_authority_policy = TURN_SCOPED
browser_authority_ttl_ms = 0
```

It must reuse the same runtime tab, prove release, and report:

```text
disposal_action = CLOSE
disposal_due_at = released_at
```

### 5. Closed-state proof

The runner first waits until provider status confirms no runtime tab. It then observes a
stable closed window (default 1000 ms) and requires every status sample to remain:

```text
bridge available
extension connected
runtime_tab_id = null
```

Only then may the next cold cycle begin.

## Cost characterization

For every cycle the runner records a paired cold/warm comparison:

- total high-level turn time;
- Browser Authority lease duration;
- post-release-to-high-level-return duration;
- cold minus warm total time;
- cold/warm total-time ratio.

Aggregate count/min/max/mean/median statistics are emitted across cycles.

`post_release_canonical_return_ms` is deliberately named as a high-level return metric. It
uses the public release timestamp and runner return time; it is **not** presented as the
internal exact `FINALIZED - WRITE_COMPLETED` lifecycle lag.

No latency threshold participates in PASS/FAIL. In particular, the runner does not assume
that every cold turn must be slower than every warm turn. Product/model/network variation
can dominate single-turn timings.

## Foreground governance

Foreground activation is characterized separately for:

- cold PERSISTENT turns;
- warm PERSISTENT turns;
- TURN_SCOPED close turns;
- all writes together.

The report contains true/false/unknown counts and an activation rate among known samples.
Foreground activation during a product write is observational, not a failure condition,
because earlier PR8.8 live runs already showed that it is environment/state dependent.

By contrast, the **resource sampler itself** must not activate the tab.

## Resource governance

Across retained-resource samples the report aggregates:

- task-time fraction;
- maximum used JS heap;
- document count;
- node count;
- event-listener count;
- sample foreground-disturbance count;
- debugger-leak count.

Closed windows prove absence of the PR8.8 runtime tab only. They do not claim that total
Chrome process resource consumption becomes zero.

## Fencing replication

Across all completed writes the runner also requires:

- non-empty unique lease IDs;
- strictly increasing Browser Authority generations.

This gives repeated evidence that successive cold/warm/close cycles do not accidentally
reuse stale lease identity.

## Safety contract

The runner has no automatic product-write retry.

If any send fails after delegation, the run stops immediately. The report preserves:

- write attempts;
- write completions;
- partial cycle evidence;
- failure phase;
- `write_may_have_been_submitted` when available;
- `reconciliation_required` when available;
- `automatic_retry_allowed` when available;
- `automatic_retry_attempted = false`.

A failed or ambiguous live run must not be blindly rerun.

The replication count is bounded to 2..5. The default is 3, yielding:

```text
write_budget = 9
```

## What this slice does not decide

This experiment does not automatically change the library default.

Even if warm reuse is consistently faster, policy selection still needs to balance:

- latency/recreation cost;
- retained resource cost;
- foreground disturbance;
- product/runtime reliability;
- HDE-specific lifecycle expectations.

Until the replicated evidence is reviewed:

```text
library default = PERSISTENT
```

remains unchanged.

A later HDE assembly may explicitly choose `IDLE_TTL` without changing the generic library
default if that tradeoff is supported by evidence.

## Files

```text
src/chatgpt_web_adapter/browser_authority_policy_replication_pr8_8.py
tests/test_browser_authority_policy_replication_pr8_8.py
docs/browser_authority_policy_replication_pr8_8.md
```

No extension/native-host file is modified by this slice.

## Deterministic regression gate

```powershell
python -m pytest `
  tests/test_browser_authority_policy_replication_pr8_8.py `
  tests/test_product_runtime_browser_authority_default_live_gate_pr8_8.py `
  tests/test_product_runtime_browser_authority_live_gate_pr8_8.py `
  tests/test_product_runtime_browser_authority_pr8_8.py `
  tests/test_browser_authority_live_characterization.py `
  -q
```

## Live command

After the deterministic gate is green and the preflight runtime-tab state is closed:

```powershell
python -m chatgpt_web_adapter.browser_authority_policy_replication_pr8_8 `
  --acknowledge-live-writes `
  --replications 3 `
  --resource-sample-ms 3000 `
  --closed-stability-ms 1000 `
  --timeout 150
```

Expected happy-path write accounting:

```text
replications_requested = 3
write_budget            = 9
write_attempts          = 9
write_completions       = 9
automatic_write_retry   = false
```

The live result is intentionally pending until run on the user's local Chrome/product
session. The measured distribution must be recorded before any default-policy promotion is
considered.
