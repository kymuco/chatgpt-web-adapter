# PR15.36 — Consolidate conversation-write predicate ownership

## Purpose

Continue #107 by removing the remaining runtime reassignment of
`isConversationWrite`.

Before this slice, the shared public predicate started as a structural
URL/method classifier in `service_worker.js`. Schema 20 then captured that
function as `_pr92Schema20PriorIsConversationWrite` and replaced the public
name with a rich-input submit-authority gate.

Schema 29 deliberately reused the captured prior binding because it needs to
classify requests that are already known to be post-arm without reapplying the
schema-20 gate.

That behavior was correct, but the ownership contract depended on source order
and a hidden "prior" alias.

## Explicit concepts

PR15.36 separates the two concepts:

```text
_cwaBaseIsConversationWrite(url, method)
```

is the structural classifier only:

- method must be POST;
- origin must be https://chatgpt.com;
- path must be the supported conversation endpoint.

```text
_pr92Schema20SubmitBoundConversationWrite(url, method)
```

is the rich-input authority gate:

```text
base structural match
AND
(no active rich-input context OR protected submit has been armed)
```

The sole public production owner is:

```text
service_worker_conversation_write_predicate.js
```

with explicit composition:

```text
isConversationWrite(...)
→ _pr92Schema20SubmitBoundConversationWrite(...)
→ _cwaBaseIsConversationWrite(...)
```

## Why schema 29 uses the base classifier

Schema 29's request-body correlation observes only after
`schema20ProtectedSubmitArmed === true`.

Its recorder must answer a different question from schema 17:

```text
"Is this request structurally a ChatGPT conversation write?"
```

not:

```text
"Does this request currently have submit authority?"
```

Therefore schema 29 now calls `_cwaBaseIsConversationWrite` explicitly.
This preserves the old captured-prior semantics without relying on mutation
history.

Schema 20's own raw post-arm diagnostic recorder uses the same base classifier
for the same reason.

## Preserved authority

Schema 17 and other dynamic consumers continue calling the public
`isConversationWrite` predicate. During a rich turn, pre-arm conversation
requests therefore remain denied. With no active rich-input context, ordinary
text behavior remains the structural base predicate.

No request is newly authorized. No retry, write, navigation, finality, or
request-body authority is added.

## Assembly

The write domain now installs the explicit owner after the complete rich-input
schema loader:

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_protected_submit_expression.js
→ service_worker_conversation_write_predicate.js
→ service_worker_attachment_evidence.js
```

## Static target

```text
isConversationWrite public definitions = 1
isConversationWrite runtime assignments = 0
_pr92Schema20PriorIsConversationWrite aliases = 0
```

## Out of scope

PR15.36 does not consolidate:

- `_pr92CreateTurnContext`, which still had schema19/schema20 source-order
  ownership;
- raw `clickSendButton` / `submitWithEnter` wrappers;
- ordinary-text `sendCommand` ownership;
- the smaller `connectNativeBridge` wrapper.

Tracking: #107


## Follow-up ownership note

PR15.37 later consolidates the rich-input turn-context factory. The schema26,
schema27, and schema28 diagnostic paths consume the factory but do not replace it.
