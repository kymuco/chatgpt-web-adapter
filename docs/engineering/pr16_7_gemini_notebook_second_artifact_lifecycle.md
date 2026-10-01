# PR16.7 — second Gemini Notebook generated-artifact lifecycle

Issue: #191

PR16.6 proved the Audio Overview lifecycle through authenticated browser-owned bytes,
verified temporary staging, and staging retirement. PR16.7 tests whether those
primitives repeat for a genuinely different generated artifact type before any shared
HostedArtifactLifecycle abstraction is considered.

## Slice 16.7a — read-only Studio creation inventory

Temporary operation:

```text
gemini_notebook_studio_creation_controls_probe
```

The first slice does not assume that Video Overview currently has a particular DOM
icon or localized label.

It reads only visible `basic-create-artifact-button` owners under the exact
`section.studio-panel`, returning at most 24 bounded control descriptions:

- owner/control tag and class;
- role, aria label, title and bounded visible text;
- disabled state;
- at most 12 `mat-icon` texts.

No control is clicked. There is no navigation, product write, raw DOM export, fetch,
XHR, input mutation, or event dispatch.

Localized text is characterization evidence only. A future Video Overview create
identity must prefer a unique structural/icon signal proven by this live inventory.

The next slice is gated on the live result. No Video-specific mutation is implemented
until one exact create control is independently identified.


## Live 16.7a result — Video Overview has one exact structural create control

The read-only Studio inventory observed nine visible enabled
`basic-create-artifact-button` controls. Their primary product icons were:

```text
audio_spark
tablet
videocam
flowchart
auto_tab_group
copy
quiz
stacked_bar_chart
format_list_bulleted
```

The Video Overview control was the only visible control whose icon set contained
`videocam`; its second icon was the common `chevron_forward`.

The localized label was observed as "Видеопересказ", but localized text and DOM index
are not admitted as identity authority. The next slice uses:

```text
section.studio-panel
→ visible basic-create-artifact-button owner
→ visible role/button control
→ enabled
→ icons include videocam
→ exactly one match
```

The live inventory itself remained read-only:

```text
writePerformed = false
navigationPerformed = false
rawDomExported = false
```

This closes slice 16.7a.


## Slice 16.7b — exact Video config-surface characterization

The live 16.7a inventory authorizes one structural create identity: the unique visible
enabled Studio control whose icon set contains `videocam`.

Temporary operation:

```text
gemini_notebook_video_config_probe
```

The operation:

```text
exact notebook
→ require zero visible dialogs
→ snapshot current artifact refs
→ potential config-open effect boundary
→ click exactly one videocam create control
→ require exactly one visible dialog
→ export only bounded dialog/control metadata
→ re-read artifact refs
→ require exact pre/post equality
```

No dialog action is activated. In particular, no tonal/generate/confirm control is
clicked.

Because Video creation semantics have not yet been proven, the config-open click is
treated conservatively as an effect boundary. Any failure after that point becomes
ambiguous and automatic retry remains false.

A successful characterization may claim:

```text
configurationSurfaceObserved = true
artifactLibraryUnchanged = true
generationStartedProven = false
durableProductWriteProven = false
automaticRetry = false
```

Only the next live result may identify a generation-capable control inside the dialog.
Localized dialog text is evidence only; no generation selector is implemented in this
slice.


## Slice 16.7c — one default Video generation acceptance proof

The 16.7b live dialog proves a Video-owned configuration surface whose icon inventory
contains `subscriptions`. Its visible button set contains one enabled
`mat-tonal-button`; the localized "generate now" text is not used as identity.

Temporary operation:

```text
gemini_notebook_video_generation_probe
```

The operation leaves all Video configuration at product defaults.

Unlike the original Audio proof, the artifact library is already non-empty. Therefore
acceptance is not based on an empty-to-one transition. Instead:

```text
before artifact refs
→ open exact videocam config
→ prove one subscriptions-owned dialog
→ prove exactly one enabled mat-tonal-button
→ generation effect boundary
→ click exactly once
→ observe artifact library
→ require exactly one new stable artifact ref
```

The new row must stabilize as either pending or non-pending candidate under the same
artifact-row observation contract already proven by PR16.5/16.6.

Success proves background generation acceptance, not completion:

```text
generationCommitMayHaveExecuted = true
generationAcceptedProven = true
startEvidence = PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_ACCEPTED
canonicalCompletionProven = false
automaticRetry = false
```

Any failure after the tonal-button effect boundary is ambiguous and automatic retry
remains forbidden.

This is intentionally a one-shot live experiment because Video generation can consume
hosted-product quota. The returned artifact ref becomes the identity input for the
next re-entry/finality slice; c1 does not start a second generation.
