# CWA Capability Map

This document is a discovery map for humans and agents.

It is **not** a runtime authority registry. A static documentation entry does not grant
write permission, retry permission, canonical finality, or provider support to a
particular runtime instance.

## Current proven surfaces

| Product | Capability | Support | Public surface | Finality |
| --- | --- | --- | --- | --- |
| ChatGPT | text new chat + continuation | Production/default | `ChatGPTProductRuntime` | Canonical readback where required |
| ChatGPT | image/file input + multimodal continuation | Production on proven browser-owned paths | `ChatGPTProductRuntime` | Canonical readback where required |
| ChatGPT | structured search/tool/source/citation observations | Production on proven paths | runtime observations | Observation is not downstream authority |
| DeepSeek Web | text new chat + continuation | Experimental | `DeepSeekWebRuntime` module-only | `PAGE_DOM_STABLE_COMPLETION`, noncanonical |
| Gemini Web | text new chat + continuation | Experimental | `GeminiWebRuntime` module-only | `PAGE_DOM_STABLE_COMPLETION`, noncanonical |
| Google Translate Web | text translation | Experimental | `GoogleTranslateWebCapability` module-only | `PAGE_DOM_STABLE_TRANSLATION`, noncanonical |

## Two capability families currently proven

### Conversational product runtimes

```text
local application
-> provider-specific chat runtime
-> hosted conversational product
```

The current chat family includes ChatGPT, DeepSeek Web, and Gemini Web.

`ProductProviderBoundary schema 2` is a metadata/invariant view over those runtimes.
It is not a request router.

### Non-chat hosted capability

```text
local application
-> CWA lower browser bridge / authority lane
-> Google Translate Web
-> bounded translation result
```

Google Translate is the first proof that useful CWA infrastructure exists below the
conversation-shaped runtime.

One proof is not enough to justify a generic `HostedCapabilityRuntime`, public
capability factory, or universal operation schema.

## Support vocabulary

CWA keeps these ideas separate:

```text
support tier
capability state
transport
finality
provenance
write authority
retry authority
```

A product being visible in this document does not imply that every surface is
production-ready.

## How callers should discover support

For a concrete production ChatGPT runtime, prefer runtime-owned capability and health
inspection:

```python
capabilities = runtime.capabilities()
health = runtime.health()
```

For module-only experimental products, use the exact documented module contract and
keep product-specific failure/finality semantics visible.

Do not infer support from:

- provider/product name alone;
- a visible UI control;
- DOM position;
- an older historical engineering record;
- this static documentation without the matching runtime contract.

## Planned evidence, not promised support

Future non-chat experiments may explore additional classes such as:

- grounded research workspaces;
- OCR / visual extraction;
- hosted media transformation;
- long-running generated artifacts.

Those are research directions, not current capability claims.

See [ROADMAP.md](../ROADMAP.md).
