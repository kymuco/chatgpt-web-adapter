# PR9.3 — Structured Product Observations Foundation

Status: **implemented and live-characterized on the browser-owned production path**.

PR9.3 turns the existing PR8.12 user-visible activity stream into a typed product-observation surface without giving observations any write, retry, action, or finality authority.

## Typed observation contract

`product_observations.py` defines immutable observation values for:

- search activity;
- tool activity;
- general visible product activity;
- source identity;
- citation-to-source relationships;
- required-action observations.

The public runtime execution contract carries the resulting values through:

```text
ProductRuntimeExecution.observations
ProductRuntimeExecution.dropped_observation_event_count
```

`ProductObservationCollector` consumes only safe normalized event fields. It intentionally ignores assistant-text and canonical-finalization events, so product observations cannot rewrite canonical answer authority.

## Activity normalization

Existing PR8.12 activity events map from already-bounded fields:

- `activity_kind`
- `operation`
- `tool_name`
- `label`
- user-visible activity text
- `source_content_type`
- observation timing/sequence metadata

Raw tool arguments, raw tool results, response bodies, credentials, DOM/HTML and private thoughts are not copied into the typed surface.

Tool request/result messages do not currently expose a proven shared lifecycle correlation id. PR9.3 therefore represents those points as independent `OBSERVED` observations rather than fabricating a request/completion pair.

Explicit operation evidence has precedence over coarse activity kind where the product actually supplies it:

- search/open/click/find/screenshot families classify as `SEARCH`;
- calculator/weather/finance/sports/time classify as `TOOL` even if a producer reports a coarse `web` activity kind;
- missing operation names remain missing rather than being guessed from the prompt, answer or tool label.

## Source/citation boundary

The browser observation layer emits dedicated safe events:

```text
product_source_observed
product_citation_observed
product_required_action_observed
```

A citation is accepted only after its `source_id` has been observed by the same collector. Orphan or malformed structured events are dropped as observation defects; they do not fail or retry a product write.

This remains the canonical boundary:

```text
product observation defect
    != product write failure
    != canonical finality failure
    != action authority
```

## Live evidence

Authenticated browser-owned live characterization established two complementary product shapes.

### Web search/source/citation

A bounded one-write web-search gate observed:

- typed `SEARCH` activity;
- canonical `SOURCE` evidence;
- a `CITATION` linked to the observed source with a valid answer range;
- source/citation events before `canonical_text_finalized`;
- canonical completion from `CANONICAL_READBACK`;
- no automatic write retry;
- no fallback transport;
- no private-thought text export;
- zero dropped observation events.

That evidence supports provider-aware browser-owned `web_search=AVAILABLE` for the production/default provider while legacy providers without the revision-safe observation channel remain `UNKNOWN`.

### Generic product tool activity

A later one-write tool characterization on exact head `d448d3fc9bb65114666d93c7525c10d2018ccd8a` requested a calculator but the current ChatGPT product chose a different internal path:

```text
TOOL    tool_name=genui.search  operation=null
SEARCH  tool_name=web.run      operation=null
TOOL    tool_name=python       operation=null
TOOL    tool_name=python       operation=null  source_content_type=execution_output
```

The answer was correct and canonically finalized, with no retry/fallback/private-thought leakage and zero dropped observation events.

This proves generic tool observation. It does not prove caller-selectable internal tool choice and does not justify synthesizing `operation=calculator` when the product did not emit it.

## Capability discipline

`web_search` is live-graduated only for the provider path that has the proven observation channel.

`tools_connectors` remains `UNKNOWN` because the capability combines broader tool and connector semantics. The generic tool live run did not prove connector coverage, connector authorization, credential behavior or required-action continuation. Promoting the combined capability would overstate the evidence.

## Public-surface note

Observation value types remain importable from `chatgpt_web_adapter.product_observations` in PR9.3. They are intentionally not added to the root-package PRIMARY_PRODUCTION export list late in the feature PR. PR9.4 / CWA 0.3 stabilization is the appropriate point to freeze any additional root public API commitment after the full 0.3 surface is reviewed together.
