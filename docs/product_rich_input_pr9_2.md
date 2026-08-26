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
PR9.2 extension overlay
        |
        +-- stale-UI recovery first
        |
        +-- durable stale-attachment fence persisted before staging
        |
        v
CDP DOM.setFileInputFiles on official ChatGPT page
        |
        v
official page owns upload + protected conversation write
        |
        v
explicit file-input cleanup / durable fence retirement
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
`executeNativeTurn` wrapper, it imports `service_worker_rich_input_pr9_2.js` as one
additional outer overlay. The overlay acts only on turns carrying
`attachmentPaths`; text-only turns delegate directly to the exact prior worker
path with no attachment argument.

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
- Text-only custom providers retain their historical call signature; attachment
  kwargs are sent only for a real rich-input turn and only to a provider that
  explicitly accepts them.

## Recovery and stale-attachment fence

PR8.11 stale-UI recovery is allowed to reload the durable runtime tab before
attachment staging. PR9.2 therefore hooks staging immediately after that recovery
boundary: a recovery reload cannot silently erase an already-selected file.

Selecting a file mutates persistent page/composer state, so PR9.2 treats it as a
separate safety boundary. Before `DOM.setFileInputFiles` is allowed to select any
file, the runtime-tab ID is persisted to `chrome.storage.local` under the PR9.2
stale-attachment fence. This makes the fence survive Manifest V3 service-worker
suspension/restart while the runtime tab remains alive.

Before every later turn the overlay reads the durable fence. If one exists, it
must prove one of the following before another write can proceed:

1. the referenced tab no longer exists; or
2. the page file input was explicitly cleared with `DOM.setFileInputFiles([])`.

Only after that proof is the durable fence removed. Downstream failures use the
same cleanup path. If cleanup or durable-fence state cannot be read/proven, the
next turn fails closed instead of risking stale attachment reuse. A successful
rich write also attempts explicit cleanup; if cleanup is temporarily unavailable,
the already-canonical result is returned but the durable fence is retained so the
next turn cannot write until cleanup succeeds.

The existing `storage` extension permission is reused; PR9.2 does not add browser
permissions or change the extension identity/version.

## Authenticated live gate

`product_rich_input_live_gate_pr9_2` implements the bounded graduation gate. Before
any product write it performs a no-write extension support probe that must prove:

- PR9.2 rich-input schema `1` is loaded by the connected extension;
- the staging primitive is `DOM.setFileInputFiles`;
- Native Messaging does not carry attachment bytes;
- the official page owns upload and the protected write;
- stale-UI recovery runs before attachment staging;
- a stale-attachment failure fence is enforced;
- that fence persists across service-worker restart;
- automatic write retry is disabled;
- fallback transport is absent;
- the support probe itself performed no write.

These safety booleans are mandatory even with schema `1`; an older schema-1 overlay
that predates the recovery/fence fixes cannot pass the current live gate.

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
6. current recovery-before-staging and restart-persistent stale-attachment fencing.

Until that live gate succeeds, existing capability metadata remains conservative.
