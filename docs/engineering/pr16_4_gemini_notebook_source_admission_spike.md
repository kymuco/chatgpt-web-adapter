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


### First successful read-only snapshot

After correcting the observed host, the characterization passed on the same owned
notebook with:

```text
origin = https://notebook.google.com
route  = /notebook/<observed-id>
read_only = true
```

The snapshot exposed a product-owned source trigger with class
`.add-source-button`, an enclosing Sources navigation panel, and the empty-source
state. It also showed that the first broad document scan collected unrelated chat,
studio and Google-account chrome.

That breadth is not needed for the source-admission experiment. The temporary
characterizer is therefore narrowed before the next live run to:

```text
Sources panel
+ currently open dialog / overlay roots
```

It no longer serializes whole-page body text. This keeps the research probe aligned
with data minimization and makes subsequent evidence easier to interpret.

The next read-only step is human-assisted state setup:

```text
user manually opens Add sources
→ CWA performs no click
→ rerun characterize_gemini_notebook
→ inspect the already-open source-admission dialog
```

This still precedes any CWA-owned product mutation.


### Second read-only snapshot: source-type chooser

With the user manually opening **Add sources**, the same notebook exposed:

```text
route = /notebook/<observed-id>?addSource=true
read_only = true
source_panel_found = false
dialog present
```

The route query therefore carries an observable add-source UI state. The source panel
trigger is no longer a reliable owner while the modal is active; characterization must
treat the dialog/overlay as the current product surface rather than requiring the
background Sources panel to remain discoverable.

The chooser presented product-owned source actions including:

```text
Upload files
Sites
Books
Drive
Copied text
```

For the intended URL-source operation, **Sites** is the relevant next product control.
The visible textarea with placeholder equivalent to *find new sources on the internet*
belongs to search/research discovery and is not evidence for direct URL admission.

The characterization also found both the material dialog container and its parent CDK
overlay. These are one UI surface, not two independent dialogs, so the probe now
collapses containing overlay roots and records the add-source route state explicitly.

Next read-only state transition:

```text
user manually clicks Sites
→ CWA performs no click
→ rerun characterize_gemini_notebook
→ inspect direct website/URL admission controls
```


### Third read-only snapshot: direct URL admission surface

With **Sites** opened manually, the product exposed the direct website/YouTube source
state while keeping the same `?addSource=true` route.

Observed direct-URL controls:

```text
textarea
  aria-label = Enter URL
  placeholder = Paste links

button
  text = Add
  disabled while input is empty
```

The dialog explicitly states that multiple URLs may be separated by whitespace/newlines,
but PR16.4 remains intentionally narrower: the candidate public operation is one exact
web URL at a time.

The current route/query does not distinguish the chooser from the nested Sites state,
so durable implementation must not use `?addSource=true` alone as source-type identity.
It needs the product-local URL input plus commit-control structure.

Before crossing the commit boundary, one more read-only transition is required:

```text
user manually enters one valid test URL
→ user does not click Add
→ CWA reads only value presence/length and commit enabled state
→ no raw entered URL is returned by characterization
```

The probe therefore records `disabled`, `ariaDisabled`, `valuePresent` and
`valueLength` for candidate controls without serializing input values.


### First durable-admission observation

After the manual URL-entry experiment, the next characterization found the notebook
back on its ordinary route with no add-source overlay. That transition alone was
ambiguous and was not treated as success.

The visible product state then provided stronger post-commit evidence:

```text
Sources panel
  → one persisted source row ("Example Domain")

notebook state
  → source count = 1

main notebook surface
  → source-derived content present
```

The checkbox shown next to the source is not used as admission finality. The UI also
shows a **Select all** checkbox, which indicates that checked state belongs to source
selection/inclusion semantics rather than source existence.

This is the first durable source-admission observation for PR16.4. However, the exact
commit-trigger event was not observed, so the implementation must not yet assume that
the commitment boundary is specifically a click on the visible **Add** button.

Before freezing finality selectors, the temporary read-only probe now records a bounded
ancestor path around the product-owned `.add-source-button`. For each nearby container
it reports only structural metadata, a bounded text sample, and descendant checkbox /
button counts. The probe stops before broad page containers so post-admission evidence
can identify the real Sources-panel owner without returning the whole notebook DOM.

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
