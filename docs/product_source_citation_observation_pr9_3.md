# PR9.3 — Product Source and Citation Observation Layer

Status: **second vertical slice implemented; deterministic closure pending CI/review; authenticated live characterization not yet run**

## Evidence basis

The browser overlay is based on two inputs:

1. the already-proven PR8.12 streamed message observer in CWA; and
2. a current public ChatGPT conversation schema independently maintained by `pionxzh/chatgpt-exporter`, inspected at commit `d0f44aae9d5650852b2979bbf830590b41f7b804` dated 2026-08-28.

That current schema describes both modern and legacy source/citation surfaces:

- `message.metadata.content_references`
- `message.metadata.citations`
- `message.metadata._cite_metadata.metadata_list`
- `content_type=tether_quote`

Observed modern `content_references` shapes include `webpage`, `grouped_webpages`, `sources_footnote`, `nav_list` and related types with `start_idx` / `end_idx`, plus source containers such as `items`, `sources`, `fallback_items`, `safe_urls`, and nested `supporting_websites`.

The implementation does not claim every future ChatGPT reference shape is covered. Unknown or malformed shapes are observationally ignored rather than promoted by guesswork.

## Normalized events

The extension now emits only two new safe event types:

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

A citation contains the explicit relationship to a previously emitted source:

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

## Privacy and authority boundary

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

Only `http` / `https` source URLs are accepted. URLs containing explicit username/password userinfo are rejected instead of exported.

Observation remains a separate non-authority plane:

```text
source/citation observation defect
    != product write failure
    != automatic retry authority
    != canonical answer finality
    != local/external action authority
```

Malformed citation ranges are dropped by the collector. An accepted citation must reference a source already observed by the same collector.

## Deterministic gate

The focused second-slice suite covers:

- worker load ordering after the immutable PR9.2 schema-29 chain;
- modern grouped `content_references`;
- `sources_footnote` source-only semantics;
- nested `supporting_websites`;
- legacy citations and `_cite_metadata`;
- `tether_quote` source-only semantics;
- hidden-message exclusion;
- credential-bearing URL rejection;
- repeated stream-patch deduplication;
- typed collector preservation of source/citation relationships;
- fail-closed malformed citation ranges;
- absence of raw source/evidence text from emitted events.

Focused local result before commit: **8/8 PASS**.

## Next slice

The next step is to integrate `ProductObservationCollector` into `ChatGPTProductRuntime.send_text_observed()` so callers receive the typed turn observation set alongside the canonical response and existing write observation, without changing answer finality or transport authority. After that integration is deterministic, run one bounded authenticated web-search turn to verify current live source/citation shapes before claiming browser-owned availability.
