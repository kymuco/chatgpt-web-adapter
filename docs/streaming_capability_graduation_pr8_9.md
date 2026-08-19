# PR8.9.4 — Streaming Capability Graduation and Public Contract Finalization

Status: **production capability graduated**

PR8.9.3 proved that revision-safe assistant text can be delivered through the normal `ChatGPTProductRuntime.on_event` path before the browser-owned write completes while preserving a single product write and canonical finality.

## Production evidence

The PR8.9.3 production live gate observed:

- one product write and one write completion;
- automatic write retry disabled;
- 33 revision-safe streaming events delivered to the high-level runtime;
- 1 `assistant_text_snapshot` and 32 `assistant_text_delta` events;
- first streamed text 16,472 ms before `browser_native_write_completed`;
- canonical finalization after the browser write;
- `EXACT_MATCH` reconciliation between the provisional stream and canonical final text;
- canonical finality remained authoritative.

This is sufficient to graduate the browser-owned `streaming` capability from `UNKNOWN` to `AVAILABLE`.

## Public contract

Streaming is exposed through the existing `on_event` callback accepted by `ChatGPTProductRuntime.send_text()`, `send()`, and `send_text_observed()`.

Revision-safe text events are:

- `assistant_text_snapshot`
- `assistant_text_delta`
- `assistant_text_revision`
- `canonical_text_finalized`

The provisional stream is not final authority. `canonical_text_finalized` carries the canonical text and one explicit reconciliation state:

- `EXACT_MATCH`
- `CANONICAL_EXTENDS_STREAM`
- `STREAM_REVISED_BY_CANONICAL`
- `STREAM_INCOMPLETE`
- `UNAVAILABLE`

`on_token` remains **final-only**. It is intentionally not redefined as append-only live streaming because a revision-safe transport must be able to replace already observed provisional text.

## Ownership and safety

The browser-owned transport owns early text observation through the page-owned response stream. Canonical HTTP remains the finality and reconciliation authority.

The production contract preserves:

- one product write;
- one Browser Authority lease;
- one request id and one loopback connection per turn;
- no automatic retry after delegation;
- no raw SSE export;
- no request-body/header/cookie export;
- callback failure cannot replay or invalidate an already delegated product write.

## Governance values

`BrowserOwnedProductTransport.governance()` declares:

- `streaming_supported = true`
- `streaming_contract_version = 1`
- `streaming_event_surface = "on_event"`
- `streaming_source = "CDP_NETWORK_STREAM_RESOURCE_CONTENT"`
- `streaming_delivery = "REVISION_SAFE_EVENT_STREAM"`
- `streaming_canonical_finality = "BROWSERLESS_CANONICAL_HTTP"`
- `streaming_canonical_finality_authoritative = true`
- `streaming_legacy_on_token_semantics = "FINAL_ONLY"`
- `streaming_raw_sse_exported = false`
- `streaming_automatic_write_retry = false`

No additional live write is required for this graduation slice; it is a declaration-and-contract step backed by the already successful PR8.9.3 production gate.
