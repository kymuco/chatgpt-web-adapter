# PR8.13 — Temporary Chat session semantics addendum

_Status: implementation clarification after first production live-gate failure_

_Date: 2026-08-21_

## Decision

Temporary Chat is a **live session capability**, not a durable conversation capability.

The product may emit a stable Temporary conversation-shaped identifier while the source session is live, and that identifier may be required internally to route the next page-owned POST. It does not become a public continuation authority.

```text
Temporary product conversation id = ephemeral session routing identity
Temporary product conversation id != durable conversation handle
Temporary product conversation id != attach/reopen authority
Temporary product conversation id != post-close write authority
```

Continuation authority remains the conjunction of:

```text
same live runtime/process
+ same opaque lifecycle token
+ same CWA-owned Temporary tab
+ same internally retained Temporary routing identity
+ lifecycle state == LIVE
```

Closing/ending the lifecycle revokes write authority. Reopening `/c/<temporary-id>` may recover already completed visible turns, as PR8.7 observed, but does not restore a writable Temporary session; controlled post-close continuation returned HTTP 404.

## Why the first PR8.13 live gate failed

The first integrated production gate reached:

```text
CHATGPT_TURN_MISSING_CONVERSATION_ID
```

The failure was not evidence that the Temporary write or prewrite proof failed. It exposed an ordinary-chat assumption inherited by the base browser-native turn path:

```text
page turn returns
→ conversation id expected from complete SSE response body or /c/<id> URL
→ PR8.11.1 early completion may skip complete response-body read
→ Temporary source URL remains on the Temporary surface
→ ordinary fallback identity is absent
→ base turn rejects missing conversation id
```

PR8.13 repairs only the identity handoff. The already active PR8.9 live SSE observer recognizes bounded `stream_handoff` metadata and records:

```text
conversation_id
turn_exchange_id
```

for the active Temporary lifecycle. The ID is used only as internal session routing metadata. The repair does not:

- open `/c/<id>`;
- call ordinary canonical `GET /backend-api/conversation/<id>`;
- wait for the full response body;
- synthesize a private conversation request;
- persist or export a lifecycle credential;
- permit continuation from an ID alone.

## Payload/read semantics

PR8.7 already established that the ordinary canonical conversation endpoint returns `404 / NOT_FOUND` for a true Temporary conversation both while the source session is live and after it closes. That does **not** prove the absence of server-side Temporary state.

PR8.7 also established that, after source close, the product route `/c/<temporary-id>` could recover completed visible turns while the ordinary history/sidebar remained absent, yet a controlled continuation write returned HTTP 404.

Therefore any future Temporary content snapshot should be explicitly session-scoped, for example:

```text
TemporarySessionSnapshot
```

and should be sourced from the live page/product stream or other proven product-session observation plane. It must not be represented as an ordinary durable `ConversationSnapshot` unless a real durable canonical contract is later proven.

## Invariant

```text
identity != permission
recoverability != write authority
server-side retention != durable conversation semantics
Temporary == live lifecycle
```
