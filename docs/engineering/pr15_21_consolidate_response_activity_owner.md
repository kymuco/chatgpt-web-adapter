# PR15.21 — Consolidate PR8.12 response activity ownership

## Purpose

Continue #107 by removing the remaining source-order composition inside PR8.12.

Before this slice, production loaded three PR8.12 workers:

```text
service_worker_normalized_activity_stream_pr8_12.js
service_worker_normalized_activity_patch_protocol_pr8_12.js
service_worker_answer_channel_pr8_12.js
```

The base activity worker wrapped the PR8.11 SSE hook. A later patch worker reassigned the activity patch reducers. A later answer-channel worker separately reassigned the PR8.9 visible-assistant and record-assistant hooks.

## New production owner

Production now loads exactly one PR8.12 response owner:

```text
service_worker_response_activity.js
```

It owns three explicit response hooks:

```text
_pr89BrowserStreamProcessSseEvent
_pr89BrowserStreamVisibleAssistantText
_pr89BrowserStreamRecordAssistant
```

Each is installed exactly once by PR8.12.

## Explicit activity composition

The SSE activity path is:

```text
_pr812ProcessSseEventOwner
→ _pr812ProcessSseEventLayer
→ upstream PR8.11 response owner
```

The normalized native-turn lifecycle hook remains:

```text
_pr812ExecuteNativeTurn
```

and remains composed by the existing PR15.8 response lifecycle owner.

## Patch compatibility

Compact patch compatibility is no longer installed by runtime reassignment.

The new owner keeps explicit core/final reducers:

```text
_pr812PatchSelectCore
→ _pr812PatchSelect

_pr812PatchApplyItemCore
→ _pr812PatchApplyItem
```

The final reducers preserve:

- stable synthetic ids for patch messages lacking an id;
- compact null-path text append behavior;
- explicit `/message/content/parts/0` behavior;
- status/end-turn/metadata updates;
- dynamic use of `_pr812InspectMessage`, so the later connector overlay remains effective.

## Answer channel

Optional `final` / `commentary` evidence remains bounded and normalized.

The owner explicitly layers:

```text
_pr812VisibleAssistantTextLayer
_pr812RecordAssistantLayer
```

over the upstream response hooks, preserving channel memory by assistant message key without exporting raw metadata.

## Preserved outer layers

This slice intentionally does not absorb later overlays.

- PR10.0 connector metadata/router layers still load after PR8.12 and may wrap `_pr812InspectMessage`.
- PR8.13 Temporary session identity still loads later and may wrap the SSE hook outside PR8.12.
- Temporary lifecycle/write/finality semantics are unchanged.
- Canonical readback remains authoritative.
- No automatic retry or second product-write path is introduced.

## Acceptance

- shipping PR8.12 workers reduce from three to one;
- one PR8.12 install of `_pr89BrowserStreamProcessSseEvent`;
- one PR8.12 install of `_pr89BrowserStreamVisibleAssistantText`;
- one PR8.12 install of `_pr89BrowserStreamRecordAssistant`;
- one direct `_pr812PatchSelect` definition and no reassignment;
- one direct `_pr812PatchApplyItem` definition and no reassignment;
- retired prior-function aliases are absent;
- connector and Temporary load boundaries remain outside the owner;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
