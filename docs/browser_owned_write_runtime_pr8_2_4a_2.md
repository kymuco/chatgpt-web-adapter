# PR8.2.4a.2 — Canonical Message-Level Completion Signal Recovery

PR8.2.4a.2 repairs a false-running status classification discovered during the
PR8.2.4a.1 live validation.

The ordinary ChatGPT UI had already completed the assistant turn, but
`ChatGPTWebClient.get_status()` returned `running`, so the production write
facade correctly refused to start another turn.

A read-only raw canonical payload probe established that the final assistant
message carries explicit top-level message completion signals:

```text
message.status   = "finished_successfully"
message.end_turn = true
```

The previous status parser inspected payload/node/metadata async status and
finish-reason fields, but did not inspect these top-level message fields.

## Repair

`status.py` now treats message-level finality as a separate signal plane.

The only newly recognized completed message status is the exact live-observed
value:

```text
finished_successfully
```

`message.end_turn == true` is also explicit assistant-turn completion evidence.

No guessed or speculative message status values are added.

## Precedence

Completion does not override stronger active/action states.

The classifier preserves this order:

```text
pending approval
→ tool role
→ assistant tool recipient
→ active async status
→ active message status
→ user-last-message
→ assistant finish reason
→ completed async status
→ message.status == finished_successfully
→ message.end_turn == true
→ running/unknown
```

Therefore a contradictory active signal remains blocking even if an `end_turn`
field is present.

## Diagnostics

For bounded status diagnostics, `ConversationStatus.metadata_preview` now also
includes these selected top-level message-level finality fields when present:

```text
message_status
end_turn
```

This does not expose message text, raw payloads, authentication state, cookies,
or browser protection material.

## PR8.2.4a.1 integration

PR8.2.4a.1 already accepts a canonical assistant without `finish_reason` when:

```text
status.status == completed
AND status.message_id == assistant.message_id
```

Recovering the correct message-level status therefore repairs both:

1. pre-write health / commit-point false-running rejection; and
2. post-write message-ID-aligned canonical readback finality.

No stability timer or text-presence heuristic is introduced.

## Governance

This PR does not modify:

- the browser extension;
- Chrome/CDP input or submit behavior;
- the protected product-write path;
- Native Messaging;
- auth/session renewal;
- challenge/Sentinel/Turnstile/proof behavior;
- automatic retry policy.

A delegated write is still never automatically retried.

## Live acceptance

On the previously blocked conversation, a health-only probe should change from:

```text
ready=false
canonical_status=running
```

to:

```text
ready=true
canonical_status=completed
```

without sending a turn.

The subsequent explicit live write can then exercise the PR8.2.4a.1 readback
repair using a fresh marker.
