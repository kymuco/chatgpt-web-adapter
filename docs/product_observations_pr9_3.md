# PR9.3 — Structured Product Observations Foundation

Status: implementation started.

PR9.3 turns the existing PR8.12 user-visible activity stream into a typed product-observation surface without giving observations any write, retry, action, or finality authority.

## First vertical slice

The first PR9.3 slice introduces `product_observations.py` with typed immutable observations for:

- search/tool activity lifecycle;
- source identity;
- citation-to-source relationships;
- required-action observations.

`ProductObservationCollector` consumes only safe normalized fields. It intentionally ignores assistant-text and canonical-finalization events, so product observations cannot rewrite canonical answer authority.

Existing PR8.12 activity events map to typed search/tool/activity observations using their already-bounded fields:

- `activity_kind`
- `operation`
- `tool_name`
- `label`
- user-visible activity text
- `source_content_type`
- observation timing/sequence metadata

Raw tool arguments, raw tool results, response bodies, credentials, DOM/HTML and private thoughts are not copied into the typed surface.

## Source/citation boundary

The foundation defines dedicated safe event names for later browser-product emitters:

- `product_source_observed`
- `product_citation_observed`
- `product_required_action_observed`

A citation is accepted only after its `source_id` has been observed by the same collector. Orphan or malformed structured events are dropped as observation defects; they do not fail or retry a product write.

This is deliberate:

```text
product observation defect
    != product write failure
    != canonical finality failure
    != action authority
```

## Next implementation layer

The next PR9.3 slice should characterize the current ChatGPT product payloads for source/citation evidence and emit these dedicated normalized events from the browser observation layer. That work must preserve the same privacy boundary as PR8.12 and keep canonical assistant readback authoritative.
