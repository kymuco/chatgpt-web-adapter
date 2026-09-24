# PR15.28 — Consolidate stream-metadata extraction ownership

## Purpose

Continue #107 by removing the remaining source-order ownership chain around
`extractSafeStreamMetadata`.

Before this slice, four shipping layers captured and reassigned the same hook:

```text
service_worker_instant_mode_pr8_8.js
service_worker_rich_input_schema19_repair_pr9_2.js
service_worker_rich_input_schema28_repair_pr9_2.js
service_worker_rich_input_schema29_repair_pr9_2.js
```

Given the current recursive runtime assembly, the effective historical call graph was:

```text
schema29
→ schema28
→ schema19
→ Instant
→ base
```

## New ownership

The base parser in `service_worker.js` is now private:

```text
_cwaBaseExtractSafeStreamMetadata
```

The historical owners now expose pure helpers:

```text
_pr88ExtractSafeStreamMetadataWithInstantHints(body, base64Encoded, next)
_pr92Schema19ExtractRequestBoundStreamMetadata(body, base64Encoded, next)
_pr92Schema28ExtractSafeStreamMetadata(body, base64Encoded, next)
_pr92Schema29ExtractSafeStreamMetadata(body, base64Encoded, next)
```

The sole public owner is:

```text
service_worker_stream_metadata.js
```

with explicit composition:

```text
schema29(schema28(schema19(instant(base))))
```

## Preserved semantic details

The consolidation preserves more than function order.

### Instant

The Instant layer still observes bounded model/reasoning response hints and then
delegates to the safe metadata parser. Observation failures remain non-authoritative.

### Schema 19

Schema 19 still consumes the metadata returned by the lower chain and writes only
the exact-request causal conversation / turn-exchange fields into the active
rich-input context.

### Schema 28

Schema 28 remains the base64 compatibility and request-bound stream-handoff owner.

When CDP supplies a base64 response body, schema28 still:

1. decodes the body to UTF-8 for the lower observer chain;
2. calls the lower chain for side effects such as Instant response hints;
3. ignores lower-chain identity as authority;
4. independently parses the original response representation;
5. overwrites schema19 causal context from the schema28 request-bound result.

This preserves the critical distinction:

```text
lower observer side effects
!= request-bound identity authority
```

### Schema 29

Schema29 remains the final outer identity parser. It still invokes the lower chain
for observation/compatibility side effects, then independently computes the stricter
request-bound protocol conversation-id consensus and returns only that result.

## Assembly

The new owner is loaded immediately after `service_worker_runtime_write.js`.
At that boundary:

- base exists from the root worker;
- Instant exists from the observability path loaded by runtime-tab reconciliation;
- schema19/schema28/schema29 exist from the rich-input write assembly.

No module needs to mutate the public hook during import.

## Static target

```text
extractSafeStreamMetadata public definitions = 1
extractSafeStreamMetadata runtime assignments = 0
PriorExtractSafeStreamMetadata aliases        = 0
```

## Regression strategy

Existing schema19/schema28/schema29 parser and authority tests remain in place.

PR15.28 additionally adds an executable Node composition regression proving the
outer-to-inner and reverse-unwind call order:

```text
enter schema29
→ enter schema28
→ enter schema19
→ enter Instant
→ base
→ exit Instant
→ exit schema19
→ exit schema28
→ exit schema29
```

The existing schema28 base64 observer regression continues to prove that decoded
UTF-8 is passed to the lower observer path before request-bound parsing while
lower identity remains non-authoritative.

## Acceptance

- exactly one public `extractSafeStreamMetadata` owner;
- zero runtime assignments of that hook;
- zero historical prior-function aliases;
- exact historical outer-to-inner composition preserved;
- schema28 base64 observer and request-bound authority semantics preserved;
- schema29 protocol-consensus authority preserved;
- engineering quality and JavaScript syntax green;
- full Linux/Windows Python 3.10–3.14 matrix green;
- release build and installed-wheel smoke green.
