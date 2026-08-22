# Browser-Owned v1 and Standalone SDK Contract

_Status: PR9.0 architecture freeze_

_Date: 2026-08-22_

## Purpose

PR9.0 closes the browser-owned text generation as the mature production baseline of `chatgpt-web-adapter` (CWA) and freezes the application-facing contract that later transports must preserve.

CWA remains a standalone SDK / CLI / local ChatGPT product bridge. CMA, HDE, terminal users and other applications are consumers of this contract; no downstream project owns it.

This freeze is additive. It does not rewrite the released CWA 0.2 `ChatGPTProductRuntime` method surface and it does not begin the experimental browserless write work planned for PR9.1.

## Contract schema

The standalone runtime contract is machine-readable and versioned:

```python
from chatgpt_web_adapter import (
    PRODUCT_RUNTIME_CONTRACT_SCHEMA,
    assemble_product_runtime,
    product_runtime_contract,
)

runtime = assemble_product_runtime()
contract = product_runtime_contract(runtime)

assert PRODUCT_RUNTIME_CONTRACT_SCHEMA == 1
print(contract.to_dict())
```

Schema `1` freezes the upper product-runtime boundary rather than the internal browser implementation.

The stable runtime operations are:

```text
health / readiness
capabilities
send / send_text / send_text_observed
get_status / get_messages / attach_conversation
end_temporary_chat / temporary_lifecycle_snapshot
governance
```

The separate `product_runtime_contract(runtime)` inspector is intentionally additive. PR9.0 does not require adding another method to the already-released `ChatGPTProductRuntime` class.

The inspector verifies that every schema-1 operation is actually callable before returning a conforming contract. It does not manufacture an operation list for a partial runtime-like object.

## Stable interface split

```text
application
    |
    v
ChatGPTProductRuntime
    |
    +-- CanonicalConversationClient
    |      attach / messages / status / readback
    |
    `-- ProductWriteTransport
           explicit product mutation transport
```

Application callers depend on these product-level interfaces. They do not depend on Chrome tab ids, extension workers, Native Messaging implementation details, debugger target ids, Sentinel internals or concrete writer classes.

`ProductWriteTransport` remains deliberately minimal so existing transport implementations do not need to accept arbitrary future keyword arguments merely to satisfy the base protocol. Concrete transports may expose additional capability-gated keyword options consumed by `ChatGPTProductRuntime`; those concrete signatures remain implementation details.

Applications should request product intent through `ChatGPTProductRuntime`, not by depending on concrete transport keyword names. New product-level intents may extend the runtime and transport implementation together without exposing browser mechanics above this boundary.

## Capability state and transport support tier are independent

PR9.0 freezes two separate axes.

### Capability state

One feature on one transport is declared as exactly one of:

```text
AVAILABLE
UNSUPPORTED
UNKNOWN
UNIMPLEMENTED
```

### Transport support tier

One concrete transport is declared as:

```text
PRODUCTION
EXPERIMENTAL
```

These values must never be combined into synthetic states such as `AVAILABLE-experimental`.

Example:

```text
browser-owned:
    transport support tier = PRODUCTION
    text_turns state        = AVAILABLE

future browserless transport:
    transport support tier = EXPERIMENTAL
    text_turns state        = AVAILABLE   # possible after evidence exists
```

`AVAILABLE` answers whether a capability is implemented and evidence-backed on that transport. `EXPERIMENTAL` answers what stability/support promise applies to the transport itself.

Transport support tier and runtime-contract schema are derived CWA metadata. Callers and transport implementations cannot self-promote a transport by supplying constructor metadata. Unknown future transport identities default conservatively to `EXPERIMENTAL` until explicitly graduated.

## Browser-owned v1 production baseline

The built-in `browser-owned` transport is the PR9.0 production baseline.

Its proven text-era product surface includes:

- ordinary text turns;
- new chat;
- continuation;
- canonical durable read/status/attach/readback where applicable;
- revision-safe streaming and final-only observation;
- Temporary Chat text turns with session-local lifecycle authority;
- product model/reasoning profile selection for the proven profile set;
- Browser Authority lifecycle policy;
- explicit finality/reconciliation governance;
- no automatic retry after an ambiguous write;
- no hidden direct-write fallback.

Images, general files, multimodal continuation, web search, tools/connectors and other rich product surfaces are not promoted by PR9.0. They remain capability work for later PR9 milestones.

## Frozen safety and correctness invariants

Schema 1 requires the runtime contract to preserve:

```text
transport identity agrees across runtime, governance and capabilities
product semantics = ordinary-chatgpt
canonical interface = CanonicalConversationClient
write interface = ProductWriteTransport
automatic_write_retry = false
fallback_transport = explicitly none
legacy_direct_write_fallback = false
ambiguous_write_requires_reconciliation = true
incremental_observation_is_canonical_finality = false
runtime caller does not depend on concrete browser implementation
```

The browser-owned production transport now declares `incremental_observation_is_canonical_finality=False` explicitly. The contract inspector requires that exact evidence; missing or contradictory finality governance fails closed.

The inspector also rejects a missing fallback declaration, interface drift, transport-identity disagreement, support-tier disagreement, and an incomplete stable operation surface instead of filling those gaps with expected values.

Ordinary ChatGPT product semantics remain first-class. A transport must not silently substitute a different API/product surface while claiming equivalence.

## Browser-owned internals are not the SDK contract

Historical module names such as `*_pr8_*` may remain internally while they still contain tested production implementation. PR9.0 does not mass-rename or rewrite those modules merely to remove historical names.

The architecture freeze is defined by the public contract, support-tier/capability metadata, conformance tests and observable behavior—not by internal filenames.

Internal cleanup is justified when it materially improves correctness, maintainability or performance without widening risk.

## PR9.1 boundary

PR9.1 may add an experimental direct-request browserless transport behind the same upper contract:

```text
                 ChatGPTProductRuntime
                         |
          +--------------+--------------+
          |                             |
          v                             v
BrowserOwnedProductTransport   BrowserlessRequestTransport
PRODUCTION                     EXPERIMENTAL
```

Browserless work must not require CMA, HDE or ordinary SDK callers to redesign their orchestration around private web protocol details.

A browserless capability may become `AVAILABLE` while the transport remains `EXPERIMENTAL`. Site-protocol drift is therefore represented honestly rather than hidden inside capability state.

A PR9.1 transport must satisfy the same schema-1 fail-closed invariants rather than inheriting browser-owned production status or browser implementation assumptions.

## Acceptance gate

PR9.0 is complete when:

- schema-1 runtime contract metadata is public and deterministic;
- browser-owned is explicitly machine-readable as `PRODUCTION`;
- capability state and transport support tier are orthogonal;
- the transport/canonical boundary remains minimal and suitable for alternative implementations;
- stable operations and interface identities are validated rather than merely reported;
- existing CWA 0.2 runtime behavior remains compatible;
- contract violations and missing evidence fail closed;
- the full regression/release CI remains green;
- no downstream-specific CMA/HDE orchestration enters the CWA SDK boundary.
