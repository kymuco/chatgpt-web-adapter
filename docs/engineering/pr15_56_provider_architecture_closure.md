# PR15.56 — Provider architecture closure and freeze

## Purpose

PR15.56 closes the provider-architecture phase of PR15 after the boundary has been
tested by three real product semantics:

```text
ChatGPT
→ canonical conversation readback
→ ordinary-chatgpt
→ production browser-owned transport

DeepSeek Web
→ page-owned noncanonical completion evidence
→ ordinary-deepseek
→ experimental deepseek-web transport

Gemini Web
→ page-owned noncanonical completion evidence
→ ordinary-gemini
→ experimental gemini-web transport
```

This slice adds no fourth provider, no new product feature, no live probe and no
generic provider factory.

Its job is to:

1. remove remaining cross-provider safety asymmetry;
2. freeze the provider-neutral contract that survived real product evidence;
3. state which provider-specific surfaces deliberately remain experimental;
4. define reopen conditions instead of continuing abstraction work indefinitely.

## Closure finding — DeepSeek ambiguity parity

PR15.55 review hardened Gemini so that uncertainty after delegation or the page-owned
submit can never look like a normal retryable failure.

The closure audit found that DeepSeek still retained the older PR15.53 behavior:

```text
page submit may have happened
→ later observation / route / storage failure
→ ordinary error possible
```

and:

```text
Native Messaging request delegated
→ response lost
→ ordinary RequestError possible
```

That violated the provider-neutral safety invariant even though both providers declared:

```text
automatic_write_retry = false
ambiguous_write_requires_reconciliation = true
```

PR15.56 aligns DeepSeek with Gemini:

```text
before delegation / before submit uncertainty
→ ordinary failure where appropriate

after delegation / once click-capable submit evaluation is dispatched
→ reconciliation required when execution outcome is uncertain
→ automatic retry forbidden
```

The successful DeepSeek write path is unchanged.

The audit also tightened the exact submit commit boundary for both DeepSeek and Gemini.
The page click is executed inside a CDP `Runtime.evaluate` command. If that command
fails with a non-navigation-detach error, CWA cannot prove whether `control.click()`
ran before the result was lost. That uncertainty is now classified as ambiguous inside
the submit helper itself. Known pre-click failures such as composer write failure or a
submit control that never becomes ready remain ordinary failures. The already-proven
navigation-detach path still proceeds to observation-only debugger reattachment and
never replays the write.

## Frozen provider-neutral contract

The surviving stable boundary is:

```text
PRODUCT_PROVIDER_BOUNDARY_SCHEMA = 2

provider_id
product_semantics
transport

canonical_readback_required
canonical_interface

write_transport_interface = ProductWriteTransport
capability_model = ProductCapabilities
provenance_model = ProductExecutionProvenance

automatic_write_retry = false
fallback_transport = none
ambiguous_write_requires_reconciliation = true
incremental_observation_is_canonical_finality = false
```

The important result is not that all providers behave the same. They do not.

The frozen contract instead makes the differences explicit:

```text
ChatGPT
  canonical_readback_required = true
  canonical_interface = CanonicalConversationClient

DeepSeek / Gemini
  canonical_readback_required = false
  canonical_interface = none
```

No provider wire shape, DOM selector, route schema or HTTP request format is part of
this shared contract.

## Stable public surface

The following provider-neutral symbols remain `PRIMARY_PRODUCTION` root-package
surface:

```text
PRODUCT_PROVIDER_BOUNDARY_SCHEMA
ProductProviderBoundary
product_provider_boundary

ProductCapabilities
ProductExecutionProvenance
ProductWriteTransport
```

This is the supported architecture boundary for downstream consumers.

PR15.56 does not promote concrete page adapters into the root API.

## Provider-specific runtimes remain module-only

These remain implementation modules rather than stable root-package contracts:

```text
chatgpt_web_adapter.deepseek_web
  DeepSeekBrowserTurnProvider
  DeepSeekWebTransport
  DeepSeekWebRuntime
  DeepSeekWebWriteOutcomeAmbiguousError

chatgpt_web_adapter.gemini_web
  GeminiBrowserTurnProvider
  GeminiWebTransport
  GeminiWebRuntime
  GeminiWebWriteOutcomeAmbiguousError
```

Both transports remain `EXPERIMENTAL`.

This is deliberate. Real live acceptance proves that the implementations work on the
observed product revision; it does not justify promising that their current DOM,
navigation or page-finality mechanics are durable public API.

## Compatibility that remains intentionally ChatGPT-shaped

Two historical public compatibility facts are not removed in this closure:

1. `CHATGPT_PRODUCT_PROVIDER_ID` and `ORDINARY_CHATGPT_PRODUCT_SEMANTICS` remain
   public because ChatGPT is the released provider #1 surface.
2. `ProductCapabilities.from_entries(...)` retains its historical
   `ordinary-chatgpt` default.

PR15.54 already proved the safety boundary around that default:

```text
non-ChatGPT provider forgets explicit product semantics
→ capability/runtime semantics mismatch
→ provider boundary rejects
```

DeepSeek and Gemini both pass product semantics explicitly. PR15.56 freezes that rule
instead of creating a compatibility-breaking cleanup.

## Private provider dispatch remains private

The extension's `productProviderTurnHandlers` registry remains internal composition
machinery.

It is not promoted into:

- a public provider registry;
- a plugin discovery API;
- a generic provider factory;
- a caller-controlled routing table.

Provider selection outside the extension is therefore not generalized merely because
three providers have now been proven.

## What PR15 proved

PR15 began as an ownership reset of a layered ChatGPT runtime. It now ends with a
provider boundary tested against materially different products.

The evidence chain is:

```text
historical layered ChatGPT runtime
→ explicit ownership consolidation
→ zero reachable rebinding closure
→ provider-neutral boundary v1
→ DeepSeek falsifies mandatory canonical readback
→ schema 2
→ neutrality audit removes silent ChatGPT provenance default
→ Gemini passes schema 2 unchanged
→ closure audit aligns post-write ambiguity semantics
→ provider architecture frozen
```

No additional provider is required merely to increase the sample count.

## Reopen conditions

Provider-architecture abstraction work should reopen only if one of these becomes true:

1. a real fourth provider cannot fit schema 2 without lying about semantics;
2. a real downstream consumer needs a stable public way to select/construct
   provider-specific runtimes;
3. a provider proves a new canonical interface shape not expressible by the current
   conditional canonical-readback field;
4. a production promotion of DeepSeek/Gemini requires a stronger support contract;
5. a concrete safety failure shows that the shared retry/reconciliation model is
   insufficient.

Otherwise, new work should be consumer-driven provider hardening rather than another
architecture layer.

## Non-goals after closure

Do not add, solely for architectural completeness:

- provider #4;
- a generic `ProductRuntime` superclass;
- a public provider registry;
- a generic provider factory;
- shared DOM selectors;
- shared route parsers;
- shared page-finality heuristics;
- automatic fallback between providers;
- automatic replay of ambiguous writes.

## Closure condition

PR15.56 closes successfully when:

```text
DeepSeek ambiguity semantics == Gemini ambiguity semantics
schema 2 unchanged
neutral boundary contains no DeepSeek/Gemini special cases
provider-specific web runtimes remain module-only
page-owned transports remain EXPERIMENTAL
no live/probe harness is added
full deterministic CI is green
```
