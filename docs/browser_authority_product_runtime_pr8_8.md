# PR8.8 — High-Level Browser Authority Policy Plumbing, Runtime Default Preservation and Product-Runtime Lease Governance

_Status: implementation slice complete; local regression verification and independent live replication required before any default-policy promotion_

_Date: 2026-08-17_

_Base: PR8.8 live characterization + test-harness repair `fa329ed34beb166d9f24ac85399fdad3fc0e1f71`_

## 1. Goal

This PR8.8 slice lifts the already-implemented Browser Authority resource-lifetime policy from `BrowserOwnedProductWriteRuntime` through the production product-runtime assembly path without moving browser mechanics into the generic `ProductWriteTransport` contract.

The resulting path is:

```text
ChatGPTProductRuntime
        ↓
BrowserOwnedProductTransport
        ↓
BrowserOwnedProductWriteRuntime
        ↓
Browser Authority Lease
```

The central lifecycle invariant remains unchanged:

```text
Browser Authority Lease != Turn Lifecycle
```

This slice is plumbing and governance only. It does not change the lower lease state machine, the canonical-finality contract, the write retry policy, Temporary Chat production status, or extension/native-host behavior.

## 2. Live evidence that permits the plumbing

The first real Windows/Chrome PR8.8 characterization completed successfully on 2026-08-17:

```text
write budget            = 5
write attempts          = 5
write completions       = 5
automatic write retry   = false
failure                 = none
```

The same ordinary durable conversation survived all five turns.

Observed policy gates:

```text
PERSISTENT initial cold start     PASS
PERSISTENT warm reuse             PASS
TURN_SCOPED ttl=0 CLOSE           PASS
canonical finality after CLOSE    PASS
next turn after CLOSE recreation  PASS
IDLE_TTL ttl=5000 CLOSE           PASS
```

The `TURN_SCOPED ttl=0` turn released browser authority, closed runtime tab `1949460203`, and still reached canonical `FINALIZED`. The next turn created runtime tab `1949460207` and continued the same conversation.

Observed canonical-finality lag after Browser Authority release ranged from about 4.3 s to 6.7 s. This is direct evidence that browser authority lifetime and logical turn finality are separate clocks.

The idle resource sample observed approximately 1.47% main-thread task-time fraction over 5.012 s, about 100.9 MB maximum JS heap used, no debugger left attached, and no activation caused by the resource sample itself.

These measurements are evidence for one machine/browser/runtime window only. They are not a basis for changing the compatibility default.

## 3. Compatibility default remains PERSISTENT

The production/library transport default remains:

```text
PERSISTENT
```

No caller that omits Browser Authority policy parameters receives new disposal behavior.

The high-level precedence is the already-proven lower-runtime precedence:

```text
per-turn explicit override
    ↓
runtime assembly default
    ↓
transport default PERSISTENT
```

This slice deliberately preserves the previous generic call shape when no Browser Authority override is requested. Generic `ProductWriteTransport` implementations are not required to accept browser-specific keyword arguments.

## 4. Runtime-default configuration

The production assembler now accepts optional Browser Authority defaults:

```python
runtime = assemble_product_runtime(
    browser_authority_policy="IDLE_TTL",
    browser_authority_ttl_ms=5000,
)

runtime.send("hello")
```

The same defaults may be supplied when `ChatGPTProductRuntime` owns construction of the selected production transport.

The browser-owned transport passes the configured defaults into `BrowserOwnedProductWriteRuntime`, where the existing resolver validates policy/TTL combinations and preserves the lower-runtime precedence rules.

A configured runtime TTL is retained as configuration even when the current effective runtime policy is still the transport default. This preserves the lower resolver's independent policy/TTL precedence semantics.

## 5. Per-turn override

A caller may override resource lifetime for one normal production turn:

```python
runtime.send(
    "hello",
    browser_authority_policy="TURN_SCOPED",
    browser_authority_ttl_ms=0,
)
```

or:

```python
runtime.send_text_observed(
    "hello",
    browser_authority_policy="IDLE_TTL",
    browser_authority_ttl_ms=5000,
)
```

The high-level runtime forwards these arguments only when the selected transport explicitly advertises:

```text
browser_authority_product_runtime_policy_supported = true
```

If a selected/injected transport does not advertise support, an explicit Browser Authority override fails before transport dispatch. The request is never silently ignored.

If no override is requested, no Browser Authority kwargs are added to the generic transport call.

## 6. Injected transport ownership

An explicitly injected `write_transport` owns its own assembly-time configuration.

Therefore this is rejected:

```python
ChatGPTProductRuntime(
    client,
    write_transport=custom_transport,
    browser_authority_policy="IDLE_TTL",
    browser_authority_ttl_ms=5000,
)
```

with a fail-closed configuration error before any product write.

The same rule applies to `assemble_product_runtime(...)` when a caller supplies both `write_transport=` and Browser Authority runtime defaults.

This avoids pretending that an implementation-independent runtime can mutate hidden construction state inside an injected transport.

## 7. Generic ProductWriteTransport remains implementation-independent

`ProductWriteTransport` is intentionally not widened with mandatory Browser Authority parameters.

Browser Authority policy is optional transport-specific resource-lifecycle control. A future non-browser transport must not be forced to synthesize concepts such as runtime tabs, extension leases, or Native Messaging simply to satisfy the generic product-write interface.

Accordingly:

```text
ProductWriteTransport
    does not require browser policy kwargs

ChatGPTProductRuntime
    exposes optional policy intent

selected transport governance
    proves whether that intent is supported
```

## 8. Product-runtime governance boundary

The high-level policy contract is explicitly scoped to:

```text
RESOURCE_LIFECYCLE_ONLY
```

Selecting `PERSISTENT`, `IDLE_TTL`, or `TURN_SCOPED` does not itself change:

```text
conversation identity
conversation mode
canonical finality semantics
write retry semantics
Temporary lifecycle authority
```

In particular:

```text
Browser Authority recreation != Temporary Lifecycle recreation
```

The PR8.7 Temporary production boundary remains unchanged:

```text
conversation_mode="temporary" = disabled
fail closed before product write
no fallback to durable semantics
```

Temporary-mode denial is resolved before Browser Authority override dispatch.

## 9. HDE-facing opacity

A caller choosing resource lifetime does not need to provide or understand:

```text
Chrome tab ids
Browser Authority lease ids
Native Messaging operations
extension implementation details
CDP/debugger mechanics
```

The product-runtime surface expresses policy intent, not browser mechanism.

Governance therefore states that Browser Authority policy does not expose browser mechanics and does not require runtime-tab identity or Native Messaging details from the caller.

## 10. Regression gates

This slice adds focused tests for:

```text
runtime-default assembly forwarding
default assembly call-shape preservation
assemble_product_runtime forwarding
injected-transport default rejection
per-turn TURN_SCOPED forwarding
send alias IDLE_TTL forwarding
observed-send forwarding
unsupported-transport fail-closed behavior
no-override generic protocol compatibility
Temporary-mode denial precedence
product-runtime opacity governance
browser-owned transport lower-runtime forwarding
PERSISTENT compatibility default preservation
```

The existing lower PR8.8 tests remain authoritative for lease issuance, release proof, disposal fencing, TTL scheduling, ambiguity handling, and canonical finality.

## 11. What this slice does not promote

This slice does **not** change the default away from `PERSISTENT`.

Before any default-policy change, PR8.8 still needs independent live replication across multiple cold/warm/CLOSE cycles and review of the distributions of:

```text
warm reuse turn cost
post-CLOSE recreation turn cost
idle retained resource cost
foreground disturbance
Browser Authority lease duration
canonical finality lag
```

A target HDE assembly may eventually choose an explicit `IDLE_TTL` without changing the library compatibility default, but that is a later evidence-based decision.
