# PR8.9.3 — Production Revision-Safe Text Observation Delivery

## Decision

PR8.9 Candidate B is the production source for early assistant text.

The live PR8.9.2a specimen proved:

- `Network.streamResourceContent` supported;
- `text/event-stream` response;
- 49 assistant-text observations (1 snapshot + 48 deltas);
- first text at 11.311 s;
- network completion at 23.618 s;
- 12.307 s first-text lead;
- zero decode/processing errors;
- final browser text length/hash exactly matched canonical final text;
- reconciliation `EXACT_MATCH`.

Candidate A is closed as non-incremental. Candidate C rendered-page observation is not needed.

## Production contract

One product turn keeps one request id, one loopback socket, one browser-owned write,
and one Browser Authority lease. The bridge may emit zero or more `turn_event`
frames before the final `turn_result` frame.

Revision-safe event types:

- `assistant_text_snapshot` — full provisional text establishing a baseline;
- `assistant_text_delta` — append-only suffix relative to the previous observation;
- `assistant_text_revision` — full replacement provisional text;
- `canonical_text_finalized` — canonical read-plane authority plus reconciliation.

The extension exports only reduced assistant text and bounded metadata. It does not
export raw SSE, headers, request bodies, cookies, credentials, or protection state.

## Reconciliation

Final canonical text is authoritative. The runtime classifies the provisional stream:

- `EXACT_MATCH`
- `CANONICAL_EXTENDS_STREAM`
- `STREAM_REVISED_BY_CANONICAL`
- `STREAM_INCOMPLETE`
- `UNAVAILABLE`

A sequence gap marks delivery incomplete but never retries or mutates the product turn.

## Legacy token callback

`on_token` remains final-only in PR8.9.3. It is append-only and cannot retract text
if the product emits a revision. Revision-safe low-latency consumers must use
`on_event`.

## Failure semantics

Streaming observation is not write authority. User callback exceptions are isolated
from the write/finality path and never trigger an automatic retry. A lost bridge after
delegation remains a write-outcome problem; event delivery cannot authorize replay.

## Capability graduation

The `STREAMING` capability remains unchanged until one production live gate proves
that `assistant_text_*` events reach Python before `browser_native_write_completed`
and canonical finalization reconciles successfully. After that gate it can graduate
with direct PR8.9 evidence.
