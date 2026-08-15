# PR8.2.4a.1 — Canonical Readback Completion-Signal Parity

PR8.2.4a.1 repairs the false readback timeout observed after a successful
browser-owned ChatGPT turn. The product write completed and the ChatGPT UI
finished normally, but the SDK waiter rejected the canonical assistant message
because `ChatMessage.finish_reason` was missing.

## Root cause

Before this repair, `messages.py` recognized only
`metadata.finish_details.type` as a message finish reason. `status.py` already
recognized the wider product signal set:

1. `metadata.finish_details.type`
2. `metadata.finish_reason`
3. top-level `message.finish_reason`
4. completed async status for conversation finality

The browser-native readback waiter then required a truthy
`ChatMessage.finish_reason`, so a conversation could be canonically completed
while the waiter continued until timeout.

## Repair

`messages.py` now uses the same three finish-reason sources as `status.py`.

The browser-native readback waiter keeps explicit finish reason as a fast path.
When finish reason is absent, it accepts a new non-empty assistant message only
when canonical status is `completed` and the status `message_id` exactly matches
the candidate assistant `message_id`.

This message-ID alignment prevents an older completed status from finalizing a
new partial assistant message.

## Failure evidence preservation

`send_text_observed()` already forwards browser-native events to the caller callback.
The operator example now captures `browser_native_write_completed` through that
callback before invoking the observed send. If canonical readback later fails,
the example emits structured JSON with the captured runtime-tab observation
instead of losing that evidence behind a traceback.

A readback failure after accepted write remains non-retryable:

- `write_may_have_been_submitted = true`
- `automatic_retry_allowed = false`
- `manual_retry_safe_after_repair = false`
- `reconciliation_required = true`

The repair does not resend a turn automatically.

## Acceptance gates

- finish-details finality remains supported
- metadata `finish_reason` fallback is supported
- top-level `finish_reason` fallback is supported
- `completed` + matching message ID finalizes a non-empty assistant
- stale completed message ID cannot finalize a new partial assistant
- running status cannot finalize a message without finish reason
- accepted-write/readback failure preserves runtime-tab observation
- no automatic write retry is introduced

## Governance boundary

This PR changes canonical read interpretation and error observability only. It
does not alter the page-owned write mechanism, submit ladder, extension browser
protection boundary, authentication, session renewal, Sentinel/Turnstile logic,
or direct product-write behavior.
