# PR9.3 — Product Runtime Observation Integration

Status: deterministic slice staged; authenticated live source/citation characterization remains a later gate.

## Runtime contract

`ChatGPTProductRuntime.send_text_observed()` now derives a runtime-owned immutable structured observation set from the same standardized `on_event` stream already delivered by product transports.

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

The observation classes themselves are not promoted into the root primary public surface in this slice. They remain available from `chatgpt_web_adapter.product_observations` until authenticated live characterization establishes the browser-owned search/source/citation availability contract.

## Deterministic gate

Focused coverage verifies:

- backward-compatible execution defaults;
- source/citation collection from event stream;
- transport-injected typed observations are ignored as authority;
- policy/privacy drops surface through `dropped_observation_event_count` without failing the turn;
- unexpected collector failures remain non-authoritative;
- caller callback semantics are preserved;
- runtime gate installation is idempotent and present on the primary runtime.
