# PR15.19 — Consolidate PR8.9 browser response-stream ownership

## Purpose

Continue #107 by removing source-order monkeypatching inside the shipping PR8.9 browser response path.

Before this slice, one response capability was assembled from three workers:

```text
service_worker_safe_browser_response_stream_pr8_9.js
service_worker_safe_browser_response_patch_protocol_pr8_9.js
service_worker_revision_safe_text_delivery_pr8_9.js
```

The second worker reassigned:

```text
_pr89BrowserStreamProcessSseEvent
_pr89BrowserStreamSafeResult
```

and the third reassigned:

```text
_pr89BrowserStreamRecordAssistant
```

Correct behavior therefore depended on import order.

## New production owner

Production now loads exactly one PR8.9 response-stream module:

```text
service_worker_browser_response_stream.js
```

The owner keeps explicit core reducers and explicit production entrypoints:

```text
_pr89BrowserStreamRecordAssistantCore
→ _pr89BrowserStreamRecordAssistant

_pr89BrowserStreamProcessSseEventFullEnvelope
→ _pr89BrowserStreamProcessSseEvent

_pr89BrowserStreamSafeResultCore
→ _pr89BrowserStreamSafeResult
```

The production entrypoints directly own patch-protocol compatibility and revision-safe delivery. They are not installed by runtime assignment.

## Preserved layering

PR15.19 does not collapse the later PR8.11/PR8.12 response overlays. Those layers still depend on the stable PR8.9 hook names and remain composed by:

```text
service_worker_response_lifecycle.js
service_worker_observability_page_turn_lifecycle.js
```

This slice changes ownership inside PR8.9 only.

## Preserved behavior

- page-owned browser write authority is unchanged;
- response observation still uses bounded `Network.streamResourceContent`;
- raw SSE, request bodies, headers, cookies, credentials and protection material are not exported;
- compact `{p, v}` patch protocol reconstruction is preserved;
- full-envelope compatibility remains available;
- assistant text events remain SNAPSHOT / DELTA / REVISION;
- request-bound `turn_event` delivery is preserved;
- canonical readback remains authoritative finality;
- no automatic retry is introduced;
- response lifecycle ordering is unchanged.

## Acceptance

- production imports one PR8.9 response-stream owner instead of three workers;
- the three historical PR8.9 workers are absent;
- `_pr89BrowserStreamRecordAssistant` has one PR8.9 definition and no PR8.9 runtime assignment;
- `_pr89BrowserStreamProcessSseEvent` has one PR8.9 definition and no PR8.9 runtime assignment;
- `_pr89BrowserStreamSafeResult` has one PR8.9 definition and no PR8.9 runtime assignment;
- existing PR8.11/PR8.12 hooks remain compatible;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
