# PR16.6 — Gemini Notebook Audio Artifact Handoff Characterization

_Status: active characterization; stacked on PR16.5._

## Purpose

PR16.5 proved a durable background Audio Overview lifecycle:

```text
generation commit
→ stable pending artifact
→ same observed artifact ref
→ stable non-pending artifact
→ ordinary reload
→ same exact ref survives
→ PAGE_DOM_DURABLE_BACKGROUND_ARTIFACT_COMPLETION
```

PR16.6 asks the next product-boundary question:

```text
Can that exact completed artifact identity own one exact acquisition/download action?
```

The first live fixture is:

```text
notebook =
https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76

observedArtifactRef =
261a5005-1c03-44d7-9aa9-ecfb5bcef8f2
```

The ref is product-observed DOM identity derived from
`artifact-labels-<ref>`. It is not claimed to be an official Google API id.

## Slice 16.6a — exact artifact row/action characterization

Temporary operation:

```text
gemini_notebook_audio_artifact_action_probe
```

Input:

```text
exact notebook route
+ expectedArtifactRef
```

The probe:

1. opens no UI;
2. clicks nothing;
3. finds the proven `artifact-library`;
4. scans visible `.artifact-item-button` rows;
5. derives each candidate ref only from `artifact-labels-<ref>`;
6. requires exactly one row whose ref equals `expectedArtifactRef`;
7. returns only bounded row-local button/control structure;
8. identifies row-local `more_vert` candidates structurally from product icons.

Returned control metadata is bounded to tag/id/class/role/aria/title/disabled/icons
plus at most four row-local ancestors.

The probe does not export raw DOM, does not inspect broad page controls, performs no
navigation, performs no download, and performs no filesystem action.

## Identity boundary

These values are **not** acquisition identity:

- artifact title;
- details text;
- filename;
- DOM row position;
- menu order;
- localized Download text.

The only admitted artifact selector in this slice is the exact PR16.5
`observedArtifactRef`.

## Next gate

Only if 16.6a proves exactly one row-scoped `more_vert` action may 16.6b open that
menu once and characterize its actions.

Opening a menu still does not authorize a Download click. The Download effect boundary
and browser acquisition correlation belong to later slices.


## Live result — exact row-scoped menu trigger

The first live PR16.6a probe matched the completed artifact by exact ref and returned
three visible row-local controls:

```text
1. artifact-stretched-button
2. play_arrow action
3. more_vert action
```

The `more_vert` control was unique and structurally owned by:

```text
exact artifact-labels-<ref> row
→ .artifact-button-content
→ .artifact-actions
→ nb-icon-button.artifact-more-button
→ button.mat-mdc-menu-trigger
→ mat-icon more_vert
```

The observed localized accessibility label is characterization evidence only and is
not identity authority.

The probe performed no product write, navigation, or download. This closes slice
16.6a.

## Slice 16.6b — open exact artifact menu once

Temporary operation:

```text
gemini_notebook_audio_artifact_menu_probe
```

The operation requires zero visible menus before mutation. It then resolves the exact
artifact row from `expectedArtifactRef`, requires exactly one visible
`button.mat-mdc-menu-trigger` under `nb-icon-button.artifact-more-button` whose
product icon is `more_vert`, and clicks that control exactly once.

This is a transient UI mutation only. It does not authorize a product write or a
download.

After the click, the operation observes only visible menu panels and at most 24 menu
items. It never activates a menu item.

Localized item text is allowed as characterization evidence but must not silently
become the future Download identity.

The next gate requires one unambiguous menu and structural evidence for a Download
action before any Download click is implemented.

## Live result — exact Download action in the artifact menu

The PR16.6b live menu probe observed one visible `mat-mdc-menu-panel` with five
enabled `button[role=menuitem]` actions. Their product-icon identities were:

```text
share
edit
save_alt
info_spark
delete
```

The Download candidate is therefore structurally unique:

```text
one visible menu
→ button.mat-mdc-menu-item[role=menuitem]
→ mat-icon save_alt
→ enabled
```

Localized menu text was not admitted as identity authority. In the live terminal the
localized text was not decoded reliably, while the product-icon identities remained
stable.

The menu trigger's post-click `aria-controls` / `aria-expanded` values were empty /
false and are explicitly rejected as menu identity/finality evidence.

No menu item was activated. No download, navigation, product write, or raw DOM export
occurred. This closes slice 16.6b.

## Slice 16.6c1 — identity-bound denied download intent

Temporary operation:

```text
gemini_notebook_audio_artifact_download_intent_probe
```

This slice tests browser acquisition correlation without materializing bytes.

```text
exact notebook + exact observedArtifactRef
→ require zero visible menus
→ Page download behavior = deny
→ arm tab-scoped debugger download observer
→ open exact row-scoped more_vert menu
→ prove exactly one enabled save_alt menuitem
→ potential download-effect boundary
→ click save_alt exactly once
→ require exactly one Page.downloadWillBegin event
→ observe bounded Page.downloadProgress states
→ restore default download behavior
```

The raw download URL is never exported. Characterization may expose only browser
`guid`, `frameId`, `suggestedFilename`, URL origin, and whether a query string was
present. Filename remains descriptive metadata, not artifact identity.

The browser is configured to deny the download before the effect boundary. Therefore
this slice does not claim acquired bytes or a filesystem artifact:

```text
downloadCompletedProven = false
filesystemArtifactProven = false
automaticRetry = false
```

If the exact Download click may have executed but event correlation cannot be proven,
the outcome is ambiguous and automatic retry remains forbidden.

No `downloads` extension permission and no private Google transport are introduced.


## PR16.6c1 correction — tab debugger cannot own download behavior

The first live c1 attempt failed before the Download click with:

```text
Cannot not access browser-level commands
```

The failure occurred at the deprecated `Page.setDownloadBehavior` command. The
extension debugger remains tab-attached, and browser-level download control is not a
supported authority surface for this integration.

The c1 design is therefore corrected rather than worked around:

```text
exact artifact ref
→ exact row-scoped more_vert
→ exact enabled save_alt action
→ arm Fetch response interception
→ potential download-effect boundary
→ one save_alt click
→ require exactly one attachment response
→ fail that response before body consumption
```

The corrected characterization uses only the already-admitted `Fetch` debugger
domain. Non-attachment paused responses are continued. The single attachment-like
response is identified by response `Content-Disposition: attachment`, recorded with
bounded metadata, and aborted with `Fetch.failRequest(..., Aborted)`.

No raw download URL is exported. No response body is read in c1. No browser Downloads
permission is added. No filesystem artifact is claimed.

This also creates a better path for c2: once response identity is proven, the same
paused authenticated response can later be read through Fetch/IO into bounded staging
without relying on the browser's Downloads folder.


## Live c1 evidence — Content-Disposition alone is not payload identity

The first corrected Fetch live run observed:

```text
resourceType = XHR
contentType = application/json; charset=utf-8
path suffix = data / batchexecute
Content-Disposition attachment = true
```

That response is control-plane traffic, not the Audio Overview media payload.
Therefore `Content-Disposition: attachment` alone is explicitly rejected as artifact
byte identity.

The next c1 characterization keeps Fetch interception active but distinguishes:

```text
known control plane:
  application/json + XHR + final path component batchexecute
  → record bounded metadata
  → continue response

payload candidate:
  audio/*
  OR application/octet-stream / binary/octet-stream
  OR non-control-plane Content-Disposition attachment
  → record bounded metadata
  → abort before body read
```

At most 16 bounded response summaries are returned. Raw URLs and bodies remain
unexported. If no payload candidate appears within the bounded observation window, the
probe returns an incomplete characterization with `automaticRetry = false` instead of
inventing byte identity.


## Private-endpoint invariant correction

The live response path ended in `batchexecute`, but production characterization must
not encode that private endpoint name as protocol knowledge.

The classifier is therefore endpoint-agnostic:

```text
JSON-like Content-Type
+ XHR resource type
+ Content-Disposition attachment
→ controlPlaneLikely
→ continue response
```

The bounded URL path suffix may still be returned as observational telemetry, but it
does not participate in classification. This preserves the existing invariant that the
Gemini Notebook worker contains no private Google `batchexecute` protocol coupling.
