# PR8.8 — Browser Authority Lease / Turn Lifecycle / TTL-disposal foundation

_Status: foundation complete; first live characterization passed; high-level product-runtime policy plumbing implemented; independent replication/default-policy review remain open_

_Date: 2026-08-17_

_Base: PR8.7 final review `d7f9d7f570bab81c8974ac36ae8e2c5c708978c1`_

## 1. Goal

PR8.8 separates the lifetime of browser/page authority from the lifetime of a logical product turn.

The central invariant is:

```text
Browser Authority Lease
        !=
Turn Lifecycle
```

This is required by both ordinary page-owned writes and the PR8.7 Temporary Chat evidence. A browser tab, runtime-tab identifier, or conversation identifier must never be treated as authority merely because it still exists.

The foundation establishes the lease/lifecycle model, opt-in disposal policies, release fencing, and the production CLOSE primitive. Follow-on PR8.8 slices added bounded live characterization and high-level product-runtime policy plumbing while intentionally preserving the compatibility default `PERSISTENT`.

## 2. Observed separation point

The existing browser-owned writer already contains a useful architectural boundary:

```text
page-owned write
    |
    | extension finishes official page turn
    | debugger detached
    | composer ready
    v
browser_native_write_completed
    |
    | browserless canonical status/messages/readback continues
    v
browser_native_readback_completed
```

PR8.8 treats `browser_native_write_completed` as the Browser Authority Lease release point for the current ordinary writer.

The logical Turn Lifecycle does **not** finalize there:

```text
Browser Authority Lease = RELEASED
Turn Lifecycle          = WRITE_COMPLETED
logical turn terminal   = false
```

Only authoritative finality transitions the logical turn to:

```text
Turn Lifecycle = FINALIZED
```

If canonical readback times out after a proven page-owned write:

```text
Browser Authority Lease = RELEASED
Turn Lifecycle          = READBACK_INCOMPLETE
reconciliation_required = true
automatic_retry         = false
```

If delegated write outcome is ambiguous and browser-authority release was not observed:

```text
Browser Authority Lease = RELEASE_UNKNOWN
Turn Lifecycle          = AMBIGUOUS
disposal                = forbidden
automatic_retry         = false
```

## 3. Lifecycle policies

PR8.8 defines:

```text
PERSISTENT
IDLE_TTL
TURN_SCOPED
```

Compatibility/default behavior remains:

```text
transport implementation default = PERSISTENT
```

`IDLE_TTL` and `TURN_SCOPED` are explicit opt-in policies.

Policy precedence is:

```text
per-turn explicit override
    ↓
BrowserOwnedProductWriteRuntime assembly default
    ↓
transport implementation default
```

The follow-on high-level plumbing slice exposes this policy intent through `BrowserOwnedProductTransport` / `ChatGPTProductRuntime` without widening the generic `ProductWriteTransport` protocol with mandatory browser-specific parameters. See `docs/browser_authority_product_runtime_pr8_8.md`.

## 4. TTL semantics

TTL never begins at submit time.

The invariant implemented by `BrowserAuthorityLease.release()` is:

```text
disposal_due_at
    =
Browser Authority Lease released_at
    +
ttl
```

Never:

```text
submit_at + ttl
issue_at + ttl
```

Policy constraints:

```text
PERSISTENT
    ttl = none
    disposal = KEEP

IDLE_TTL
    ttl > 0
    disposal = CLOSE

TURN_SCOPED
    ttl >= 0
    disposal = CLOSE
```

`TURN_SCOPED ttl=0` is allowed and remains opt-in. The first real Windows/Chrome characterization on 2026-08-17 confirmed that immediate CLOSE after the current `browser_native_write_completed` release point preserved canonical finality and allowed the next ordinary turn to recreate browser authority successfully.

## 5. Disposal semantics

Production disposal v1 is:

```text
CLOSE
```

`DISCARD` is not implemented.

A disposal timer can be scheduled only when:

```text
lease.state == RELEASED
authority_release_proven == true
policy != PERSISTENT
disposal_due_at is known
```

No timer is scheduled for:

```text
ACTIVE
RELEASE_UNKNOWN
PERSISTENT
```

This enforces the roadmap invariant:

> no tab disposal while browser authority is still required.

## 6. Fresh Browser Authority commit check

The previous write preflight already checked bridge/extension readiness.

PR8.8 adds a second Browser Authority freshness check after canonical continuation checks and immediately before lease issuance/delegation:

```text
initial health
    ↓
canonical continuation commit check
    ↓
fresh provider.status()
    ↓
lease issue
    ↓
page-owned write
```

If the bridge or extension is lost between the advisory health check and this commit point:

```text
zero write
no lease delegation
manual repair may be safe
```

This is separate from canonical conversation status fencing.

## 7. Release fencing

PR8.8 adds a Native Messaging operation:

```text
release_runtime_tab
```

The broker serializes it through the same authority lock as `turn`, so a page-owned turn and CLOSE are never forwarded concurrently.

The extension CLOSE primitive requires two fences:

```text
expected runtime tab id
+
Browser Authority Lease id
```

A new production turn stores its new lease token **before** page-owned mutation. Therefore a stale timer from an older turn cannot close the reused runtime tab after a newer turn has claimed authority:

```text
old lease A released
timer A pending

new turn begins
lease B stored

timer A fires
    ↓
lease A != stored lease B
    ↓
BROWSER_NATIVE_AUTHORITY_LEASE_CHANGED
    ↓
NO CLOSE
```

Tab-id fencing independently prevents a stale timer from closing a newly recreated runtime tab.

## 8. Turn Lifecycle states

PR8.8 foundation defines:

```text
PREPARED
DISPATCHED
WRITE_COMPLETED
FINALIZED
READBACK_INCOMPLETE
AMBIGUOUS
```

Normal success:

```text
PREPARED
  ↓
DISPATCHED
  ↓
WRITE_COMPLETED       browser authority may now release
  ↓
FINALIZED             logical turn completes
```

Readback failure after write:

```text
WRITE_COMPLETED
  ↓
READBACK_INCOMPLETE
  ↓
explicit reconciliation required
```

Ambiguous delegated outcome:

```text
DISPATCHED
  ↓
AMBIGUOUS
```

TTL/disposal never changes retry safety and never converts an ambiguous write into a failed or retryable write.

## 9. Runtime observation

`BrowserOwnedWriteObservation` accepts bounded lease/lifecycle metadata from the write-completed event:

```text
browser_authority_lease_id
browser_authority_generation
browser_authority_policy
browser_authority_ttl_ms
browser_authority_issued_at_ms
browser_authority_released_at_ms
browser_authority_disposal_due_at_ms
browser_authority_release_proven
browser_authority_disposal_action

turn_lifecycle_id
turn_lifecycle_state_at_write
```

This is transport metadata, not product semantic authority.

The runtime also exposes a diagnostic `lifecycle_snapshot()` for characterization/testing.

## 10. Compatibility behavior

No default resource behavior changes in PR8.8:

```text
default policy = PERSISTENT
default disposal timer = none
default runtime tab reuse = unchanged
ordinary canonical finality = unchanged
automatic write retry = false
```

The active PR8.7 manifest entrypoint is intentionally preserved:

```text
service_worker_temporary_chat_route_reopen_probe.js
manifest version = 0.1.13
```

PR8.8 layers its lease-fenced CLOSE primitive into
`service_worker_runtime_tab_reconciliation.js`, which already sits below the
Temporary-specific wrappers in the active import chain. This preserves the
existing PR8.7 probe asset contract while placing generic runtime-tab authority
governance at the layer that already owns runtime-tab identity reconciliation.

The extension source changed in the earlier foundation/characterization slice even though the research manifest version was kept stable for PR8.7 compatibility, so an unpacked-extension reload was required before that live validation. The later high-level product-runtime plumbing slice changes Python/docs/tests only and does not itself require another extension reload.

## 11. Unit/regression evidence

The isolated PR8.8 harness covers:

```text
PERSISTENT compatibility default
policy precedence
IDLE_TTL > 0 validation
TURN_SCOPED ttl=0
TTL starts at authority release
release != logical finality
readback-incomplete reconciliation
ambiguous-write reconciliation
fresh authority loss before delegation
no disposal without release proof
stale-generation cancellation
lease-id fencing protocol
runtime-tab-id fencing protocol
broker turn/release serialization
manifest/worker boundary
```

The high-level plumbing follow-on adds regression gates for:

```text
runtime-default assembly forwarding
per-turn policy forwarding
injected-transport fail-closed ownership
generic ProductWriteTransport call-shape preservation
Temporary-mode denial precedence
product-runtime browser-mechanics opacity
```

## 12. First live evidence

The first bounded Windows/Chrome characterization on 2026-08-17 completed all five product writes with zero automatic write retry and no failure:

```text
PERSISTENT initial cold start     PASS
PERSISTENT warm reuse             PASS
TURN_SCOPED ttl=0 CLOSE           PASS
canonical finality after CLOSE    PASS
next turn after CLOSE recreation  PASS
IDLE_TTL ttl=5000 CLOSE           PASS
```

The runtime tab changed from `1949460203` to `1949460207` after the explicit CLOSE, while the same durable conversation continued.

Observed Browser Authority lease duration ranged from 13039 ms to 18435 ms. Canonical finality lag after release ranged from 4343 ms to 6732 ms, directly confirming that release and logical finality are distinct phases.

The bounded idle sample observed approximately 1.47% main-thread task-time fraction and about 100.9 MB maximum JS heap used over about five seconds, with no debugger left attached.

Detailed evidence is recorded in `docs/browser_authority_live_characterization_pr8_8.md`.

This single run closes the first live-safety gate but does **not** justify a default-policy change.

Current policy status remains:

```text
PERSISTENT remains default
IDLE_TTL remains opt-in
TURN_SCOPED remains opt-in
```

## 13. PR8.7 boundary retained

PR8.8 Browser Authority Lease is generic browser execution authority.

It is **not** PR8.7 Temporary lifecycle authority:

```text
Browser Authority Lease recreation
    !=
Temporary Lifecycle recreation
```

Closing/recreating an ordinary runtime tab must not reconstruct a terminated Temporary conversation lifecycle.

Likewise, a future live Temporary implementation may keep a product-specific Temporary lifecycle alive only while independently proven; generic browser authority never manufactures that proof.

The high-level policy surface is resource-lifecycle control only. It does not alter `conversation_mode`, does not create Temporary write authority, and does not treat cold/warm runtime state as Temporary lifecycle evidence.

## 14. Remaining PR8.8 work

High-level policy plumbing is now implemented while preserving `PERSISTENT` as the compatibility default.

Before any default-policy promotion, the next evidence slice should independently replicate multiple cold/warm/CLOSE cycles and compare distributions of:

```text
warm reuse cost
vs
post-CLOSE recreation cost

idle runtime-tab resource cost
vs
CLOSE/recreation cost

foreground disturbance
vs
retention policy

Browser Authority Lease duration
vs
canonical finality safety
```

A target HDE assembly may later choose an explicit `IDLE_TTL` without changing the library compatibility default. `TURN_SCOPED` should remain an explicit low-retention policy unless repeated live measurements justify its recreation cost for that call class.
