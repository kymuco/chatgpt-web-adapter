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
product-generated user message id from the actual conversation request body. PR14.9
applies this stronger reconciliation only to an existing-conversation continuation,
where the expected conversation id was already bound before delegation. A failed
fresh/new-chat turn does not gain identity from its URL or any post-failure guess and
therefore remains `UNKNOWN`.

Production continuations normally enter the stale-UI recovery send path after the
canonical preflight proves the conversation is completed. That provider path sets
`canonicalCompleted=true`. PR14.9 therefore explicitly extends the same
request-bound ordinary identity authority across `canonicalCompleted` recovery
continuations. The recovery layer still owns reload/stale-UI behavior; the identity
layer only observes and correlates the exact delegated product POST. Disabling
identity authority merely because `canonicalCompleted=true` would make the
post-delegation classifier unreachable on the actual production continuation path.

On an eligible post-delegation conversation-request failure, CWA may export only the
bounded identity tuple:

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


## CWA-owned live acceptance

The live gate is intentionally self-contained and consumer-independent.

It performs exactly two product writes:

```text
1. seed one disposable saved conversation
2. send one existing-conversation continuation with a one-shot observer-failure probe
```

The probe does **not** modify, cancel, replay, or retry the product request. It
injects one diagnostic field into exactly one normal `turn` RPC. The ordinary-text
identity authority passes a diagnostic callback through the existing
`executeOfficialPageTurn` wrapper stack.

After the exact conversation POST has been delegated and its 2xx response headers
are observed, the callback boundedly settles the existing request-body identity
lookup. Only if the exact request correlation is proven does the callback return:

```text
CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED
```

That error is injected at the same local `completed`-promise failure boundary used
by real `Network.loadingFailed` events. The underlying ChatGPT network request is
left untouched and may continue independently; the CWA transport observer fails and
then performs canonical reconciliation.

This distinction is deliberate:

```text
product network cancellation != required proof surface
post-delegation CWA transport failure == required proof surface
```

The probe exports an explicit
`postDelegationObserverFailureProbeTriggered=true` evidence bit. A random network
failure cannot satisfy the live gate without that proof.

The live gate itself wraps the provider RPC and permits exactly one probe
`type="turn"`. Any attempted second probe turn fails locally before it can be sent.
This makes the no-replay acceptance criterion executable rather than inferred.

Run:

```powershell
python -m chatgpt_web_adapter.post_delegation_reconciliation_live_gate \`
  --auth-file auth_data.json \`
  --acknowledge-live-writes
```

Acceptance requires:

```text
deployment identity healthy
seed write succeeds exactly once
probe turn sent exactly once
response-stage observer-failure probe triggered
request-bound user message canonically persisted
outcome = SUBMITTED_GENERATION_INCOMPLETE
       or SUBMITTED_TERMINAL_ASSISTANT
automatic_retry_allowed = false
manual_retry_safe_after_repair = false
no third product write
consumer_dependency = false
```

`UNKNOWN` is a safe runtime classification, but it is not sufficient to graduate
this PR's live acceptance because the live gate exists specifically to prove that
the stronger request-bound + canonical evidence path works on the real product.


## Recovery-continuation reachability receipt

The live acceptance requires an explicit bounded receipt:

```text
post_delegation_recovery_continuation_observed = true
```

This receipt proves that the failing turn was a `canonicalCompleted` stale-UI
recovery continuation **and** that request-bound ordinary identity authority was
active around it. It is separate from the observer-failure-probe receipt and from
canonical persistence proof.

The proof chain is therefore:

```text
production recovery continuation observed
→ exact request correlation proven
→ observer failure probe triggered
→ canonical snapshot complete
→ exact user turn persisted
→ precise submitted outcome
```
