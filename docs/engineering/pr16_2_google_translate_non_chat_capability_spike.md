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

The worker's page-load and pre-input phases share one operation deadline. It is not
allowed to begin the authoritative input after the caller's usable response budget has
already been exhausted. Python reserves a response margin between the worker budget
and the outer bridge timeout.

## Current DOM hypotheses

The spike intentionally keeps selector knowledge provider-local.

Initial hypotheses:

```text
source
→ visible textarea / textbox

result
→ [jsname="W297wb"]
→ fallback [jsname="jqKxS"]
```

The spike deliberately has **no generic `[lang]` fallback**. If the product-specific
output selectors do not establish result identity, execution fails closed rather than
accepting arbitrary page text.

If more than one distinct output candidate is observed, PR16.2 also fails closed with
`RESULT_IDENTITY_UNRESOLVED` instead of returning the first segment and silently
truncating a translation. Multi-segment reconstruction is outside this first proof.

These selectors are not architecture contracts.

Live acceptance is allowed to falsify them.

## Finality

Current proposed evidence:

```text
PAGE_DOM_STABLE_TRANSLATION
```

It means:

1. the previous page result is proven cleared before the authoritative input;
2. exactly one bounded product-specific output candidate is established;
3. a non-empty result appears after the source mutation;
4. the result differs from the post-clear baseline;
5. the result remains stable for a bounded interval;
6. the page remains on the Google Translate origin.

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

## Preliminary live evidence

The first real Google Translate Web acceptance run passed on commit
`849b3e1761a4017572aa61a6828a8794ee62d8b3`:

```text
input:
hello
en → es

result:
Hola

capability_id                  translate_text
conversation_semantics         false
finality_evidence              PAGE_DOM_STABLE_TRANSLATION
canonical_completion_proven    false
automatic_retry                false
result                         PASS
```

That run proved the basic non-chat browser path on the real product.

A subsequent review identified three safety/identity edges and the implementation was
hardened after that live run:

- repeated identical output nodes must not bypass multi-candidate rejection;
- the final observed route must still encode the requested source/target languages;
- post-write finality must not introduce a separate `chrome.tabs.get` failure point.

Because those changes affect the accepted worker, the preliminary PASS is preserved as
evidence but **does not close final acceptance**. One live rerun is required on the
post-hardening head before the temporary gate can be removed.

## Result-identity characterization

The hardened rerun correctly failed closed with:

```text
GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:
RESULT_IDENTITY_UNRESOLVED
```

A temporary read-only characterization then inspected the already-rendered result
without submitting another translation.

Observed DOM:

```text
candidate 0
  jsname = jqKxS
  lang = es
  text = Hola
  contains = [1]

candidate 1
  jsname = W297wb
  text = Hola
  containedBy = [0]
```

Observed route:

```text
https://translate.google.com/?sl=en&tl=es&text=hello&op=translate
```

This proves that one logical translation result may be represented by nested
product-output nodes:

```text
jqKxS "Hola"      ancestor wrapper
└─ W297wb "Hola"  deepest result node
```

Therefore neither of these rules is valid:

```text
one matching DOM node = one logical result
same text = safe deduplication
```

The revised identity rule is structural:

```text
product-specific output candidates
→ remove any candidate that contains another matching candidate
→ remaining deepest candidates are logical result candidates

one deepest candidate
→ bounded result identity established

multiple deepest candidates
→ RESULT_IDENTITY_UNRESOLVED
→ fail closed
```

This collapses only containment wrappers demonstrated by the live DOM. It does not
concatenate siblings or deduplicate independent nodes merely because their text is
equal.

The temporary characterization path is diagnostic only and must be removed with the
live gate before merge.

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
