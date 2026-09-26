# PR15.52 — Freeze the provider-neutral runtime boundary

## Purpose

PR15.51 completes the ChatGPT ownership/cleanup pass. The next step is not to add
DeepSeek directly to ChatGPT-specific assembly. First freeze the smallest contract
that a materially different provider must satisfy.

The audit found three layers that must stay distinct:

```text
provider-neutral runtime boundary
!= provider product semantics
!= provider transport / wire mechanics
```

## Audit result

The existing `ProductWriteTransport` and `CanonicalConversationClient` protocols are
already mostly implementation-neutral.

The frozen schema-1 `ProductRuntimeContract` is intentionally not neutral:

- it requires `ordinary-chatgpt` product semantics;
- it serializes `ChatGPTProductRuntime` as the runtime identity;
- the public runtime exposes ChatGPT-specific Temporary, browser-authority,
  model-profile, rich-input, submission, UI-liveness and artifact surfaces.

Those contracts remain valid for provider #1 and are not generalized in this slice.

## New boundary

PR15.52 adds:

```text
ProductProviderBoundary
product_provider_boundary(runtime)
```

The boundary validates only concepts expected to survive a second provider:

```text
provider identity
product semantics identity
transport identity
CanonicalConversationClient
ProductWriteTransport
ProductCapabilities
ProductExecutionProvenance
automatic_write_retry = false
fallback_transport = none
ambiguous write requires reconciliation
incremental observation != canonical finality
```

It deliberately does not know:

- ChatGPT request/response payload shapes;
- browser-owned or browserless transport ids;
- Temporary Chat;
- Browser Authority;
- model-profile names;
- rich-input attachment mechanics;
- DeepSeek transport ids or wire shapes.

## ChatGPT as provider #1

`ChatGPTProductRuntime` now explicitly declares:

```text
provider_id = "chatgpt"
```

and exports that identity through runtime governance.

Existing ChatGPT transport and capability semantics remain:

```text
provider_id       = chatgpt
product_semantics = ordinary-chatgpt
```

No existing runtime method, transport id, capability state, finality rule or public
compatibility behavior changes.

## Neutrality proof

A synthetic second-provider fixture uses:

```text
provider_id       = deepseek
product_semantics = ordinary-deepseek
transport         = deepseek-web
```

and passes the same `product_provider_boundary(...)` validator.

This is intentionally a contract proof only. It does not claim DeepSeek product
support and performs no network or browser work.

The boundary implementation itself contains no DeepSeek-specific branch and no
ChatGPT product-semantics constant.

## Why not create ProductRuntime yet

A generic runtime class before provider #2 would force decisions about concepts that
may not survive the comparison:

- Temporary lifecycle;
- Browser Authority;
- split submit/await lifecycle;
- model-profile mapping;
- rich input;
- canonical snapshot/artifact handoff.

Those stay on `ChatGPTProductRuntime` until real DeepSeek evidence shows which
semantics are shared.

## Next proof

The next bounded slice should implement the smallest DeepSeek provider capable of:

```text
text new chat
+ text continuation
+ explicit provider identity/semantics
+ no automatic retry
+ explicit finality/reconciliation evidence
```

No images, files, tools/connectors, account pooling, model-profile abstraction or
generic provider registry should be added until this two-provider proof is green.

Tracking: #107


## PR15.53 provider #2 follow-up

PR15.53 exercises this boundary with an experimental `DeepSeekWebRuntime`.
The second provider keeps ChatGPT-specific Temporary/Browser Authority/rich-input
surfaces out of shared core and uses only the frozen identity/semantics,
capabilities/provenance, no-retry/no-fallback and reconciliation invariants.
