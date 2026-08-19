# PR8.8 — Unified GPT-5.6 Sol Instant Route Semantics

## Scope

This slice changes only route interpretation and validation. It does not change
the reasoning-effort slider, product-write path, Browser Authority lifecycle,
automatic retry policy, prompt insertion, submit behavior, or tab disposal.

## Live evidence that motivated the repair

A completed production smoke independently proved all of the following before
route validation:

- selected product effort changed from `HIGH` to `INSTANT`;
- ARIA slider changed from `2` to `0`;
- `selected_mode_before_write = INSTANT` was proven at the composer;
- the conversation request was observed;
- the product write completed;
- Browser Authority release was proven.

The request identified `gpt-5-6`. Response metadata also contained identifiers
such as `gpt-5-6-auto-thinking` and `gpt-5-6-thinking`, but both request and
response carried zero bounded `reasoning_hint_keys` and zero `reasoning_states`.

The old classifier incorrectly treated the word `thinking` inside a model slug
as proof of a reasoning route.

## Governance repair

Model identity and reasoning state are now separate evidence dimensions.

A `model` / `model_slug` value may contribute model-family identity and bounded
alias evidence. It does not, by itself, make `reasoning_route_observed = true`.

Positive reasoning-route evidence remains fail-closed. An explicit bounded
reasoning/thinking key that resolves `ON`, or an explicit reasoning/thinking key
without an explicit `OFF` state, still produces `REASONING_ROUTE_OBSERVED`.

When the independently proven UI mode is `INSTANT`, the network evidence
contains a `gpt-5-6*` model identifier, and there is no explicit reasoning
metadata, the neutral network status is:

`UNIFIED_GPT_5_6_ROUTE_WITHOUT_EXPLICIT_REASONING`

This status does not claim that network metadata proves "no reasoning". It only
prevents a model-slug alias from manufacturing a contradiction to the stronger
product-UI evidence.

## Product documentation boundary

OpenAI's August 6, 2026 product announcement states that, for Plus and Pro
users, the same GPT-5.6 Sol model powers both Instant responses and deeper
reasoning through the new slider. Some Help Center material still describes
the earlier GPT-5.5 Instant / GPT-5.6 reasoning split. The adapter therefore
does not hard-code "Instant always means GPT-5.6 Sol". It accepts unified
GPT-5.6 network identity only when the product UI independently proves
`INSTANT` and explicit reasoning metadata is absent.

## Shipping decision

The successful smoke is sufficient evidence for this repair. No additional
live product write is required merely to prove the new classifier; the captured
specimen is represented as a regression fixture.
