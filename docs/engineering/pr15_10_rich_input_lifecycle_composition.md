# PR15.10 — Rich-input lifecycle composition

## Goal

Finish the rich-input runtime ownership consolidation started in PR15.7 by
replacing the six remaining mixed `executeNativeTurn` wrappers with one explicit
lifecycle owner.

## Before

Support-only native-turn ownership was already removed in PR15.7, but six mixed
runtime layers still used import-order monkeypatching:

1. base rich-input lifecycle;
2. closure result semantics;
3. schema 14 model-profile composition guard;
4. schema 18 committed identity normalization;
5. schema 28 identity diagnostic normalization;
6. schema 29 submit/identity diagnostic normalization.

The effective outer-to-inner chain was:

```text
schema 29
→ schema 28
→ schema 18
→ schema 14
→ closure
→ base rich-input
→ prior runtime
```

## After

Those six modules keep their lower-level attachment, submit, page-turn, stream
metadata, identity, and diagnostic hooks, but expose native-turn behavior as
composable `(message, next)` layers.

`service_worker_rich_input_lifecycle.js` is the single native-turn owner for the
cluster. It is imported immediately after the schema 7→29 loader and before
request-text compatibility, preserving the historical boundary around retained
conversation routing and ordinary-text identity authority.

## Preserved boundaries

This change does not alter attachment staging, durable-fence cleanup, total turn
deadline, protected submit, Browser Authority, model-profile conflict behavior,
request-bound conversation identity, committed-readback-incomplete
classification, diagnostic redaction, retry policy, or canonical finality.
