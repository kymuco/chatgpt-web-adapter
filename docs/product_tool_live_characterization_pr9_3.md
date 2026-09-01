# PR9.3 — Live Product Tool Characterization

Status: **authenticated live characterization completed**.

## Exact live gate

The bounded live characterization was executed on exact head:

```text
d448d3fc9bb65114666d93c7525c10d2018ccd8a
```

The gate allowed exactly one ordinary ChatGPT product write and requested calculator use for a deterministic arithmetic result.

Observed result:

```text
product write budget        1
write attempts              1
write completions           1
canonical answer            9449772114049
expected answer             9449772114049
answer correct              true
canonical completion        true
completion source           CANONICAL_READBACK
automatic write retry       false
streaming write retry       false
fallback transport          null
private thought text leak   false
dropped observation events  0
```

## What the product actually did

The product did **not** emit an observable `calculator` operation despite the explicit request to use a calculator tool.

Instead, the live turn exposed this safe normalized activity shape:

```text
TOOL    tool_name=genui.search  operation=null
SEARCH  tool_name=web.run      operation=null
TOOL    tool_name=python       operation=null
TOOL    tool_name=python       operation=null  source_content_type=execution_output
```

The two Python observations are independent observation points. They are not promoted into a fabricated request/completion lifecycle pair because PR8.12 does not expose a proven shared correlation identifier between the request and result messages.

The turn also contained reasoning activity observations. Private `thoughts` text was not exported; only the safe activity marker was preserved. A later product-visible reasoning recap remained on the ordinary activity plane.

## Interpretation

This run proves the current browser-owned production path can expose real ChatGPT **tool activity** as typed PR9.3 observations while preserving canonical answer finality and the observation/authority boundary.

It does **not** prove that callers can force ChatGPT to select a particular internal product tool such as `calculator`, and PR9.3 must not infer a missing operation name from the prompt or numeric result.

The deterministic explicit-operation precedence repair remains valid for future events that actually provide an operation field:

- search/open/click/find/screenshot operations classify as `SEARCH`;
- calculator/weather/finance/sports/time operations classify as `TOOL` even when the coarse activity kind is `web`;
- absence of an operation remains absence of evidence and is not guessed.

## Capability boundary

`web_search` is separately live-graduated to `AVAILABLE` for the production/default browser-owned provider because PR9.3 has direct live SEARCH + SOURCE + CITATION evidence.

`tools_connectors` intentionally remains `UNKNOWN`.

Reason: this live turn proves generic product-tool observation (`genui.search`, `web.run`, `python`) but does not prove connector coverage, connector lifecycle semantics, credential handling, required-action continuation, or a general caller-selectable tool execution contract. The existing capability combines tools and connectors, so promoting the whole capability would overstate the evidence.

This is deliberate evidence discipline, not a missing implementation fallback.

## PR9.3 closure implication

A further authenticated write solely to coerce a `calculator` operation is not required for PR9.3 closure. The useful contract is observation of what the product actually did, not enforcement of an internal tool choice.

PR9.3 can close with:

- typed immutable search/tool/activity/source/citation/required-action observation contracts;
- runtime-owned collection from the standardized event stream;
- live browser-owned SEARCH observation;
- live canonical SOURCE and CITATION relationships;
- live generic product TOOL observation;
- deterministic explicit-operation classification for operation-bearing events;
- privacy and non-authority invariants preserved;
- `web_search=AVAILABLE` only where live evidence applies;
- `tools_connectors=UNKNOWN` until broader tool/connector evidence exists.
