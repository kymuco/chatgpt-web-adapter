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
