# PR9.3 — Product Runtime Observation Integration

Status: **implemented; deterministic and authenticated live characterization complete for search/source/citation plus generic tool activity**.

## Runtime contract

`ChatGPTProductRuntime.send_text_observed()` derives a runtime-owned immutable structured observation set from the same standardized `on_event` stream already delivered by product transports.

`ProductRuntimeExecution` carries two additive defaulted fields:

```text
observations: tuple[StructuredProductObservation, ...] = ()
dropped_observation_event_count: int = 0
```

The defaults preserve existing transport/test constructors.

## Authority boundary

The runtime collector is observation-only. It cannot:

- submit or retry a product write;
- select a fallback transport;
- establish canonical answer finality;
- replace write observation or execution provenance;
- authorize local or external actions.

A transport cannot inject typed observation authority by pre-populating `ProductRuntimeExecution.observations`. The package-level gate replaces those fields with values derived from the standardized event stream after the existing runtime method returns.

## Callback semantics

The gate wraps `on_event` only for `send_text_observed()`:

1. the event is offered to `ProductObservationCollector`;
2. unexpected collector exceptions are contained and counted as dropped observation events;
3. the original caller callback receives the same event object afterward.

Caller callback exceptions are not swallowed by the gate; the selected transport retains its existing callback/error semantics.

`send_text()` is unchanged.

## Installation

The wrapper is installed at package import time alongside the repository's existing compatibility/safety gates. It is idempotent, so reload or repeated gate application cannot stack duplicate wrappers.

The canonical source/citation observation gate is installed around the already-existing browser-owned canonical readback path. It adds observation taps only; it does not add an extra product read, alter canonical finality, acquire retry authority or change product write ownership.

## Live evidence

### Search/source/citation

The authenticated browser-owned search gate established that the runtime receives typed `SEARCH`, `SOURCE` and `CITATION` observations on a real product turn while the response remains canonically finalized by `CANONICAL_READBACK`.

The citation was linked to an already-observed source with a valid answer range, source/citation provenance was observed before `canonical_text_finalized`, automatic write retry remained disabled, fallback transport remained `null`, no private-thought text leaked and no observation events were dropped.

This evidence is the basis for provider-aware `web_search=AVAILABLE` on the production/default browser-owned provider. Legacy providers without the proven revision-safe observation channel remain `UNKNOWN`.

### Generic tool activity

A later one-write live characterization on exact head `d448d3fc9bb65114666d93c7525c10d2018ccd8a` requested calculator use, but the current ChatGPT product emitted a real sequence involving `genui.search`, `web.run` and Python instead of an observable `calculator` operation.

The typed runtime result contained:

```text
TOOL    genui.search
SEARCH  web.run
TOOL    python
TOOL    python / execution_output
```

The arithmetic answer was correct and canonically finalized. The run used one write, had no automatic retry, no fallback transport, no private-thought text exposure and zero dropped observation events.

PR9.3 therefore treats the actual product-emitted tool identity as evidence. It does not infer a missing `calculator` operation from the prompt or answer.

## Tool lifecycle discipline

PR8.12 currently assigns different message identities to assistant tool requests and tool results. Those identities are not proven to be a shared lifecycle correlation key.

Accordingly:

- tool request/result points are represented as independent `OBSERVED` observations;
- PR9.3 does not fabricate a `STARTED -> COMPLETED` tool pair;
- same-id non-tool activity may still retain real lifecycle phases;
- explicit operation names, when present, may refine SEARCH-vs-TOOL classification but do not create lifecycle authority.

## Capability boundary

The live generic tool evidence is intentionally **not** used to promote the combined `tools_connectors` capability. Connector coverage, connector authorization/credential semantics and required-action continuation were not proven by this run, so the combined capability remains `UNKNOWN`.

## Public API boundary

Observation classes remain available from `chatgpt_web_adapter.product_observations` during PR9.3. Root-package PRIMARY_PRODUCTION promotion is deliberately deferred to PR9.4 / CWA 0.3 stabilization, where the complete next-release public surface can be reviewed and frozen together rather than expanded late in the feature PR.

## Deterministic coverage

Coverage verifies:

- backward-compatible execution defaults;
- source/citation collection from the event stream;
- transport-injected typed observations are ignored as authority;
- policy/privacy drops surface through `dropped_observation_event_count` without failing the turn;
- unexpected collector failures remain non-authoritative;
- caller callback semantics are preserved;
- runtime gate installation is idempotent and present on the primary runtime;
- uncorrelated tool events stay point observations;
- explicit operation precedence classifies search operations as SEARCH and calculator/weather/finance/sports/time as TOOL even under a coarse `web` activity kind;
- absence of an operation remains absence of evidence rather than guessed metadata.
