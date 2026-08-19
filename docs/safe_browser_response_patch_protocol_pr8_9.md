# PR8.9.2a — Product Patch-Stream Protocol Dealiasing

_Status: bounded Candidate-B parser compatibility repair after first live response-stream characterization_

_Date: 2026-08-19_

## Live evidence that motivated the repair

The first PR8.9.2 Candidate-B turn proved the transport-level observation source itself:

```text
response_status                         200
response_mime_type        text/event-stream
streamResourceContentSupported         true
bufferedByteLength                       34
dataEventCount                           53
dataByteLength                        14109
sseEventCount                            57
jsonEventCount                           56
nonJsonSseEventCount                      0
decodeErrorCount                          0
processingErrorCount                      0
assistantTextEventCount                   0
observationCount                          0
```

This is not evidence that the response stream lacks assistant text. It is evidence that the first browser-local reducer did not recognize the product stream's JSON representation.

## Existing implementation evidence

The established `ChatGPTWebClient._parse_event()` already handles this product stream as a compact patch protocol:

```text
payload.v = { ... message skeleton ... }

then either:

payload.p = "/message/content/parts/0"
payload.v = "<text delta>"

or:

payload.v = [
    {"p": "/message/content/parts/0", "v": "<text delta>"},
    {"p": "/message/metadata", "v": {...}}
]
```

The first Candidate-B reducer instead searched primarily for complete nested assistant message objects. That semantic mismatch explains the observed combination:

```text
56 valid JSON SSE events
0 decoder errors
0 processing errors
0 assistant text observations
```

without requiring a new transport hypothesis.

## Repair

`service_worker_safe_browser_response_patch_protocol_pr8_9.js` is loaded immediately after the original Candidate-B worker.

It replaces only the browser-local SSE event reducer and adds bounded diagnostics.

The repair mirrors the existing Python parser semantics:

```text
message skeleton
    -> establish assistant message id / recipient / visible content type

/message/content/parts/0 string patch
    -> append to current visible assistant text

/message/content/parts/0 list patch
    -> append each text delta in order

/message/metadata patch
    -> retain bounded finish-reason state
```

Each accumulated visible assistant state is passed through the already existing revision-safe observation recorder.

Therefore the exported observation contract remains:

```text
SNAPSHOT
DELTA
REVISION

text length
SHA-256
bounded preview
message identity
relative timing
before-network-complete evidence
```

Raw SSE bytes are still not exported.

## Added diagnostic counters

The safe result now additionally exposes:

```text
patchProtocolEventCount
patchTextDeltaCount
patchMessageSkeletonCount
patchMetadataUpdateCount
patchAssistantMessageIdObserved
```

These are structure/count metadata only.

## Boundary preservation

The repair does not add or use:

```text
Network.getResponseBody
Network.getRequestPostData
Fetch interception
request mutation
response mutation
cookies
Authorization headers
raw headers
raw body export
tab creation/activation
automatic product-write retry
```

The existing `Network.streamResourceContent` source remains unchanged.

## Decision rule

One new live Candidate-B turn is justified because the implementation under test has materially changed: the previous stream source succeeded and only the parser contract was wrong.

If the repaired run yields:

```text
patchProtocolEventCount > 0
patchTextDeltaCount > 0
observationCount > 0
firstTextObservedMs < loadingFinishedMs
preNetworkCompleteTextObserved = true
```

then Candidate B graduates as the PR8.9 low-latency observation source.

If patch events are observed but assistant text still cannot be reconstructed, do not continue broad parser guessing. Inspect the bounded counters once and either make one evidence-backed compatibility correction or move to Candidate C.

## Architecture invalidation check

No architecture boundary changes.

```text
page-owned browser write authority
+
browser response stream as provisional text observation
+
canonical plane as authoritative finality/reconciliation
```

remains the intended composition.

`Incremental Text Observation != Canonical Finality` remains mandatory.
