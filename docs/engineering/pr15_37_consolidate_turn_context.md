# PR15.37 — Consolidate rich-input turn-context ownership

## Purpose

Continue #107 by removing source-order replacement from
`_pr92CreateTurnContext`.

Before this slice, the shared factory evolved implicitly:

```text
PR9.2 base deadline/staging context
→ schema 19 request-bound identity fields
→ schema 20 protected-submit correlation fields
```

Later schema26/schema27/schema28 diagnostic paths call the final public factory,
but do not replace it.

## Explicit stages

PR15.37 names each context layer directly:

```text
_pr92BaseCreateTurnContext(message)
_pr92Schema19CreateTurnContext(message)
_pr92Schema20CreateTurnContext(message)
```

The composition is now explicit:

```text
_pr92CreateTurnContext(message)
→ _pr92Schema20CreateTurnContext(message)
→ _pr92Schema19CreateTurnContext(message)
→ _pr92BaseCreateTurnContext(message)
```

The sole public production owner is:

```text
service_worker_turn_context.js
```

## Preserved state

The base context still creates:

- one monotonic total-turn deadline;
- attachment/staging defaults;
- the existing timeout cap and validation.

Schema 19 still adds:

- requested conversation identity;
- causal conversation identity placeholder;
- causal turn-exchange identity placeholder.

Schema 20 still adds:

- protected-submit armed state;
- arm timestamp;
- unique page-side marker;
- marker-observed state;
- post-arm conversation-request collection.

No field is reordered in a way that changes observable values: schema19 still
extends the base first, then schema20 extends schema19.

## Diagnostic consumers

The schema26 and schema27 staging diagnostics and schema28 committed-identity
diagnostic continue calling the public `_pr92CreateTurnContext` dynamically.
They therefore receive the exact same final context shape as production rich
turns without owning or mutating the factory.

## Assembly

The write domain now loads:

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_turn_context.js
→ service_worker_protected_submit_expression.js
→ service_worker_conversation_write_predicate.js
```

All historical schema helpers are defined before the public owner is installed.

## Static target

```text
_pr92CreateTurnContext public definitions = 1
_pr92CreateTurnContext runtime assignments = 0
_pr92Schema19PriorCreateTurnContext aliases = 0
_pr92Schema20PriorCreateTurnContext aliases = 0
```

## Authority

PR15.37 changes context construction ownership only.

It does not change:

- submit authority;
- request classification;
- attachment staging/evidence/cleanup;
- retry policy;
- navigation;
- canonical finality;
- diagnostic write authority.

## Out of scope

Still open after this slice:

- raw `clickSendButton` / `submitWithEnter` nested wrappers;
- ordinary-text `sendCommand` ownership;
- the smaller `connectNativeBridge` product-state wrapper.

Tracking: #107
