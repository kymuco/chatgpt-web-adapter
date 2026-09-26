# PR16.2 — Google Translate non-chat capability spike

## Status

Experimental falsification spike.

This slice does **not** redefine CWA's stable public architecture and does not promote
Google Translate into `ProductProviderBoundary schema 2`.

Its purpose is to test whether CWA's useful abstraction is broader than conversational
AI products:

```text
local program
→ bounded browser-owned capability execution
→ hosted product result
```

## Why translation first

Text translation is intentionally simpler than OCR.

It has:

```text
structured text input
+ source language
+ target language
→ bounded text result
```

and does not require:

- conversation identity;
- continuation;
- message identity;
- chat history;
- canonical conversation readback;
- rich media upload.

That makes it a clean falsification test for chat-shaped architecture.

## Initial architecture finding

The PR15 provider boundary survived three materially different chat products, but the
current runtime contract is still explicitly conversation-shaped:

```text
ProductWriteTransport
→ send_text(...)
→ ConversationInput
→ ChatResponse

ProductExecutionProvenance
→ conversation_id
→ message_id

ProductCapabilities
→ text_turns
→ new_chat
→ continuation
```

Therefore Google Translate must **not** be forced into the existing chat provider
contract merely to make the architecture look universal.

PR16.2 keeps it beside that contract.

## Spike contract

Python module:

```text
chatgpt_web_adapter.google_translate_web
```

Experimental surface:

```python
GoogleTranslateWebCapability.translate_text(
    text,
    source_language=...,
    target_language=...,
)
```

Native Messaging request:

```text
type = translate_text
productId = google-translate-web
text
sourceLanguage
targetLanguage
timeoutMs
```

Result:

```text
translatedText
sourceLanguage
targetLanguage
finalUrl
finalityEvidence = PAGE_DOM_STABLE_TRANSLATION
canonicalCompletionProven = false
automaticRetry = false
```

There is deliberately no:

- `providerId`;
- `conversationId`;
- `ChatResponse`;
- `ProductWriteTransport`;
- `ProductProviderBoundary`;
- generic capability registry.

## Reused shared infrastructure

The spike reuses only the lower-level pieces that are already genuinely product-
agnostic:

```text
local loopback bridge
Native Messaging
extension connection
single browser authority lane
background product tab
CDP Runtime.evaluate
bounded result observation
no silent fallback
post-execution ambiguity discipline
```

This is the main architectural question under test.

## Browser execution

The worker opens/reuses a background tab on:

```text
https://translate.google.com/
```

Source/target languages are expressed through the product route. The page's own text
input is then mutated through the browser DOM.

Google Translate begins translation in response to source input. Therefore the
ambiguity boundary begins once the authoritative input mutation may have executed:

```text
known pre-input failure
→ ordinary failure

input mutation may have executed
→ hosted operation may have started
→ uncertainty requires reconciliation
→ automatic retry forbidden
```

No private Google Translate HTTP endpoint is called by CWA.

## Current DOM hypotheses

The spike intentionally keeps selector knowledge provider-local.

Initial hypotheses:

```text
source
→ visible textarea / textbox

result
→ [jsname="W297wb"]
→ fallback [jsname="jqKxS"]
→ bounded target-language [lang] fallback
```

These are not architecture contracts.

Live acceptance is allowed to falsify them.

## Finality

Current proposed evidence:

```text
PAGE_DOM_STABLE_TRANSLATION
```

It means:

1. a non-empty result appears after the source mutation;
2. the result differs from the post-clear baseline;
3. the result remains stable for a bounded interval;
4. the page remains on the Google Translate origin.

It does **not** claim:

- canonical service-side persistence;
- durable job identity;
- exactly-once server execution;
- official Google API semantics.

## Temporary live gate

Acceptance-only command:

```powershell
python -m chatgpt_web_adapter.google_translate_web_live_gate
```

The gate currently asks Google Translate Web to translate:

```text
hello
en → es
```

and requires a result containing `hola`.

The executable live gate must be removed before merge after real acceptance evidence is
preserved in this record.

## What success would prove

A successful spike would prove only:

```text
CWA's browser bridge + authority + ambiguity model
can support at least one non-conversational hosted capability
without pretending it is a chat provider.
```

It would **not** yet prove that CWA needs a generic `HostedCapabilityRuntime`.

One successful non-chat product is still insufficient evidence for that abstraction.

## What failure would teach us

Useful falsification outcomes include:

- bridge operation routing is too turn-specific;
- authority semantics need operation identity rather than turn identity;
- result/finality modeling needs a non-chat base contract;
- capability discovery needs a new model;
- browser tab ownership is too ChatGPT-shaped;
- the page result cannot be observed robustly enough for a bounded contract.

Any of those is a valid scientific result.

## Non-goals

PR16.2 does not add:

- OCR;
- image translation;
- document translation;
- website translation;
- generic hosted-capability registry;
- public provider factory;
- provider fallback;
- official Google Cloud Translation API support;
- browserless Google Translate private-request support;
- HDE integration.

## Acceptance

Before merge:

```text
deterministic CI green
Google Translate text live gate PASS
no conversation/provider semantics fabricated
no private Google HTTP endpoint used
post-input ambiguity → reconciliation
automatic retry false
temporary executable live gate removed
evidence record updated
```
