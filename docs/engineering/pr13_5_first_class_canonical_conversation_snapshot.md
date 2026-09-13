# PR13.5 — First-Class Canonical Conversation Snapshot

## Purpose

Promote complete canonical conversation history from a private payload-reader detail
into a stable public value object without exposing ChatGPT pagination, cursors, or
wire-shape drift as application contracts.

## Public surface

`ChatGPTWebClient` and `ChatGPTProductRuntime` expose:

```python
snapshot = client.get_conversation_snapshot(conversation)
# or
snapshot = runtime.get_conversation_snapshot(conversation)
```

The result is `CanonicalConversationSnapshot`.

Stable application-facing projection:

```python
snapshot.messages
snapshot.message_count
snapshot.current_node
snapshot.title
snapshot.complete
snapshot.provenance
snapshot.to_dict()
```

`ConversationReadProvenance` records only bounded canonical evidence:

- `complete`;
- `canonical_record_count`;
- `read_scope="full_history"`.

It deliberately does not expose endpoint names, `num_turns`, `before`, cursor
values, page sizes, cookies, headers, or response bodies.

## Canonical payload escape hatch

Callers that need the complete normalized payload for archival or forensic use can
use:

```python
payload = snapshot.to_canonical_payload()
```

The returned object is a defensive copy. It is explicitly a **canonical CWA
payload**, not a claim that ChatGPT returned the whole conversation in one raw HTTP
response.

`to_dict()` remains the stable snapshot schema and does not expose the internal
`mapping` representation.

## Existing ConversationSnapshot artifact

PR8.15 already uses the name `ConversationSnapshot` for the on-disk artifact bundle
containing context/payload files plus a manifest. That meaning remains unchanged.

PR13.5 therefore introduces `CanonicalConversationSnapshot` for the in-memory
production value object instead of overloading or silently renaming the existing
artifact type.

The artifact writer now consumes the first-class snapshot when available, so the
normal `ChatGPTWebClient` path performs one complete history read and derives both
the curated Markdown context and canonical payload backup from that same snapshot.
Legacy lightweight injected clients keep the previous fallback behavior.

## Compatibility

The historical runtime-checkable `CanonicalConversationClient` protocol remains
unchanged (`get_status`, `get_messages`, `attach_conversation`). Snapshot support is
modeled as the separate additive `CanonicalConversationSnapshotClient` production
protocol. This preserves structural `isinstance(..., CanonicalConversationClient)`
compatibility for existing custom clients while giving the new capability an
explicit contract.

`ChatGPTProductRuntime.get_conversation_snapshot()` feature-detects that additive
capability. Calling it against a legacy injected client without snapshot support
fails explicitly rather than fabricating snapshot semantics.

## Invariants

```text
wire response != canonical snapshot
num_turns != page size
pagination implementation != public contract
complete snapshot -> full canonical reader completed
snapshot.to_dict() != raw ChatGPT response
```

The change does not alter write authority, retry semantics, canonical finality,
Browser Authority, Temporary Chat identity, or generated-artifact handoff.
