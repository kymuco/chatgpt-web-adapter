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
| ChatGPT (direct HTTP) | Text, streaming, Temporary Chat send, Markdown and PNG, continuation | Experimental / Windows live 2026-10-23 | `BrowserlessHTTPClient` opt-in | Stream and model request are not canonical finality/model attestation |
| ChatGPT (shared canonical client) | Conversation export and governed generated-file handoff | Shared client operation, bounded live evidence | `cwa export` / `handoff_generated_artifact(...)` | Requires exact product identity and destination integrity checks |
| DeepSeek Web | text new chat + continuation | Experimental | `DeepSeekWebRuntime` module-only | `PAGE_DOM_STABLE_COMPLETION`, noncanonical |
| Gemini Web | text new chat + continuation | Experimental | `GeminiWebRuntime` module-only | `PAGE_DOM_STABLE_COMPLETION`, noncanonical |
| Qwen Web | text new chat, continuation, network SSE and `--chat` reattachment (Windows live-verified) | Experimental / **isolated Qwen extension** | `QwenClient(transport="browser")` | Network stream verified on observed turns; canonical finality unproven |
| Qwen Web (direct HTTP) | One authenticated generation; renewal/repeatability unverified | Experimental / limited proof | `QwenClient(transport="http")` | Canonical finality unproven |
| Google Translate Web | text translation | Experimental | `GoogleTranslateWebCapability` module-only | `PAGE_DOM_STABLE_TRANSLATION`, noncanonical |
| Gemini Notebook Web | add web URL source | Experimental | `GeminiNotebookWebCapability` module-only | `PAGE_DOM_DURABLE_SOURCE_ADMISSION`, noncanonical |
| Gemini Notebook Web | generate + observe Audio Overview | Experimental | `GeminiNotebookWebCapability` module-only | background acceptance, then `PAGE_DOM_DURABLE_BACKGROUND_ARTIFACT_COMPLETION` after reload verification; noncanonical |

## Three capability families currently proven

### Conversational product runtimes

```text
local application
-> provider-specific chat runtime
-> hosted conversational product
```

The current chat family includes ChatGPT, DeepSeek Web, Gemini Web and isolated
experimental Qwen Web (see [Qwen SDK guide](qwen.md)).

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

Gemini Notebook adds a second non-chat class:

```text
local application
-> CWA lower browser bridge / authority lane
-> existing owned Gemini Notebook
-> durable URL-source admission
```

Its result is persistent hosted workspace state, not a chat turn and not a stateless
transform. Finality is proven from one new stable product-owned source-row reference
in the same notebook. Checkbox selection state is explicitly not admission identity.

PR16.5 adds a third non-chat lifecycle:

```text
existing owned notebook
-> default Audio Overview generation commit
-> durable pending background artifact
-> re-enterable read-only observation
-> stable non-pending artifact
-> ordinary reload
-> same exact observed artifact ref
```

Generation returns after durable background acceptance rather than holding one browser
turn open until media completion. `observe_audio_overview(...)` is the read-only
re-entry surface; it reports pending without navigation and proves completed finality
only after the same exact product-observed artifact ref survives one ordinary reload.

One proof is not enough to justify a generic `HostedCapabilityRuntime`, public
capability factory, or universal operation schema. Translate, durable source admission,
and background artifact generation now provide three qualitatively different non-chat
proofs, but CWA still keeps their product-specific contracts explicit until repeated
primitives are understood well enough to justify a shared runtime.

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

Those are research directions, not current capability claims.

See [ROADMAP.md](../ROADMAP.md).
