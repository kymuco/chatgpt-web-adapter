# PR17.0 — Google Translate Web non-chat hosted-capability falsification

## Purpose

PR17.0 tests a stronger hypothesis than adding another chat provider:

```text
Can CWA provide a bounded hosted product capability
without conversation semantics?
```

The first target is Google Translate Web text translation.

The scope is intentionally minimal:

```text
text
+ source language
+ target language
→ translated text
```

No image translation, document translation, website translation, speech, history,
saved phrases or official Cloud Translation API are in scope.

## Why translation first

Translation is a useful falsification case because it differs materially from chat:

- no conversation id;
- no new-chat / continuation distinction;
- no assistant message;
- no model identity requirement;
- no explicit submit button in the text flow;
- structured parameters beyond one prompt string;
- one bounded transformation result.

If CWA can only express this by pretending that a translation is a chat turn, the
current abstraction is too narrow.

## Existing core audit

The PR15 provider boundary is provider-neutral across **chat products**, but the
surrounding runtime contracts remain intentionally chat-shaped.

Examples on current main:

```text
ProductWriteTransport
→ send_text(...)
→ send_text_observed(...)

ConversationInput
→ ConversationRef / ChatConversation

ProductRuntimeExecution
→ ChatResponse

ProductIdentityProvenance
→ conversation_id
→ message_id
→ observed_model

ProductCapabilities
→ text_turns
→ new_chat
→ continuation
→ canonical_readback
→ conversation_attach
...
```

That is not a defect. Those contracts were derived from real ChatGPT / DeepSeek /
Gemini evidence.

PR17.0 must not retroactively relabel them as generic hosted-capability contracts.

## Research decision

The Google Translate spike therefore **does not** implement:

- `ProductWriteTransport`;
- `ProductCapabilities`;
- `ProductRuntimeExecution`;
- `ProductExecutionProvenance`;
- `ProductProviderBoundary schema 2`;
- `ChatResponse`;
- conversation identity.

Instead it introduces one module-only experimental surface:

```python
GoogleTranslateWebRuntime.translate(
    text,
    source_language=...,
    target_language=...,
)
```

This is deliberate falsification scaffolding, not a new stable public abstraction.

## Product semantics

Research identity:

```text
product_id        = google-translate
product_semantics = google-translate-web-text
transport         = google-translate-web
capability        = translate_text
support tier      = EXPERIMENTAL
```

The runtime exposes provider-specific health/result/governance values only.

## Browser-owned execution

The spike reuses the existing local Native Messaging + Chrome/CDP bridge.

It does **not** use:

- Google Cloud Translation API;
- undocumented Google Translate HTTP endpoints;
- fetch/XHR reproduction;
- CDP Network interception;
- challenge bypass.

Execution is page-owned:

```text
background Google Translate tab
→ requested sl/tl route
→ visible source textarea
→ one Runtime.evaluate source write + input/change dispatch
→ observe page-owned translated result
```

The official web product currently exposes text, image, document and website
translation modes. PR17.0 uses only the text mode.

## Native operation

PR17.0 adds one explicit broker operation:

```text
translate_text
```

It does not add a public generic capability bus.

The operation uses the existing exclusive browser authority lane but routes outside
the historical chat-turn Native Messaging lifecycle:

```text
translate_text
→ Google Translate capability wrapper
→ page-owned operation

turn
→ existing ChatGPT / DeepSeek / Gemini chain unchanged
```

This is intentionally product-specific until a second non-chat capability provides
evidence for a reusable operation abstraction.

## No explicit submit

Google Translate text translation reacts to source input.

That changes the mutation commit boundary.

For chat providers:

```text
composer write
→ page-owned submit click
→ result
```

For this spike:

```text
source textarea mutation
→ input/change dispatch
→ translation may begin
```

Therefore uncertainty begins inside the `Runtime.evaluate` that performs the source
write and dispatches those events.

If the command result is lost, CWA must assume the hosted operation may already have
started.

## Retry / ambiguity invariant

```text
before source mutation
→ ordinary failure where appropriate

source mutation may have executed
→ GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED
→ automatic retry forbidden
```

A lost Native Messaging response after delegation is also ambiguous.

The fact that translation is usually idempotent does not weaken the architecture rule.
Another hosted capability may consume quota, create an artifact or cause a durable
side effect.

## Finality

PR17.0 initially claims only:

```text
PAGE_DOM_STABLE_RESULT
canonical_result_proven = false
```

The current proof requires:

- source textarea still equals the requested text;
- a non-empty translated result is visible;
- no visible page busy state;
- the same translated text remains stable for at least two seconds.

This is browser/page evidence, not a canonical product result API.

## Fresh baseline

Each operation reloads or navigates the CWA-owned Google Translate background tab to a
text-translation route without embedding the input text in the URL.

Before mutation, PR17.0 requires both source text and translated result to be empty.

It fails closed instead of clearing/reusing an uncertain stale result.

## Temporary live gate

During acceptance only:

```powershell
python -m chatgpt_web_adapter.google_translate_web_live_gate_pr17_0
```

The gate performs two independent operations:

```text
English → Spanish
"The house is blue."

English → German
"One two three."
```

It verifies simple semantic anchors plus the non-chat governance/result contract.

The live gate is acceptance instrumentation and must be removed before merge.

## What success would prove

A successful PR17.0 does **not** prove that schema 2 is a generic hosted capability
boundary.

It proves a narrower and more useful statement:

```text
existing local browser bridge
+ authority serialization
+ no-fallback discipline
+ ambiguity / no-replay discipline
+ page-owned observation

can support a useful non-chat hosted capability.
```

At the same time it proves that the current chat runtime types are not the right
public abstraction for that capability.

## What happens after a successful proof

Do not immediately create a large `HostedCapabilityRuntime` hierarchy.

First compare the evidence from:

```text
chat
vs
translation
```

Then identify the smallest genuinely shared layer.

A second non-chat proof such as OCR would be especially valuable because it adds:

- file/image input;
- extraction semantics;
- potentially longer processing;
- possibly different result identity.

Only repeated evidence should decide whether concepts such as `operation`,
`capability`, `result provenance` or a generic browser-owned execution contract
deserve stable shared types.

## Acceptance

PR17.0 is ready to close/merge only when:

```text
deterministic CI green
Google Translate Web live text translation PASS
two language-pair operations PASS
no conversation identity in the spike
no ProductWriteTransport implementation
no ProductProviderBoundary schema claim
no provider-turn registration
no private Google HTTP protocol
automatic retry = false
fallback transport = none
ambiguous delegated/write outcome requires reconciliation
canonical result remains unclaimed
temporary live gate removed before merge
```
