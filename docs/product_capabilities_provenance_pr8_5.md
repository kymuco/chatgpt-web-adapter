# PR8.5 — Product Capability Model and Provenance-Aware Response Governance

PR8.5 builds on the PR8.4 transport/canonical interface split. It does not change the proven browser-owned write mechanism. Its purpose is to make two pieces of product-runtime state explicit and machine-readable:

1. what the selected runtime is known to support;
2. what evidence supports a successful returned execution.

## Capability state model

Capabilities are not booleans. The runtime distinguishes four states:

- `AVAILABLE` — implemented and evidence-backed on the declared runtime;
- `UNSUPPORTED` — the relevant product/transport contract is known not to provide it;
- `UNKNOWN` — the capability has not been characterized strongly enough;
- `UNIMPLEMENTED` — the concept may exist at product/transport level, but the production runtime does not currently implement it.

This distinction is intentional. In particular, `UNKNOWN` must not be treated as `False`, and `UNIMPLEMENTED` must not be presented as a claim that ordinary ChatGPT itself lacks a feature.

Each capability also declares an owner:

- `TRANSPORT` — constrained by the selected write transport/runtime implementation;
- `CANONICAL` — supplied by the canonical read/status/attach plane;
- `PRODUCT` — primarily a product-owned semantic whose behavior is not controlled by this transport.

The public model is exposed through:

```python
runtime.capabilities()
```

and returns `ProductCapabilities` with stable `ProductCapability` entries.

## Browser-owned capability baseline

The PR8.5 browser-owned declaration is deliberately conservative.

Evidence-backed `AVAILABLE` capabilities:

- `text_turns`;
- `new_chat`;
- `continuation`;
- `canonical_readback`;
- `conversation_attach`;
- `conversation_read`;
- `conversation_status`.

Current production-runtime `UNIMPLEMENTED` capabilities:

- `images`;
- `approvals`;
- `multimodal_continuation`.

These states describe the new production `ProductWriteTransport`, not the historical capabilities of legacy direct/Sentinel paths.

Capabilities that have not been independently characterized through the new production contract remain `UNKNOWN`, including streaming, files, web search, temporary chat, model/reasoning selection or preservation, product memory/personalization behavior, tools/connectors, and branching.

`UNSUPPORTED` remains a first-class state in the model, but PR8.5 does not manufacture an unsupported claim merely to exercise that enum value.

## Provenance model

`send_text_observed()` now returns a `ProductRuntimeExecution` carrying `ProductExecutionProvenance`.

The generic provenance object records:

```text
product_semantics
transport
write_plane
readback_plane
session_plane
completion
identity
transport_metadata
```

### Completion is not finish_reason

A key PR8.5 invariant is that successful product completion is separate from optional backend metadata.

For the browser-owned runtime, successful returned executions require canonical final assistant readback. Therefore the high-level completion source is:

```text
CANONICAL_READBACK
```

The runtime does **not** claim which private finality field supplied that readback signal unless a lower layer explicitly exports it.

`finish_reason` is preserved exactly as observed:

```text
finish_reason = null
finish_reason_observed = false
```

is a valid completed execution when canonical readback proved completion through another signal. PR8.5 never rewrites missing metadata to `stop`.

### Identity provenance

The provenance model preserves canonical identity fields when present:

- conversation id;
- assistant message id;
- observed model.

These are observations, not guessed replacements.

### Transport metadata

Transport-specific observations are carried in an opaque `transport_metadata` dictionary. The generic provenance contract does not require Chrome tab IDs, extension state, Native Messaging state, or any other browser-specific field.

The current browser-owned observation can still include fields such as runtime-tab reuse and foreground activation, but a future native/daemon transport is not required to synthesize them.

## Ownership

PR8.5 keeps the PR8.4 ownership split:

```text
ChatGPTProductRuntime
├─ CanonicalConversationClient
└─ ProductWriteTransport
```

The runtime owns generic capability/provenance presentation. The concrete transport owns its capability declarations and transport-specific observations.

The existing `BrowserOwnedProductWriteRuntime` still owns the already-proven safety behavior:

- write preflight;
- continuation commit-point canonical recheck;
- browser-owned delegation;
- canonical final assistant readback;
- ambiguous write classification;
- no automatic retry after ambiguous delegation.

PR8.5 does not duplicate or relocate those mechanics.

## CLI additions

`chatgpt-web-adapter runtime status` now includes a `capabilities` object.

`chatgpt-web-adapter runtime send` keeps all existing PR8.3 fields and adds a `provenance` object. Existing `runtime_observation`, `finish_reason`, `conversation_id`, `message_id`, and other compatibility fields remain present.

## Public API additions

PR8.5 exposes the following product-layer contracts from the package root:

- `CapabilityState`;
- `CapabilityOwner`;
- `ProductCapability`;
- `ProductCapabilities`;
- `CompletionSource`;
- `ProductCompletionProvenance`;
- `ProductIdentityProvenance`;
- `ProductExecutionProvenance`;
- `CanonicalConversationClient`;
- `ProductWriteTransport`;
- `ORDINARY_CHATGPT_PRODUCT_SEMANTICS`;
- `PRODUCT_CAPABILITY_NAMES`.

## Non-goals

PR8.5 does not:

- change the Chrome extension;
- change Native Messaging;
- change the browser-owned write runtime;
- add a hidden/non-tab transport;
- implement images, files, web search, approvals, tools, branching, or memory controls;
- infer ChatGPT product capabilities from general product knowledge;
- synthesize a finish reason;
- automatically retry ambiguous writes;
- add another product/provider abstraction.

## Acceptance gates

PR8.5 is complete when:

- all four capability states remain distinct and serializable;
- browser-owned capability declarations are complete for the frozen PR8.5 capability-name set;
- evidence-backed capabilities are not downgraded or inflated by guesswork;
- `ChatGPTProductRuntime.capabilities()` is transport-independent;
- successful observed executions carry structured provenance;
- nullable finish reason remains nullable;
- canonical readback is represented as completion evidence without inventing a private finality detail;
- transport-specific metadata remains optional and opaque to the generic contract;
- public exports are regression-tested;
- CLI output exposes capability/provenance additively;
- the full repository regression suite remains green.
