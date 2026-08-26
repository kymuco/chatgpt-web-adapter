# PR9.2 — Full Product Input Expansion

Status: **implementation complete for browser-owned normal turns / live graduation pending**

PR9.2 expands `ChatGPTProductRuntime` from text-only input toward images, files,
and multimodal continuation without weakening the frozen PR9.0 browser-owned
production boundary or the PR9.1 browserless challenge boundary.

## Current architecture

```text
ChatGPTProductRuntime.send_text(..., media=[...])
        |
        v
browser-owned normal-turn preflight
        |
        v
execution-local MediaItem materialization
        |
        +-- local path -> validated absolute local path
        |
        +-- bytes -> private short-lived temp file
        |
        +-- data: URI -> decoded private short-lived temp file
        |
        +-- HTTP(S) URL -> fetched private short-lived temp file
        |
        +-- (source, filename) -> preserve requested basename
        |
        v
Native Messaging: paths only, never attachment bytes
        |
        v
PR9.2 extension overlays
        |
        +-- stale-UI recovery first
        |
        +-- durable stale-attachment fence persisted before staging
        |
        +-- one outer deadline reaches the exact protected-submit boundary
        |
        +-- no mouse -> Enter retry after mouse release is attempted
        |
        v
CDP DOM.setFileInputFiles on official ChatGPT page
        |
        v
official page owns upload + protected conversation write
        |
        v
same-turn durable fence retention
        |
        v
next prewrite: destroy fenced runtime tab + prove absence before fence retirement
        |
        v
existing PR8/PR9 browser-owned write observation
        |
        v
canonical assistant finality/readback
```

The existing proven service-worker chain is not rewritten and the packaged
extension keeps its PR8.7 `0.1.13` manifest entrypoint. After that entrypoint has
assembled the full prior worker chain and installed its own final
`executeNativeTurn` wrapper, it imports the PR9.2 rich-input overlay and then the
PR9.2 deadline/cleanup repair overlay. The rich-input path acts only on turns
carrying `attachmentPaths`; text-only turns keep the prior product semantics.

## Safety and compatibility boundary

- The reused public `MediaItem` contract is preserved, including local paths,
  bytes/bytearray, base64 `data:` URIs, HTTP(S) URLs, and `(source, filename)` tuples.
- Non-path sources are materialized before browser delegation; Native Messaging
  still carries local paths only and never serializes attachment bytes.
- `media=[]` is equivalent to text-only input.
- The official ChatGPT page remains responsible for upload behavior, challenge/proof
  handling, request construction, and the protected conversation write.
- Existing browser-owned canonical finality remains authoritative.
- No automatic retry is introduced.
- No browserless fallback is introduced.
- Browserless rich input fails before write.
- Temporary Chat rich input fails before write until separately characterized.
- Text-only custom providers retain their historical call signature. A real rich
  turn also requires exact provider attachment-count confirmation, and injected or
  subclassed browser-owned transports do not receive rich-input authority.

## Recovery, deadline, and stale-attachment fence

PR8.11 stale-UI recovery is allowed to reload the durable runtime tab before
attachment staging. PR9.2 therefore hooks staging only after that recovery boundary:
a recovery reload cannot silently erase an already-selected file.

One outer rich-turn deadline governs stale-UI recovery/reload, runtime-tab waits,
attachment staging, protected page dispatch, and cleanup. The exact mouse/Enter
protected-submit events are deadline-guarded. For the Enter fallback, successful
`keyDown` is the write boundary; the later `keyUp` is best-effort and cannot turn an
already-delegated write into a local timeout or error.

The historical page helper also used a broad mouse-submit catch that could fall back
to Enter after `mouseReleased` had already been delegated. That is unsafe because a
CDP acknowledgement can be lost even when the page received the release and sent the
conversation write. Schema 4 removes that ambiguity: Enter fallback remains allowed
only before mouse release is attempted. Once `mouseReleased` is attempted, any error
is terminal/fail-closed (`PR9_2_MOUSE_RELEASE_OUTCOME_UNCONFIRMED`) and no second
submit path is invoked.

Selecting a file mutates persistent page/composer state, so PR9.2 treats it as a
separate safety boundary. Before `DOM.setFileInputFiles` may select any file, the
runtime-tab ID is persisted to `chrome.storage.local` under the PR9.2 stale-attachment
fence. This makes the fence survive Manifest V3 service-worker suspension/restart
while the runtime tab remains alive.

Clearing only the underlying file input is **not** accepted as proof that ChatGPT's
composer/upload state is clean. After staging, the same rich turn retains the durable
fence even if the product write succeeds. Before any later write, the next prewrite
must clean the fenced state by closing the extension-managed runtime tab under the
remaining outer deadline and then separately proving that the tab is absent. Only
`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED` permits the durable fence to be removed.
Timeouts and unrecognized tab errors never count as cleanup proof.

`ensureRuntimeTab()` only reuses the stored extension-managed runtime-tab ID and
otherwise creates a new inactive runtime tab; this cleanup authority does not adopt
an arbitrary user ChatGPT tab. If destructive cleanup or fence retirement cannot be
proven, the next turn fails closed instead of risking stale attachment reuse.

The existing `storage` extension permission is reused; PR9.2 does not add browser
permissions or change the extension identity/version.

## Authenticated live gate

`product_rich_input_live_gate_pr9_2` implements the bounded graduation gate. Before
any product write it performs a zero-write extension support probe that must prove
**schema 4** and the complete current safety contract:

- staging primitive is `DOM.setFileInputFiles`;
- Native Messaging does not carry attachment bytes;
- the official page owns upload and the protected write;
- stale-UI recovery runs before attachment staging;
- the stale-attachment fence exists and survives service-worker restart;
- one total rich-turn deadline is enforced through the actual submit boundary;
- post-write cleanup is deadline-bounded and the fence remains until next prewrite;
- post-submit Enter `keyUp` cannot affect the already-submitted outcome;
- mouse-to-Enter fallback is forbidden after a mouse release attempt;
- ambiguous mouse-release outcomes fail closed instead of issuing a second submit;
- stale attachment cleanup authority is exactly
  `RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`;
- automatic write retry is disabled;
- fallback transport is absent;
- the support probe itself performed no write.

Schema 3 and earlier overlays therefore fail the current gate even if ordinary live
turns happen not to exercise the repaired edge cases.

The live phase then has an exact budget of **three** product writes using generated,
deterministic fixtures. Each response must depend on content that is absent from
the prompt, so a staged-but-silently-omitted attachment cannot produce a false
capability pass:

1. a generated PNG contains three vertical bands in `BLUE | RED | GREEN` order;
   the canonical answer must identify that exact order;
2. a general `.txt` file contains a hidden `EVIDENCE:` marker absent from the
   prompt; the canonical answer must reproduce that marker;
3. a different `.txt` file is attached as a continuation on the first durable
   conversation and contains a distinct hidden marker; the canonical answer must
   reproduce the new marker while preserving conversation identity.

Every write must also produce exactly one browser-native write event and exactly
one canonical readback event, both reporting attachment count `1`. The returned
execution must prove `CANONICAL_READBACK` finality and preserve the expected
conversation identity for the continuation.

The gate is intentionally opt-in because it performs real authenticated product
writes:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_pr9_2 \
  --acknowledge-live-writes
```

A successful command prints a JSON report with `ok: true`, `write_attempts: 3`,
`write_completions: 3`, per-turn identity/finality/attachment-dependent evidence,
and no attachment file contents.

## Capability graduation rule

Implementation presence is not live product evidence. `images`, `files`, and
`multimodal_continuation` must not be promoted to `AVAILABLE` solely because the
code and deterministic tests pass.

Graduation requires bounded authenticated browser-owned live evidence for at least:

1. one attachment-dependent image + text new-chat turn;
2. one attachment-dependent general file + text turn;
3. one attachment-dependent multimodal continuation on an existing durable conversation;
4. canonical final assistant readback after each write;
5. exact attachment-count observation with no hidden fallback or automatic retry;
6. current recovery-before-staging, schema-4 submit/deadline guarantees, and restart-safe
   destructive stale-composer cleanup proof.

Until that live gate succeeds, existing capability metadata remains conservative.
