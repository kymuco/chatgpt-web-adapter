# PR14.1 — Request-Bound Ordinary-Text Conversation Identity Authority

## Purpose

Issue #79 proved that an ordinary browser-owned text write can complete successfully
while the SPA route exposes a namespaced display identity such as `WEB:<uuid>`.
The canonical read plane rejects that route identity even though the exact request
stream carries a valid bare conversation id.

The production invariant is therefore:

```text
browser route identity != canonical conversation identity authority
```

PR14.1 makes conversation identity for an ordinary text write authoritative only
when it is bound to the exact protected write request and supported by one
request-bound protocol consensus.

## Evidence inherited from #79

Three bounded live runs established the failure mode without retrying writes:

1. an ordinary write completed after the local RPC acknowledgement was lost;
2. a later run showed a route identity in `WEB:<uuid>` form that canonical reads
   rejected with HTTP 400;
3. request-bound SSE on the exact conversation POST emitted one stable bare
   `conversation_id` consensus across seven records, and canonical readback on
   that identity recovered the exact user/assistant turn.

This evidence does not authorize trusting every conversation POST. It only proves
that the protocol identity is useful once the request itself has been bound to the
protected logical user message.

## Why PR #80 is superseded rather than merged

PR #80 discovered the correct authority direction but its branch also contains
unrelated live journals, probes and historical final-review work. Its first
implementation had three correctness gaps:

- production assembly depended on diagnostic capture instrumentation;
- request-body correlation was observational rather than a hard prerequisite;
- response-body identity conflict was observed but not enforced fail-closed.

PR14.1 carries forward the evidence and authority model, not that branch topology.
The new delta is built directly on current `main` after PR14.0.

## Authority chain

PR14.1 requires all stages below before a conversation id can be promoted:

```text
ordinary text turn
  -> PR11.3 protected submit commit boundary
  -> post-commit conversation POST
  -> schema-29 exact request-body correlation
  -> request-bound protocol identity evidence
  -> one verbatim consensus
  -> promoted conversation identity
```

No individual stage implies the next stage.

### 1. Ordinary-text scope

The authority applies only to ordinary saved text turns:

- non-empty text;
- zero attachment paths;
- `conversationMode=normal`;
- not stale canonical-completion reconciliation;
- not a Temporary Chat, rich-input, connector, artifact, model, timing or other
  characterization/probe turn.

Specialized write paths remain owned by their existing contracts.

### 2. Protected submit boundary

The layer is installed after `service_worker_text_submit_commit_hardening_pr11_3.js`.
It observes the actual PR11.3 commit primitives:

```text
mouse submit: Input.dispatchMouseEvent(type=mouseReleased)
enter fallback: Input.dispatchKeyEvent(type=keyDown, Enter)
```

Conversation requests observed before that boundary have no identity authority.
The new layer does not perform a submit itself and does not add any retry path.

### 3. Exact request-body correlation

Each post-commit conversation POST is inspected with the already-reviewed schema-29
helper:

```text
_pr92Schema29InspectRequestPostData(
    postData,
    expectedText,
    0,
    expectedConversationId,
)
```

The first post-commit conversation request must prove:

- `action=next`;
- exact intended prompt text;
- one logical user message id;
- zero attachments;
- correct new-chat or continuation conversation semantics.

If CDP omits `Request.postData`, PR14.1 performs an exact-request
`Network.getRequestPostData(requestId)` lookup and waits for that asynchronous
lookup only within a bounded settle budget. Unresolved request bodies remain
fail-closed.

Additional post-commit requests can belong to the same logical user message, but a
foreign logical user-message id invalidates correlation.

```text
post-commit request observed != exact logical request bound
```

### 4. Request-bound protocol identity

Only requests that passed the exact body correlation can contribute conversation
identity.

For a matched request, the primary channel is streamed network content:

```text
Network.responseReceived
  -> Network.streamResourceContent(requestId)
  -> bufferedData + Network.dataReceived(requestId)
  -> bounded SSE parser
```

Conversation-id extraction reuses the existing schema-29 protocol parser:

```text
_pr92Schema29ExtractRequestBoundConversationMetadata(...)
```

If no usable streamed identity exists and the exact matched request reached
`Network.loadingFinished`, PR14.1 may use one exact-request
`Network.getResponseBody(requestId)` fallback.

The SPA route is never consulted by this authority layer.

## Conflict and completeness semantics

Authority is fail-closed:

```text
0 protocol ids
  -> SSE_IDENTITY_UNRESOLVED

>1 protocol ids
  -> SSE_IDENTITY_CONFLICT

continuation consensus != requested conversation id
  -> SSE_REQUEST_IDENTITY_MISMATCH

conflicting response-body ids
  -> RESPONSE_IDENTITY_CONFLICT

truncated bounded SSE identity buffer
  -> SSE_CAPTURE_TRUNCATED

request-body correlation incomplete / mismatched
  -> ORDINARY_REQUEST_CORRELATION_UNRESOLVED
```

All authority failures use the existing committed-write prefix:

```text
PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED
```

The Python browser-native provider already maps that state to a committed-write
identity-unresolved timeout. The failure therefore does not grant automatic retry
or second-submit authority.

## Verbatim promotion

Exactly one request-bound protocol identity is promoted verbatim.

PR14.1 does not:

- strip `WEB:`;
- extract a UUID from a namespaced string;
- rewrite prefixes;
- infer identity from the final URL;
- compare route shape and choose the more convenient value.

If the protocol itself ever emits a form the canonical plane rejects, canonical
readback remains the final authority and the adapter must fail rather than invent a
translation.

## Success metadata

A successful ordinary text turn carries bounded authority metadata:

```text
conversationId
ordinaryTextConversationIdentityAuthority = REQUEST_BOUND_ORDINARY_TEXT_PROTOCOL_CONSENSUS
ordinaryTextRequestCorrelation = SCHEMA29_EXACT_REQUEST_BODY_IDENTITY
ordinaryTextConversationIdentitySource = sse_stream | response_body | sse_and_response_body
ordinaryTextMatchingRequestCount
routeConversationIdentityAuthoritative = false
```

Raw SSE, request bodies, message ids, request ids, credentials and route ids are
not persisted by this layer.

## Deterministic regression target

The PR14.1 executable Node harness drives the actual authority wrapper through
mocked CDP events and must prove:

- authority is loaded last in the write domain;
- no diagnostic module is required;
- pre-commit conversation requests have no authority;
- exact request-body binding succeeds;
- exact-text mismatch fails closed;
- unresolved async `getRequestPostData` fails closed;
- async request-body lookup settles before protocol identity authority;
- streaming protocol identity overrides a deliberately wrong `WEB:` route value;
- non-streaming completed requests can use exact response-body fallback;
- response-body identity conflict fails closed;
- continuation identity mismatch fails closed;
- both mouse-release and Enter-keydown PR11.3 commit boundaries are supported;
- no route parser or `WEB:` normalization exists in the authority module.

The existing runtime-consolidation test also treats the PR14.1 module as the final
write-domain layer and keeps read/observation domains separated.

## Live acceptance target

Before merge, one exact-head authenticated ordinary-text write is required.
The gate is intentionally bounded:

```text
one ordinary new-chat submit
zero automatic retry
zero second submit
```

Acceptance requires:

1. the returned identity is produced by the PR14.1 authority metadata;
2. `routeConversationIdentityAuthoritative` is false;
3. canonical readback accepts the returned identity;
4. canonical history contains the exact submitted client turn and its assistant
   response;
5. no route-derived identity is used as fallback;
6. if identity authority cannot be proven, the gate stops and does not retry the
   write.

The live gate is a product write and therefore remains human-gated. Deterministic
CI must be green first.

## Non-goals

PR14.1 does not add:

- multi-provider identity abstraction;
- route normalization;
- automatic write retry;
- second-submit recovery;
- changes to Temporary Chat identity semantics;
- changes to rich-input identity semantics;
- new canonical-read behavior;
- diagnostic journals or live-capture artifacts in production assembly.
