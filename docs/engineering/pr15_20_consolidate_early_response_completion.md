# PR15.20 — Consolidate PR8.11 early response completion ownership

## Purpose

Continue #107 by removing the remaining source-order composition inside the PR8.11 early-response stack.

Before this slice, three shipping workers layered behavior over the PR8.9 response hooks:

```text
service_worker_post_answer_tail_timing_pr8_11.js
service_worker_early_product_completion_pr8_11_1.js
service_worker_early_product_completion_repair_pr8_11_1.js
```

The historical text hook was assembled as:

```text
repair
→ early completion characterization
→ tail timing
→ PR8.9 response stream
```

and the SSE hook as:

```text
repair
→ early completion characterization
→ PR8.9 response stream
```

The repair also reassigned `_pr8111FirstTerminal` after the characterization worker had already defined it.

## New production owner

Production now loads:

```text
service_worker_early_response_completion.js
```

Internal behavior is expressed as explicit layer functions:

```text
_pr8111RepairRecordAssistantLayer
_pr8111RecordAssistantLayer
_pr811TailRecordAssistantLayer

_pr8111RepairProcessSseEventLayer
_pr8111ProcessSseEventLayer
```

and a single install on each PR8.9 hook:

```text
_pr89BrowserStreamRecordAssistant = _pr811RecordAssistantOwner
_pr89BrowserStreamProcessSseEvent = _pr811ProcessSseEventOwner
```

The historical nesting order is preserved explicitly.

## Terminal semantics

The repaired terminal selector is now the sole direct definition of:

```text
_pr8111FirstTerminal
```

The earlier superseded selector is not retained.

The fail-closed early boundary remains:

```text
visible assistant text
+
finish_reason for the current visible answer
+
(end_turn OR is_complete) for the current visible answer
→ assistant terminal candidate
```

Pre-text generic completion status remains diagnostic only and cannot establish current-answer completion.

## Preserved boundaries

- page-owned browser write authority is unchanged;
- canonical HTTP readback remains final authority;
- no automatic retry is introduced;
- no prompt/model-selection behavior changes;
- tail timing remains numeric-only observability;
- raw assistant text, raw SSE, request bodies, cookies and credentials are not persisted by PR8.11 diagnostics;
- composer readiness polling remains observational;
- PR15.8 response lifecycle order is unchanged;
- PR15.13 page-turn lifecycle order is unchanged;
- later PR8.12 activity/answer-channel overlays remain outside this owner.

## Updated-main revalidation

While this PR was in CI, main advanced through PR13.6 canonical conversation read timeout recovery. That change is confined to the Python canonical-read implementation and its dedicated test; it does not overlap this PR's browser-native extension or ownership-regression files.

This note commit intentionally retriggers pull-request CI so the final merge ref is validated against the updated main rather than relying on the earlier green merge ref.

## Acceptance

- one shipping PR8.11 owner replaces three workers;
- exactly one PR8.11 install on `_pr89BrowserStreamRecordAssistant`;
- exactly one PR8.11 install on `_pr89BrowserStreamProcessSseEvent`;
- one direct repaired `_pr8111FirstTerminal` definition, no reassignment;
- old three PR8.11 files are absent;
- explicit internal order matches the historical chain;
- PR8.12 still loads after the PR8.11 owner;
- engineering quality and JavaScript syntax pass;
- full Linux/Windows Python 3.10–3.14 matrix passes;
- release build and installed-wheel smoke pass.

Tracking: #107
