# PR9.3 — Product Source and Citation Observation Layer

Status: **implemented, deterministically covered and authenticated-live characterized**.

## Evidence basis

The browser overlay is based on two inputs:

1. the already-proven PR8.12 streamed message observer in CWA; and
2. current independently maintained public ChatGPT conversation-schema evidence inspected during PR9.3.

The implementation recognizes modern and legacy source/citation surfaces including:

- `message.metadata.content_references`
- `message.metadata.citations`
- `message.metadata._cite_metadata.metadata_list`
- `content_type=tether_quote`

Observed modern `content_references` shapes include `webpage`, `grouped_webpages`, `sources_footnote`, `nav_list` and related types with `start_idx` / `end_idx`, plus source containers such as `items`, `sources`, `fallback_items`, `safe_urls`, and nested `supporting_websites`.

The implementation does not claim every future ChatGPT reference shape is covered. Unknown or malformed shapes are observationally ignored rather than promoted by guesswork.

## Normalized events

The extension emits only bounded safe source/citation event types:

```text
product_source_observed
product_citation_observed
```

A source contains bounded product-visible provenance only:

```text
source_id
url
name/title
hostname/domain
attribution
source_origin
```

A citation contains an explicit relationship to a previously emitted source:

```text
citation_id
source_id
citation_index
start_index
end_index
reference_type
display_text
```

The Python collector preserves these fields as immutable `ProductSourceObservation` and `ProductCitationObservation` values.

## Relationship semantics

- Modern inline `content_references` emit source observations and citation→source relationships.
- A grouped reference can relate the same answer range to more than one source, including explicit `supporting_websites`.
- `sources_footnote` emits sources but does **not** fabricate an inline citation relationship.
- Legacy `metadata.citations` are normalized with their `start_ix` / `end_ix` range.
- `_cite_metadata.metadata_list` is source evidence only because it does not itself provide a trustworthy inline range relation.
- `tether_quote` is source evidence only.
- Repeated stream patches are deduplicated by turn-local source identity and citation relation identity.
- A source id is pinned to its first accepted sanitized URL; conflicting reuse is dropped instead of making later citation relations ambiguous.

## URL/privacy boundary

Only `http` / `https` source URLs are accepted.

The worker and Python collector apply defense-in-depth filtering:

- explicit username/password URL userinfo is rejected;
- common credential-bearing query keys are rejected, including signed URL families such as `X-Amz-*` and `X-Goog-*`;
- URL fragments are removed before source emission;
- raw evidence text, quote bodies and matched citation markers are not exported.

The overlay never exports:

- source evidence text or quote bodies;
- raw tool arguments or tool results;
- `matched_text` citation markers;
- raw message metadata;
- private `thoughts` content;
- response bodies;
- request bodies or headers;
- cookies or credentials;
- DOM/HTML.

Observation remains a separate non-authority plane:

```text
source/citation observation defect
    != product write failure
    != automatic retry authority
    != canonical answer finality
    != local/external action authority
```

## Citation range discipline

A citation is emitted only after a complete non-negative `start <= end` range exists.

An incomplete streaming reference may emit source evidence only. If a later patch supplies a valid range, exactly one citation relationship is emitted. Reversed or malformed ranges are ignored by the worker and fail closed again at the Python collector boundary.

An accepted typed citation must reference a source already observed by the same collector.

## Deterministic gate

Coverage includes:

- worker load ordering after the immutable PR9.2 schema-29 chain;
- modern grouped `content_references`;
- `sources_footnote` source-only semantics;
- nested `supporting_websites`;
- legacy citations and `_cite_metadata`;
- `tether_quote` source-only semantics;
- hidden-message exclusion;
- credential-bearing URL rejection;
- fragment stripping;
- incomplete→complete streaming citation evolution;
- repeated complete-patch deduplication;
- reversed/malformed ranges;
- typed collector preservation of source/citation relationships;
- source-id conflicting-URL rejection;
- absence of raw source/evidence text from emitted events.

## Authenticated live characterization

A bounded one-write browser-owned web-search gate on PR9.3 observed all of the evidence required for the source/citation vertical slice:

- typed `SEARCH` activity;
- at least one canonical `SOURCE` observation;
- a `CITATION` linked to the observed source;
- a valid citation answer range;
- source and citation evidence before `canonical_text_finalized`;
- canonical assistant completion from `CANONICAL_READBACK`;
- one write attempt and one write completion;
- no automatic write retry;
- no fallback transport;
- no private-thought text export;
- zero dropped observation events.

This is the evidence used for provider-aware browser-owned `web_search=AVAILABLE` on the production/default provider. A legacy provider without the revision-safe observation channel does not inherit this proof and remains `UNKNOWN`.

## Closure

The source/citation slice no longer has a pending authenticated-live gate. Further PR9.3 work is limited to overall milestone closure/review/documentation; new source schemas discovered later should be treated as product-drift follow-up rather than silently broadened by inference.
