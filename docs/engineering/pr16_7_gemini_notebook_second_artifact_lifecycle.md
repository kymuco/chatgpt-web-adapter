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


## Live 16.7c result — exact Video generation acceptance

The one-shot Video generation proof succeeded with an already non-empty artifact
library.

Before generation:

```text
261a5005-1c03-44d7-9aa9-ecfb5bcef8f2
```

After the exact tonal-button commit:

```text
261a5005-1c03-44d7-9aa9-ecfb5bcef8f2
b2c41cbb-470f-46fb-8b39-578303b50c25
```

Exactly one new stable artifact ref was admitted:

```text
observedArtifactRef = b2c41cbb-470f-46fb-8b39-578303b50c25
artifactStatus = PENDING
artifactIcons = progress_activity
generationCommitMayHaveExecuted = true
generationAcceptedProven = true
startEvidence = PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_ACCEPTED
canonicalCompletionProven = false
automaticRetry = false
```

This closes 16.7c. The Video generation must not be repeated.

## Slice 16.7d — exact Video re-entry and durable finality

Temporary operation:

```text
gemini_notebook_video_artifact_observe_probe
```

The Audio observer was originally written for a one-row artifact library. The Video
proof now has at least two rows, so 16.7d introduces a narrower reusable internal
primitive: stabilize one exact artifact ref among any bounded set of observed rows.

The observer:

```text
exact notebook
+ exact observedArtifactRef
→ scan current artifact rows
→ require exactly one matching ref
→ stabilize only that row

if pending:
  return PENDING
  no reload
  completionProven = false

if non-pending:
  ordinary reload exact Notebook tab
  re-enter
  require the same exact ref
  require NON_PENDING_CANDIDATE
  completionProven = true
```

Pending evidence:

```text
PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_PENDING
```

Durable completion evidence:

```text
PAGE_DOM_DURABLE_BACKGROUND_VIDEO_ARTIFACT_COMPLETION
```

Observation performs no product write and never starts another generation.
`canonicalCompletionProven` remains false and `automaticRetry` remains false.


## Live 16.7d result — durable Video completion

The exact Video artifact completed and survived ordinary Notebook reload:

```text
observedArtifactRef = b2c41cbb-470f-46fb-8b39-578303b50c25
artifactStatus = COMPLETED
title = Для чего на самом деле нужен example.com
details = 1:21 · Краткое описание · 2 источника
icons = videocam / play_arrow / more_vert

completionProven = true
reloadVerified = true
finalityEvidence = PAGE_DOM_DURABLE_BACKGROUND_VIDEO_ARTIFACT_COMPLETION
writePerformed = false
navigationPerformed = true
automaticRetry = false
```

This closes 16.7d and proves that the second artifact type reaches the same durable
re-entry/finality boundary as Audio while coexisting with another artifact row.

## Slice 16.7e — exact Video artifact menu characterization

The completed Video row exposes `more_vert`, but PR16.7 must not assume that its
artifact-local actions are identical to Audio.

Temporary operation:

```text
gemini_notebook_video_artifact_menu_probe
```

This slice reuses the already-proven exact-ref row/menu primitives:

```text
exact completed Video ref
→ stabilize exact row among multiple artifacts
→ click exact row-local more_vert
→ read exactly one visible menu
→ identify structural save_alt candidates
→ STOP
```

No menu item is activated. In particular, Download is not clicked.

A unique Download candidate requires:

```text
button
+ role=menuitem
+ mat-mdc-menu-item
+ enabled
+ mat-icon save_alt
```

Localized menu text is characterization evidence only.

The slice remains non-durable:

```text
productWritePerformed = false
navigationPerformed = false
downloadPerformed = false
rawDomExported = false
```

Only a live unique `save_alt` result may authorize a later Video download/byte proof.


## Live 16.7e result — Video repeats the exact artifact-local Download action

The completed Video artifact menu contained five enabled actions:

```text
share
edit
save_alt
info_spark
delete
```

Exactly one item satisfied the structural Download identity:

```text
button
+ role=menuitem
+ mat-mdc-menu-item
+ enabled
+ icon save_alt
```

The localized text was observed as "Скачать" but is not used as identity authority.

The characterization returned:

```text
downloadCandidateCount = 1
downloadActionStructurallyProven = true
downloadPerformed = false
productWritePerformed = false
navigationPerformed = false
```

This closes 16.7e and proves that Audio and Video share the same artifact-local menu
and structural Download-action primitive.

## Slice 16.7f — Video Download handoff characterization

Temporary operation:

```text
gemini_notebook_video_artifact_download_intent_probe
```

The slice asks whether Video also repeats the browser handoff primitive proven for
Audio, without assuming a transport, origin, or media MIME type in advance.

It requires the exact Video ref to remain completed, opens the exact row-local menu,
requires the unique structural `save_alt` item, installs the existing bounded
browser-sink probe plus response-stage Fetch observation, then crosses the Download
effect boundary and clicks exactly once.

Direct response payload candidates are Video-specific:

```text
video/*
or application/octet-stream
or binary/octet-stream
or a non-control-plane attachment
```

JSON/XHR attachment-like control traffic is continued and recorded only as bounded
metadata. The implementation contains no private endpoint name.

In parallel, page-facing handoff sinks remain suppressed and sanitized:

```text
anchor
form
window.open
URL.createObjectURL
```

No response body is read, no filesystem artifact is created, raw locator URLs are not
exported, and automatic retry remains false after the Download effect boundary.

A live result determines whether Video repeats the Audio `window.open` /
Googleusercontent handoff or uses a different browser transport.


## Live 16.7f result — Video repeats the product-created browser locator

The exact completed Video Download action produced one suppressed page-facing sink:

```text
kind = window_open
target = _blank
scheme = https
origin = https://lh3.googleusercontent.com
query present = true
path class = notebooklm/...
```

The direct Notebook-tab response observer saw no Video payload response. The raw signed
locator was not exported, no filesystem artifact was created, and the product-created
`window.open` was suppressed.

This closes 16.7f and independently reproduces the Audio retrieval handoff:

```text
exact durable artifact ref
→ exact row-local save_alt
→ product-created Googleusercontent browser locator
```

## Slice 16.7g — authenticated Video bytes and verified temporary staging

The byte proof now tests whether the second artifact type also repeats the lower
browser-owned retrieval primitive:

```text
exact completed Video ref
→ exact save_alt
→ unique product-created Googleusercontent locator
→ authenticated Network.loadNetworkResource
→ video/* or application/octet-stream
→ IO.read
→ SHA-256
→ chunked native transfer
→ temporary staging
→ second size/hash verification
→ staging deletion
```

The existing internal network loader is generalized only by media family:
`audio` remains bound to `audio/*`, while Video is bound to `video/*`; both allow
opaque octet-stream responses.

The characterization remains bounded to 64 MiB. No raw signed URL or private protocol
body is exported. No final caller destination is written and automatic retry remains
false after the Download effect boundary.


## Live 16.7g result — authenticated Video bytes and verified temporary staging

The exact completed Video artifact repeated the full Audio byte-retrieval path.

Observed identity:

```text
observedArtifactRef =
b2c41cbb-470f-46fb-8b39-578303b50c25
```

Authenticated browser-owned retrieval:

```text
locatorOriginClass = GOOGLEUSERCONTENT
HTTP status = 200
Content-Type = application/octet-stream
mediaFamily = video
```

Verified payload evidence:

```text
sizeBytes = 11,204,155
SHA-256 =
c3a35f6f1457aa3d31745f1ccadabfd2b52e49667b585d64d53d99d7cd6b6595
chunkCount = 25
```

Browser-side proof:

```text
browserBytesProven = true
networkResourceLoadProven = true
authenticatedBrowserRequestProven = true
acquisitionTabCreated = false
```

Python-side staging proof:

```text
stagingMaterializedProven = true
stagingIntegrityVerified = true
stagingDeleted = true
```

Negative authority boundaries remained intact:

```text
rawDownloadUrlExported = false
privateProtocolBodyRead = false
finalDestinationWritten = false
automaticRetry = false
```

This closes 16.7g.

## PR16.7 closure — second complete generated-artifact lifecycle

Audio and Video have now independently proven the same bounded lifecycle:

```text
structural create identity
→ bounded configuration surface
→ one generation effect boundary
→ background hosted acceptance
→ stable artifact identity
→ pending/re-entry
→ durable completion after reload
→ exact row-local Download action
→ product-created Googleusercontent locator
→ authenticated browser-owned bytes
→ SHA-256
→ verified temporary staging
→ staging retirement
```

The repeated primitives are now evidence-backed rather than hypothetical.

The strongest candidates for a small **internal** extraction are:

```text
exact-ref artifact observation among multiple rows
row-local more_vert + save_alt action identity
product-created window.open locator capture
authenticated Network.loadNetworkResource byte retrieval
chunked native transfer + temporary staging integrity
```

This evidence still does **not** justify:

```text
public HostedArtifactLifecycle
public artifact registry/factory
universal generated-artifact schema
generic hosted-capability runtime
caller filesystem publication authority
```

Those abstractions remain deferred until further product/capability diversity proves
that their semantics are stable beyond the current Gemini Notebook generated-artifact
family.


## Closure — independent Video proof retained privately

PR16.7 closes as a second independent generated-artifact proof, not as a new public
Video API.

The live work proved:

```text
structural Video create identity
→ bounded default generation commit
→ exactly one new stable artifact ref
→ pending / re-entry
→ reload-verified same-ref completion
→ exact artifact-local save_alt
→ product-created Googleusercontent locator
→ authenticated browser-owned byte retrieval
→ video media-family admission
→ SHA-256 verified temporary staging
→ staging retirement
```

Closure removes the temporary Studio inventory, config, menu, download-intent, and
public-looking probe modules from the package surface.

Only three private primitives remain:

```text
_gemini_notebook_video_generation
_gemini_notebook_video_artifact_observation
_gemini_notebook_video_artifact_retrieval
```

They are intentionally not exported from the root package and have no CLI entrypoints.

This PR does **not** claim:

- a supported public `generate_video_overview(...)` API;
- caller filesystem publication authority;
- a public HostedArtifactLifecycle;
- a generated-artifact registry/factory;
- a universal artifact schema.

The purpose of the retained implementation is evidence: Audio and Video now
independently demonstrate which lifecycle and retrieval primitives truly repeat.
PR16.8 may consolidate only those repeated internals.
