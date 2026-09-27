# PR16.5 — Gemini Notebook background Audio Overview generation spike

Tracking: #187

## Question

Can CWA safely own a hosted operation whose potential effect begins during one
browser mutation while the useful result is produced asynchronously and persists in
the notebook after the initiating mutation has returned?

PR16.5 deliberately starts with characterization rather than production generation.

## Baseline

The branch starts from:

```text
main = 7e4ac8fed32d6e2394baf32dfa5a592bd47492e2
```

That baseline already contains the PR16.4 source-admission safety correction: the
conservative potential-effect boundary begins before URL input/change dispatch rather
than assuming the later explicit Add click is the first durable trigger.

Existing non-chat evidence:

```text
Google Translate
text
→ bounded page transformation
→ observed result

Gemini Notebook add_url_source
existing workspace + URL
→ durable source admission
→ persisted source-row reconciliation
```

PR16.5 targets a third lifecycle:

```text
existing notebook
→ generation start
→ background hosted work
→ pending state
→ durable completed artifact
→ re-entry / reload persistence
```

No generic HostedCapabilityRuntime is justified by this spike.

## Characterization slice 1

Temporary operation:

```text
gemini_notebook_audio_overview_probe
```

Temporary Python entrypoint:

```powershell
python -m chatgpt_web_adapter.gemini_notebook_audio_overview_probe \
  --notebook "https://notebook.google.com/notebook/<id>"
```

The probe is read-only. It:

- requires one exact already-open Gemini Notebook route;
- reuses the existing Gemini Notebook Native Messaging worker and Browser Authority
  lane;
- attaches CDP only long enough to evaluate one bounded DOM snapshot;
- performs no click, input/change dispatch, navigation, fetch/XHR, or private Google
  request;
- returns no raw HTML/DOM dump and no hrefs.

### Returned evidence

The first probe intentionally has two layers.

Target controls:

- only visible controls whose bounded structural/accessibility evidence resembles
  Studio, Audio Overview, generation, listening, podcast, or equivalent Russian
  labels;
- includes tag/id/class/role, bounded aria/title/text, bounded Material icon names,
  disabled state, and at most five structural ancestors;
- capped at 30 controls.

Fallback control sample:

- at most 60 visible button / button-role controls;
- controls inside `section.source-panel` are excluded so source titles cannot leak
  through per-source aria labels;
- tag/id/class/role/aria/title/icon structure only;
- text is deliberately omitted.

Region candidates:

- at most 40 visible semantic region/container elements;
- structural metadata plus descendant button count;
- no region text.

The probe also reports only the source panel/picker presence and source-row count,
never source titles or contents.

## Unknowns

The probe must establish before any generation mutation:

- exact Studio surface owner;
- exact Audio Overview control identity;
- whether generation starts directly or through a configuration step;
- whether multiple Audio Overview artifacts may coexist;
- pending vs completed artifact structure;
- whether a stable opaque artifact ref is available;
- whether that ref/status survives ordinary re-entry or reload;
- earliest product mutation that may start hosted generation.

Until those are observed, no production `generate_audio_overview(...)` API is frozen.

## Provisional effect boundary

Known pre-effect failures may remain ordinary only while no product mutation capable of
starting generation has been dispatched.

Once the earliest click-capable or otherwise product-mutating generation action may
execute:

```text
hosted work may already have started
→ quota/work may already be consumed
→ unknown outcome requires reconciliation
→ automatic retry forbidden
```

The exact boundary is intentionally not frozen in characterization slice 1.

## Provisional finality

Candidate only:

```text
PAGE_DOM_DURABLE_BACKGROUND_ARTIFACT_COMPLETION
canonical completion proven = false
automatic retry = false
```

A spinner disappearing, Studio text changing, a button re-enabling, or a timeout is not
sufficient completion evidence.

## Next evidence step

Run the read-only probe against an owned notebook with admitted sources. Use the
returned structure to narrow the next probe around the real Studio/Audio subtree.

No generation click is authorized until the trigger path and a reconciliation-capable
artifact identity model are proven.


## Characterization result — Studio owner and Audio create control

The first live read-only probe against the owned notebook produced a clean structural
result:

```text
section.studio-panel
  → studio-panel
    → .panel-content-scrollable
      → .create-artifact-buttons-container.studio-panel-open-create
        → basic-create-artifact-button
          → [role=button]
              aria-label = localized Audio Overview label
              mat-icon = audio_spark
              mat-icon = chevron_forward
```

The important identity is structural, not the localized label:

```text
exact owner = section.studio-panel
create owner = basic-create-artifact-button
audio discriminator = mat-icon audio_spark
control = descendant [role=button]
```

The same probe observed two admitted sources and reported no write, navigation, or raw
DOM export.

The first broad fallback control sample also demonstrated that page-wide
accessibility metadata is unnecessarily broad for this experiment. Characterization
slice 2 therefore removes page-wide control sampling entirely and scopes all detailed
observation to `section.studio-panel`.

## Characterization slice 2

The temporary operation remains read-only but now returns only:

- exact Studio owner structure;
- at most 20 `basic-create-artifact-button` owners and their descendant controls;
- Audio create candidates identified by the product icon `audio_spark`;
- at most 120 visible Studio descendants whose tag/class structure mentions
  studio/artifact/audio/generate/loading/progress;
- source panel/picker presence and source-row count only.

No broad page controls, notebook-header controls, account controls, source titles, raw
text, hrefs, or raw HTML are returned.

The next question is whether the empty Studio surface already exposes a stable
artifact-list/container topology that can support later pending/completed
reconciliation. No Audio Overview control is clicked in slice 2.
