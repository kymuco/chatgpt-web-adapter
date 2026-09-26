# PR15.55 — Minimal Gemini Web provider proof

## Purpose

Use Gemini Web as provider #3 only after the ChatGPT + DeepSeek boundary survived
PR15.54's post-second-provider neutrality audit.

This slice is deliberately narrow:

```text
Gemini Web
→ text new chat
→ text continuation
→ opaque local conversation identity bound to an observed page route
→ page-owned completion evidence
→ no automatic retry
→ no fallback transport
```

It does not add images/files, web-search control, tools/connectors, model selection,
reasoning modes, account pooling, a generic public provider registry, or a generic
ProductRuntime.

## Provider identity

```text
provider_id       = gemini
product_semantics = ordinary-gemini
transport         = gemini-web
support tier      = EXPERIMENTAL
```

The existing schema-2 `ProductProviderBoundary` is reused unchanged.

Gemini declares:

```text
canonical_readback_required = false
canonical_interface = none
automatic_write_retry = false
fallback_transport = none
ambiguous_write_requires_reconciliation = true
incremental_observation_is_canonical_finality = false
```

## Browser composition

Gemini registers one private provider-turn handler in the same extension-internal
registry already proven by DeepSeek:

```text
type=turn, providerId=gemini
→ private provider dispatch
→ service_worker_gemini_provider.js
→ gemini.google.com page/CDP
```

Provider dispatch occurs before ChatGPT diagnostics, observers and native-turn
lifecycle. Gemini therefore does not pass through ChatGPT Browser Authority,
Temporary lifecycle, rich-input handling, model profiles, response-stream hooks or
canonical reconciliation.

The manifest adds only:

```text
https://gemini.google.com/*
```

## No private Gemini HTTP contract

The proof does not use undocumented Google/Gemini request endpoints, fetch/XHR or CDP
Network interception.

The browser worker uses only page/browser ownership:

```text
chrome.tabs
chrome.storage.local
Runtime.evaluate
one page-owned send-control click
```

The initial DOM hypotheses are intentionally narrow and replaceable by live evidence:

```text
composer:
  div.ql-editor[contenteditable=true]
  rich-textarea [contenteditable=true]
  aria-labelled / role=textbox fallbacks

send:
  composer-local Send message / Send / submit / .send-button

assistant response:
  model-response
  message-content
  model-response-text / response-content
  bounded structural fallbacks
```

They are implementation details, not public API.

## Conversation identity

No Gemini conversation route schema is hardcoded.

A successful new-chat turn must produce an observed final URL under
`https://gemini.google.com` that differs from the initial route. The extension then
creates an opaque local UUID and stores:

```text
opaque local id → exact observed Gemini page URL
```

Continuation receives only the opaque id, resolves the exact stored route and requires
the same local identity after the turn.

If Gemini does not expose stable route change semantics in the live product, this
assumption must be falsified and replaced from evidence rather than by guessing an
`/app/<id>` contract.

## Submit / retry authority

The worker writes the composer once and resolves a send control only from the
composer-local DOM surface.

```text
write once
→ click once
→ never replay write
→ never second-click
```

If route navigation detaches the debugger after the click, reattachment is
observation-only. Debugger loss is never permission to replay the write.

## Finality

PR15.55 initially uses the same conservative noncanonical evidence class proven by
DeepSeek:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

Success requires new assistant text relative to the pre-submit baseline, no visible
generation-stop signal, and identical text stable for at least nine seconds.

A post-submit timeout or unrecoverable observation loss becomes:

```text
GEMINI_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED
```

with no automatic retry.

Gemini live evidence is allowed to falsify this finality rule.

## Python surface

PR15.55 adds experimental module-only classes:

```text
GeminiBrowserTurnProvider
GeminiWebTransport
GeminiWebRuntime
```

They are not added to the ChatGPT transport assembler or root public API.

Only:

```text
text_turns   = AVAILABLE
new_chat     = AVAILABLE
continuation = AVAILABLE
```

Everything else remains UNKNOWN or UNIMPLEMENTED.

## Live acceptance

Real logged-in Gemini Web acceptance passed on PR15.55 at production head
`0a7acadcb36b93383c7277820c14795c45d79c75`.

Observed acceptance:

```text
provider boundary schema 2 passes
provider_id = gemini
product_semantics = ordinary-gemini
transport = gemini-web
new-chat marker observed
opaque conversation id established
continuation marker observed
continuation preserves the same opaque conversation id
automatic write retry = false
fallback transport = none
canonical completion proven = false
result = PASS
```

The executable live gate was acceptance-only instrumentation and is removed before
merge. The repository keeps the production runtime, deterministic regressions and this
evidence record.

## Post-live review hardening

Review after the successful live run identified two ambiguity-classification gaps
without changing the successful write path.

First, once the single page-owned submit returns, every later observation/route/storage
failure is now classified as:

```text
GEMINI_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED
```

rather than escaping as an ordinary retryable-looking error.

Second, Native Messaging response loss after the turn has already been delegated is
mapped to `GeminiWebWriteOutcomeAmbiguousError`. Bridge failures before delegation
remain ordinary request failures.

The invariant is therefore:

```text
before delegation / before submit uncertainty
→ ordinary failure where appropriate

after delegation / after submit uncertainty
→ reconciliation required
→ automatic retry forbidden
```


## Acceptance

PR15.55 acceptance requires all of the following:

```text
provider boundary passes
real Gemini composer write succeeds
exactly one page-owned submit succeeds
first marker observed
opaque conversation id established
second marker observed
continuation preserves the same opaque id
automatic write retry = false
fallback transport = none
canonical completion proven = false
deterministic CI = green
temporary live gate removed before merge
```
