# PR14.9 — Post-Delegation Ordinary-Turn Reconciliation

## Problem

An ordinary continuation can cross the ChatGPT product-write boundary, persist the
user turn, and then lose the generation request with a browser network failure such
as:

```text
CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED
```

Before PR14.9, the browser-owned runtime conservatively classified this whole class
as:

```text
BROWSER_OWNED_WRITE_OUTCOME_UNKNOWN
write_may_have_been_submitted = true
reconciliation_required = true
automatic_retry_allowed = false
```

That no-replay behavior is correct, but it discards evidence CWA already owns.

## Decision

PR14.9 separates three facts:

```text
request-bound identity evidence
    != canonical persistence proof
    != retry authority
```

The existing ordinary request-correlation authority already identifies the exact
product-generated user message id from the actual conversation request body. On a
post-delegation conversation-request failure, CWA may export only the bounded
identity tuple:

```text
conversation_id
user_message_id
runtime_tab_id
request_correlation_proven = true
```

No raw request body, prompt text, headers, cookies, credentials, or SSE payload are
exported by this failure evidence.

Python then performs at most one complete canonical conversation snapshot read under
the same Browser Authority Lease and classifies the result from that one snapshot.

## Classification

```text
prewrite mutation proven absent
    -> NOT_SUBMITTED
       (existing behavior; PR14.9 does not broaden it)

post-delegation exact request identity unavailable
    -> UNKNOWN

exact request-bound user message absent from one complete canonical snapshot
    -> UNKNOWN
       absence is not proof of NOT_SUBMITTED because canonical visibility may lag

exact request-bound user message present
+ canonical current state is user_last_message or running
+ no terminal assistant proven
    -> SUBMITTED_GENERATION_INCOMPLETE

exact request-bound user message present
+ canonical terminal assistant after that user turn
    -> SUBMITTED_TERMINAL_ASSISTANT
```

A canonical state outside those proven cases remains `UNKNOWN`.

## Canonical read boundary

The reconciliation path uses `CanonicalConversationSnapshot`:

- one full-history canonical read;
- exact conversation identity;
- complete snapshot provenance;
- normalized current-branch messages;
- the same canonical payload used by the existing status parser.

Terminality is not redefined. PR14.9 reuses the existing canonical
`_status_from_payload()` semantics on the already-read payload.

## Browser Authority

The failed browser turn carries its exact runtime tab id as part of the bounded
request-bound evidence.

If the reconciliation performs a browser-context canonical read:

1. the read enters under the still-bound Browser Authority Lease;
2. the readback acknowledgement completes that lease;
3. release is bound to the exact failed-turn tab id;
4. disposable policies may therefore close only that exact tab.

No legacy runtime-tab pointer or unrelated retained conversation tab is used as
cleanup identity.

## Failure surface

PR14.9 adds two precise failure kinds:

```text
BROWSER_OWNED_WRITE_SUBMITTED_GENERATION_INCOMPLETE
BROWSER_OWNED_WRITE_SUBMITTED_TERMINAL_ASSISTANT
```

Both remain transport outcomes rather than retry permission.

For `SUBMITTED_GENERATION_INCOMPLETE`:

```text
automatic_retry_allowed = false
manual_retry_safe_after_repair = false
reconciliation_required = true
turn_lifecycle = READBACK_INCOMPLETE
```

For `SUBMITTED_TERMINAL_ASSISTANT`:

```text
automatic_retry_allowed = false
manual_retry_safe_after_repair = false
reconciliation_required = false
turn_lifecycle = FINALIZED
```

PR14.9 deliberately does not synthesize a successful `ChatResponse` after a lost
transport return. It exposes the stronger canonical classification while preserving
the fact that the original transport call failed.

## Non-goals

PR14.9 does not:

- retry or replay the original user turn;
- treat canonical absence as NOT_SUBMITTED;
- compare prompts by fuzzy text/history diff;
- add a second product write;
- infer persistence from the DOM;
- change successful ordinary-turn finality;
- change Temporary Chat semantics;
- add consumer-specific recovery policy.

## Regression requirements

The deterministic gate must prove:

- exact request correlation survives an `ERR_ABORTED`-style failure as bounded
  identity metadata;
- unproven/mismatched identity cannot enter canonical reconciliation;
- one complete snapshot can classify persisted-user/no-assistant as
  `SUBMITTED_GENERATION_INCOMPLETE`;
- one complete snapshot can classify a terminal assistant as
  `SUBMITTED_TERMINAL_ASSISTANT`;
- absent exact user identity remains `UNKNOWN`;
- no product write retry occurs;
- terminal canonical proof finalizes the logical turn;
- incomplete canonical proof leaves reconciliation required;
- browser-context reconciliation releases authority against the exact failed-turn
  tab, including disposable Browser Authority policies.
