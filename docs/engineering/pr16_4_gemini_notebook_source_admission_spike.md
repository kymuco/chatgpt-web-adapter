# PR16.4 — Gemini Notebook consumer source-admission spike

Status: active characterization-first experiment.

## Question

Can CWA reuse its lower browser bridge / authority / ambiguity machinery for a
persistent hosted research workspace whose operation is not a chat turn and whose
result is durable product state?

Target first operation:

```text
existing owned consumer Gemini Notebook
+ exact web URL source
→ durable source admission
```

This experiment targets the ordinary consumer Gemini Notebook web product, not Gemini
Notebook Enterprise.

## Why this is a new capability class

Google Translate proved:

```text
bounded text input
→ hosted transformation
→ bounded text result
```

Gemini Notebook source admission adds persistent workspace semantics:

```text
notebook identity
+ source identity
→ durable product mutation
→ admitted source state
```

The first useful architectural questions are therefore notebook identity, source
identity, commitment boundary, durable admission finality, and post-commit
reconciliation.

## Official API relationship

Gemini Notebook Enterprise has preview APIs for notebook and source management.

PR16.4 does not attempt to replace or mimic those APIs.

The CWA experiment is about the ordinary consumer product/session used by an
individual user in the browser. Any public CWA surface must keep that distinction
explicit.

## Product evidence before implementation

Current official product documentation establishes that:

- NotebookLM was renamed Gemini Notebook;
- existing notebooks remain available through the standalone product;
- web URLs are a supported source type;
- adding a source creates notebook state used for later grounded responses;
- notebook/source changes can sync across Gemini and Gemini Notebook surfaces.

Those facts justify a bounded consumer-product source-admission experiment but do not
tell us the current DOM, route identity, or finality markers.

## First slice

Candidate public shape, not yet implemented:

```python
GeminiNotebookWebCapability.add_url_source(
    notebook=...,
    source_url=...,
)
```

The operation must not be promoted until live evidence establishes stable enough
identity and finality.

## Characterization-first protocol

Before any source write, PR16.4 adds a temporary read-only characterization operation.

It must:

- inspect exactly one already-open Gemini Notebook tab;
- never create or navigate a tab;
- never click;
- never mutate an input;
- never call a private Google endpoint;
- return only bounded DOM metadata needed to identify notebook route, Sources panel,
  Add sources control, dialogs, and existing source presentation.

Supported product origins for characterization are intentionally limited to the
currently documented/current standalone hosts:

```text
https://notebook.google.com/*
https://notebooklm.google.com/*
```

If zero or multiple matching tabs are open, characterization fails closed.

### First live characterization finding

The initial branch guessed `https://notebook.google/*` as the renamed consumer host.
The first real owned notebook instead exposed the route as
`https://notebook.google.com/notebook/...` and the characterization correctly failed
closed with `GEMINI_NOTEBOOK_CHARACTERIZATION_TAB_MISSING` before any mutation.

The allowlist was therefore corrected to the exact observed consumer origin
`https://notebook.google.com`, while retaining `https://notebooklm.google.com` as the
legacy/alternate standalone origin. This is characterization evidence, not a reason
to widen the product boundary further.

## Expected durable contract

The intended operation is:

```text
notebook route identity proven
→ source URL validated locally
→ open Add sources UI
→ choose URL/web source path
→ authoritative source submit may execute
→ observe durable source admission in the same notebook
```

## Commitment boundary

Before the source-accepting product action executes:

```text
ordinary failure may be safe
```

Once the source-add action may have executed:

```text
outcome may be durable
→ unknown outcome requires reconciliation
→ no automatic replay
```

A timeout or debugger/bridge failure after that boundary must never silently resubmit
the source.

## Finality

The spike must not claim canonical completion merely because a modal closes.

Candidate finality class:

```text
PAGE_DOM_DURABLE_SOURCE_ADMISSION
```

This name is provisional until characterization proves what observable state actually
persists.

A successful result needs evidence that:

- the same notebook route still owns the operation;
- one intended source has been admitted;
- the admitted source can be identified without relying only on DOM position or a
  guessed title;
- transient processing UI is not confused with durable admission.

## Non-goals

PR16.4 does not add:

- generic HostedCapabilityRuntime;
- notebook creation;
- source deletion;
- file upload;
- Drive source import;
- chat over notebook sources;
- Audio/Video Overview generation;
- Deep Research;
- MCP;
- private batchexecute reproduction;
- direct Enterprise API support;
- HDE integration.

## Acceptance sequence

```text
1. read-only DOM/route characterization
2. freeze exact smallest source-admission mechanics
3. deterministic failure/ambiguity regressions
4. one bounded live URL-source admission
5. preserve evidence
6. remove temporary characterization/live tooling
7. exact-head full CI
```

Shared core changes are forbidden unless the product evidence demonstrates a
requirement that cannot remain product-local.
