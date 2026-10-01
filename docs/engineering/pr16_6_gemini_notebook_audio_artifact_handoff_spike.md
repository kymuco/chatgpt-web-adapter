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


## Live c1 result — no media response in the original tab target

A 15-second live observation after the exact `save_alt` click produced only:

```text
JSON XHR attachment-like control-plane response
play.google.com telemetry Ping/XHR
```

No `audio/*`, octet-stream, or other non-control-plane attachment response appeared
in the original tab target.

The project therefore does not read the JSON control-plane body to discover a private
download URL. Instead, c1 now also instruments the page-facing browser sinks used by a
product after its control-plane RPC:

- anchor click;
- form submit;
- `window.open`;
- `URL.createObjectURL`.

The hooks are temporary and restored in `finally`. Anchor and form events are
prevented, and `window.open` returns null, so a detected page-facing handoff is
characterized before browser acquisition. Returned URL metadata is sanitized to
scheme/origin/query-presence/path suffix; raw URLs are never exported.

Fetch response characterization remains armed in parallel, so a direct media response
in the original target is still blocked before body read.


## Live c1 closure — product-created Googleusercontent locator

The page-facing sink characterization observed exactly one suppressed sink:

```text
kind = window_open
target = _blank
scheme = https
origin = https://lh3.googleusercontent.com
query present = true
```

The raw signed URL was not exported. The hook returned `null`, so the product-created
`window.open` did not create a browser tab or download.

This closes c1 with the following evidence:

```text
exact observedArtifactRef
→ exact row-scoped more_vert
→ exact enabled save_alt
→ product control-plane activity
→ one product-created window.open locator
→ googleusercontent origin class
```

The locator is browser/product output, not a URL reverse-engineered from private Google
RPC data.

## Slice 16.6c2 — bounded byte acquisition and temporary staging proof

Temporary operation:

```text
gemini_notebook_audio_artifact_byte_probe
```

The operation repeats the proven exact-artifact Download lane, but keeps the raw
`window.open` locator only inside the page/extension boundary. The public sink-read
surface remains sanitized.

The internal locator policy requires:

```text
https
+ no username/password
+ no fragment
+ standard TLS port
+ googleusercontent.com or a subdomain
```

The worker then creates one CWA-owned inactive `about:blank` tab, attaches the
existing debugger authority, enables Fetch at response stage, and navigates the owned
tab to the exact product-created locator.

The exact locator response must be 2xx and prove an Audio-compatible response type:

```text
audio/*
or application/octet-stream
or binary/octet-stream
```

Bytes are consumed through:

```text
Fetch.takeResponseBodyAsStream
→ IO.read
→ bounded Uint8Array
→ SHA-256
→ existing Native Messaging chunk pattern
```

The characterization limit is 64 MiB. No arbitrary locator is accepted and no private
Google protocol body is read.

Python receives ordered chunk frames over the existing broker socket, writes them only
to a temporary staging file, computes SHA-256 while writing, fsyncs the staging file,
re-reads it, and requires the same size and digest as the browser manifest.

The staging path is never returned. On success it is deleted before the operation
returns:

```text
browserBytesProven = true
stagingMaterializedProven = true
stagingIntegrityVerified = true
stagingDeleted = true
finalDestinationWritten = false
automaticRetry = false
```

The CWA-owned acquisition tab must also be confirmed absent before success.

This slice deliberately stops before caller destination authority, overwrite policy,
and atomic final publish. Those remain separate from browser/product retrieval.


## PR16.6c2 correction — avoid browser download navigation entirely

The first c2 live attempt repeatedly timed out while a CWA-owned `about:blank` tab
remained loading. The Notebook tab itself was already open and healthy.

The failed design navigated the owned tab to the signed Googleusercontent locator and
then waited for a response-stage Fetch pause. That assumes a download locator behaves
like an ordinary page navigation. The live behavior showed that assumption is not
reliable.

c2 now uses the browser network loader directly on the already-authorized Notebook
debugger target:

```text
product-created signed locator
→ Page.getFrameTree
→ Network.loadNetworkResource
   disableCache = true
   includeCredentials = false
→ resource stream
→ IO.read
→ bounded bytes
→ SHA-256
```

No acquisition tab is created and `Page.navigate` is not used. The signed locator
remains internal to the page/extension boundary and is still restricted to HTTPS
Googleusercontent origin class.

This keeps the operation in browser-owned network semantics while avoiding Chrome's
special download-navigation behavior entirely.


## Live c2 evidence — authenticated locator context is required

The first `Network.loadNetworkResource` live attempt returned immediately with:

```text
net::ERR_HTTP_RESPONSE_CODE_FAILURE
```

and the browser also exposed a late product-side Google media/download URL that
returned HTTP 403 when opened outside the original handoff context.

Two assumptions in the first c2 implementation were therefore rejected:

1. the product-created locator is not safely retrievable with
   `includeCredentials = false`;
2. restoring the temporary `window.open` hook immediately after the first locator
   event is too early, because the product can perform later asynchronous handoff work.

The corrected c2 keeps the sink hook installed until the operation's `finally`
cleanup and uses:

```text
Network.loadNetworkResource
  includeCredentials = true
  disableCache = true
```

The request still uses only the exact product-created locator and browser-owned
credentials. No cookies, auth headers, signed URL, or private RPC body are exported to
Python.

Keeping the hook live through retrieval also ensures that any late product
`window.open` call remains suppressed rather than creating an uncontrolled browser
tab.


## Live c2 success — authenticated browser bytes and verified temporary staging

The authenticated c2 live proof succeeded for the already-proven Audio Overview
artifact:

```text
observedArtifactRef =
261a5005-1c03-44d7-9aa9-ecfb5bcef8f2

locatorOriginClass = GOOGLEUSERCONTENT
HTTP status = 200
Content-Type = application/octet-stream

sizeBytes = 34,882,933
SHA-256 =
9cef3aed24cff1322e6c46bed6bb968ab4a30cfc284fc9582c07d9c8294da87c

chunkCount = 78
```

The browser-side retrieval proof returned:

```text
browserBytesProven = true
networkResourceLoadProven = true
authenticatedBrowserRequestProven = true
acquisitionTabCreated = false
```

The Python-side staging proof returned:

```text
stagingMaterializedProven = true
stagingIntegrityVerified = true
stagingDeleted = true
```

The negative authority boundaries also remained intact:

```text
rawDownloadUrlExported = false
privateProtocolBodyRead = false
finalDestinationWritten = false
automaticRetry = false
```

This closes PR16.6c2. The retrieval half is now proven end to end:

```text
exact completed artifact identity
→ exact row-scoped Download action
→ product-created browser locator
→ authenticated browser-owned resource load
→ bounded bytes
→ SHA-256 identity
→ chunked native transfer
→ verified temporary staging
→ staging retirement
```

Caller-owned destination authority, overwrite policy, atomic final publish, and durable
local handoff remain deliberately outside this characterization slice.
