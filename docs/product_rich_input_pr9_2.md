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
        +-- DOM.setFileInputFiles on the official page
        |
        +-- stable page-owned composer attachment evidence
        |
        +-- immediate pre-submit attachment revalidation
        |
        +-- page-side deadline-guarded Send click
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
assembled the full prior worker chain, it imports the PR9.2 rich-input overlay,
the deadline/cleanup repair overlay, and finally the schema-5 closure overlay.
The closure overlay acts only while a rich-input context is active; text-only turns
continue through the historical product path.

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
  turn requires the known browser-owned implementation and exact attachment-count
  confirmation; injected or subclassed browser-owned transports do not receive
  rich-input authority.

## Recovery, deadline, submit, and stale-attachment fence

PR8.11 stale-UI recovery may reload the durable runtime tab before attachment
staging. PR9.2 therefore stages only after that recovery boundary so an authorized
reload cannot silently erase an already-selected file.

One outer rich-turn deadline governs stale-UI recovery/reload, runtime-tab waits,
attachment staging, protected page dispatch, and cleanup. Earlier repair layers
closed Enter and mouse-to-Enter retry ambiguities, but a fresh closure review found
that raw CDP `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent` commands are not
cancellable once dispatched. Racing such a command against a local timer can report
timeout while Chrome executes the queued protected input later.

Schema 5 removes raw CDP Input from rich-turn submit authority. The final closure
layer locates the ready Send control but performs the protected action through a
`Runtime.evaluate` expression whose **page-side `Date.now()` check** rejects execution
after a deadline reserved inside the outer RPC deadline. Raw mouse submit and Enter
fallback explicitly fail closed while a rich-input context is active. Therefore a
CDP command delivered late cannot become a protected write after its page deadline.
Text-only turns keep the historical submit path.

Selecting a file mutates persistent page/composer state, so PR9.2 treats it as a
separate safety boundary. Before `DOM.setFileInputFiles` may select any file, the
runtime-tab ID is persisted to `chrome.storage.local` under the PR9.2 stale-attachment
fence. This makes the fence survive Manifest V3 service-worker suspension/restart
while the runtime tab remains alive.

`DOM.setFileInputFiles` path count is **not** accepted as proof that ChatGPT ingested
the attachments. Schema 5 waits for stable page-owned composer evidence matching
every expected attachment basename. Rejection/error state fails the turn, evidence
must remain stable across multiple polls, and the same page-owned evidence is
revalidated immediately before the protected Send click. `attachmentCount` is only
returned after that page-owned evidence succeeds.

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
**schema 5** and the complete current safety contract:

- staging primitive is `DOM.setFileInputFiles`;
- Native Messaging does not carry attachment bytes;
- the official page owns upload and the protected write;
- stale-UI recovery runs before attachment staging;
- the stale-attachment fence exists and survives service-worker restart;
- one total rich-turn deadline is enforced through the actual submit boundary;
- post-write cleanup is deadline-bounded and the fence remains until next prewrite;
- historical Enter/mouse retry ambiguity remains closed;
- attachment count is derived from `PAGE_OWNED_COMPOSER_ATTACHMENT_STATE`, not requested paths;
- page-owned attachment evidence is stable across at least two polls;
- page-owned attachment evidence is revalidated immediately before submit;
- rich turns disable raw CDP Input submit and Enter fallback;
- protected rich submit uses `PAGE_DEADLINE_GUARDED_SEND_BUTTON_CLICK`;
- late protected-submit execution is blocked by the page-side deadline check;
- stale attachment cleanup authority is exactly
  `RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`;
- automatic write retry is disabled;
- fallback transport is absent;
- the support probe itself performed no write.

Schema 4 and earlier overlays therefore fail the current gate even if ordinary live
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
5. exact page-owned attachment-count evidence with no hidden fallback or automatic retry;
6. current recovery-before-staging, schema-5 page-deadline submit guarantees, and
   restart-safe destructive stale-composer cleanup proof.

Until that live gate succeeds, existing capability metadata remains conservative.
