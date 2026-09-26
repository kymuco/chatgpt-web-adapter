# Providers

_Last updated: 2026-09-26_

This document describes the provider-specific support surface on current `main`.

CWA does not assume that every provider exposes the same concepts. Provider capability
state and runtime support tier are evidence-backed independently.

## Shared provider contract

A provider runtime is inspected through:

```python
from chatgpt_web_adapter import product_provider_boundary

boundary = product_provider_boundary(runtime)
```

`ProductProviderBoundary` is metadata/validation over an existing runtime, not a
request router.

Schema 2 currently freezes:

```text
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

## Support matrix

| Surface | ChatGPT | DeepSeek Web | Gemini Web |
| --- | --- | --- | --- |
| Provider id | `chatgpt` | `deepseek` | `gemini` |
| Product semantics | `ordinary-chatgpt` | `ordinary-deepseek` | `ordinary-gemini` |
| Transport | `browser-owned` (default) | `deepseek-web` | `gemini-web` |
| Support tier | **PRODUCTION** | **EXPERIMENTAL** | **EXPERIMENTAL** |
| Text turns | AVAILABLE | AVAILABLE | AVAILABLE |
| New chat | AVAILABLE | AVAILABLE | AVAILABLE |
| Continuation | AVAILABLE | AVAILABLE | AVAILABLE |
| Canonical readback | AVAILABLE / required | UNIMPLEMENTED | UNIMPLEMENTED |
| Conversation attach/read/status | AVAILABLE | UNIMPLEMENTED | UNIMPLEMENTED |
| Streaming | AVAILABLE on proven paths | UNIMPLEMENTED | UNIMPLEMENTED |
| Images/files | AVAILABLE on proven paths | UNIMPLEMENTED | UNIMPLEMENTED |
| Web search | AVAILABLE observation on proven path | UNKNOWN | UNKNOWN |
| Temporary chat | AVAILABLE text path | UNIMPLEMENTED | UNIMPLEMENTED |
| Model selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Reasoning selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Tools/connectors | Conservative / UNKNOWN overall | UNIMPLEMENTED | UNIMPLEMENTED |
| Multimodal continuation | AVAILABLE on proven path | UNIMPLEMENTED | UNIMPLEMENTED |

The table describes current `main`, not necessarily the latest published wheel.

## ChatGPT

ChatGPT is the mature/default provider.

Application boundary:

```text
ChatGPTProductRuntime
```

The default mutation transport is:

```text
browser-owned = PRODUCTION
```

The alternative direct-request transport is:

```text
browserless-request = EXPERIMENTAL
```

ChatGPT also has a canonical conversation/session plane. Successful turns can therefore
use canonical readback as completion authority where the runtime contract requires it.

The mature ChatGPT surface includes evidence-backed rich input, model profiles,
Temporary Chat, streaming/finality handling and structured product observations.

## DeepSeek Web

Module:

```python
from chatgpt_web_adapter.deepseek_web import DeepSeekWebRuntime
```

Current proof:

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
```

Conversation identity uses a local opaque id mapped to the exact observed page route.

Completion evidence:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

This is intentionally weaker than ChatGPT canonical readback and is never relabeled as
canonical finality.

## Gemini Web

Module:

```python
from chatgpt_web_adapter.gemini_web import GeminiWebRuntime
```

Current proof:

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
```

Conversation identity uses the same architectural model as DeepSeek: a local opaque id
bound to an exact observed product route, without hardcoding the provider's internal
conversation-id schema.

Completion evidence:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

## Finality is provider-specific

The shared architecture does not require all providers to have the same finality plane.

```text
ChatGPT
→ canonical readback can prove durable completion

DeepSeek / Gemini
→ current proof observes stable page completion
→ canonical completion remains unproven
```

This distinction is intentional.

## Write uncertainty

All page-owned providers preserve:

```text
automatic_write_retry = false
fallback_transport = none
```

For DeepSeek/Gemini, once the click-capable submit evaluation may have executed,
uncertainty becomes reconciliation-required.

A caller must not interpret an ambiguous outcome as permission to replay the turn.

## Why provider-specific runtimes are module-only

DeepSeek/Gemini live acceptance proves that the current implementations work against
the observed product revisions.

It does **not** prove that:

- current DOM selectors are durable API;
- route behavior will never change;
- page finality can be upgraded to canonical finality;
- all visible features should be implemented;
- the provider is ready for root-package production support.

Therefore concrete runtimes remain module-only and experimental while the
provider-neutral boundary remains the stable public contract.

## Adding or promoting a provider

Do not add a provider only to increase provider count.

A new provider should be justified by a real consumer or by evidence that tests the
existing architecture.

Promotion requires stronger evidence than “a live turn worked once”. At minimum,
review:

- repeatable product behavior;
- capability scope;
- finality semantics;
- conversation identity;
- ambiguous-write behavior;
- support burden under product drift;
- deterministic regression coverage;
- whether public construction/selection is actually needed.

See [architecture.md](architecture.md) and
[engineering/pr15_56_provider_architecture_closure.md](engineering/pr15_56_provider_architecture_closure.md).
