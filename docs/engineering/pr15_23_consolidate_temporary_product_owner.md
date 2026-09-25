# PR15.23 — Consolidate PR8.13 Temporary product ownership

## Purpose

Continue #107 by collapsing the PR8.13 Temporary production owner and its two identity repair overlays into one explicit shipping module.

Before:

```text
service_worker_temporary_chat_production_pr8_13.js
service_worker_temporary_session_identity_pr8_13.js
service_worker_temporary_fresh_identity_flush_pr8_13.js
```

The session-identity worker reassigned `_pr89BrowserStreamProcessSseEvent`.
The fresh-identity worker reassigned `_pr813ConversationId`.

## New owner

```text
service_worker_temporary_product.js
```

Identity normalization is now explicit:

```text
_pr813ConversationIdCore
→ _pr813ConversationId
```

The public Temporary normalizer directly owns the fresh-session sentinel behavior. No late reassignment is required.

Live SSE session identity is also installed once:

```text
_pr813SessionIdentityUpstreamProcessSseEvent = _pr89BrowserStreamProcessSseEvent
_pr89BrowserStreamProcessSseEvent = _pr813ProcessSseWithTemporarySessionIdentity
```

## Preserved boundaries

- Temporary mode is still proven from the browser-local paused request body before network dispatch;
- `history_and_training_disabled === true` remains the authoritative prewrite proof;
- fresh Temporary requests still must omit `conversation_id`;
- continuation requests still require exact live conversation identity;
- Temporary conversation ids remain session-local routing metadata, not durable continuation authority;
- fresh identity still resolves only from the active Temporary context/live lifecycle;
- canonical product write and no-retry semantics remain unchanged;
- startup readiness remains a separate outer layer;
- explicit Temporary native lifecycle composition remains a separate owner;
- official page-turn composition remains unchanged.

## Acceptance

- shipping Temporary product workers reduce 3 → 1;
- one direct `_pr813ConversationId` definition;
- one `_pr89BrowserStreamProcessSseEvent` install;
- zero retired fresh/session prior aliases;
- old three imports absent;
- PR15.11 native lifecycle order remains unchanged;
- PR15.14 page-turn order remains unchanged;
- engineering quality + JS syntax green;
- Linux/Windows Python 3.10–3.14 green;
- release build + installed-wheel smoke green.

Tracking: #107


## PR15.50 closure follow-up

PR15.50 removes the remaining Temporary SSE captured-upstream alias and public
`_pr89BrowserStreamProcessSseEvent` reassignment. The Temporary product now
exposes `_pr813ProcessSseWithTemporarySessionIdentity(...)` as an explicit
layer delegating directly to `_pr812ProcessSseEventOwner(...)`. The final public
stream-hook owner is assembled immediately after the Temporary product.
