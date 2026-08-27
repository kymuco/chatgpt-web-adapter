# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / schema-10 closure review pending / authenticated live graduation pending**

PR9.2 expands `ChatGPTProductRuntime` from text-only input to images, files, and multimodal continuation without weakening the frozen PR9.0 browser-owned production boundary or the PR9.1 browserless challenge boundary.

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
        +-- local path -> validated local snapshot/path
        +-- bytes -> private temporary file
        +-- data: URI -> decoded private temporary file
        +-- HTTP(S) URL -> fetched private temporary file
        +-- (source, filename) -> requested basename preserved
        |
        v
Native Messaging: local paths only, never attachment bytes
        |
        v
PR8.11 stale-UI recovery
        |
        v
schema-10 deadline-bounded official-composer clean proof
        |
        v
durable local fence + browser-session runtime identity
        |
        v
DOM.setFileInputFiles on official ChatGPT page
        |
        v
stable cross-channel exact page-owned attachment evidence
        |
        v
Send readiness
        |
        v
ONE page task:
  absolute page deadline check
  + final exact attachment validation
  + Send button validation
  + button.click()
        |
        v
Network.requestWillBeSent proves protected conversation write
        |
        v
existing browser-owned completion + canonical assistant readback
```

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint. The historical schema-7 compatibility filename also remains stable and loads immutable authority generations in order:

```text
schema-7 reviewed core
  -> schema-8 clean-composer / destructive-close repair
  -> schema-9 cross-evidence-channel exactness repair
  -> schema-10 official-composer / basename / pre-stage-deadline repair
```

Text-only turns continue through the historical product path. Later overlays change authority only for rich input or durable rich-input fence recovery.

## Input and transport boundary

- The established public `MediaItem` contract remains compatible with local paths, bytes/bytearray, base64 `data:` URIs, HTTP(S) URLs, and `(source, filename)`.
- Non-path inputs are materialized before browser delegation.
- Native Messaging carries validated local paths only; attachment bytes never cross the bridge.
- `media=[]` remains text-only.
- Browserless and Temporary Chat rich input fail before write.
- Injected/custom/subclassed browser-owned transports cannot gain rich-input authority merely by reusing the `browser-owned` transport identity.
- Rich provider results must confirm the exact requested attachment count.
- No browserless fallback, challenge bypass, protected-request reconstruction, or automatic write retry is introduced.

## One total deadline and protected-submit authority

Attachment staging occurs only after PR8.11 stale-UI recovery, so an authorized reload cannot erase a selected file after staging.

One outer rich-turn deadline governs recovery/reload, runtime-tab waits, clean-composer proof, debugger setup, staging, protected submission, post-submit observation, and cleanup. Raw CDP `Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` are not protected-submit authority for rich turns.

The only rich protected-submit primitive is:

`PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`

The final page expression checks an absolute deadline, validates the current attachment evidence, validates the Send button, and synchronously calls `button.click()`. No page task can run between final attachment validation and the protected click.

The debugger acknowledgement of the command that may click is deliberately not awaited. A slow acknowledgement must not convert an already-issued write into a local timeout. The already-installed `Network.requestWillBeSent` observation of the protected conversation POST is the first post-submit proof. Missing observation fails without retry; canonical assistant readback remains final completion authority.

## Page-owned attachment evidence generations

`DOM.setFileInputFiles` path count is not evidence that ChatGPT accepted an attachment. PR9.2 therefore derives attachment authority from page-owned composer state.

### Schema 8 — clean composer and exact per-channel sets

Schema 8 introduced a stable pre-stage clean-composer proof and exact-set matching after staging. It also closed destructive stale-runtime cleanup TOCTOU by revalidating tab/runtime/fence ownership at the destructive boundary.

### Schema 9 — cross-channel exactness

The page exposes attachment evidence through multiple observable channels, currently role-group labels and attachment-removal controls. Schema 9 requires every non-empty evidence channel to independently describe the requested set exactly. One correct channel cannot mask extra, partial, or different evidence in another.

### Schema 10 — official composer only

Fresh closure review found that an empty fallback `form` or `document.body` could previously be mistaken for a clean composer while the real prompt editor was still mounting.

Schema 10 removes those fallbacks. Attachment evidence is unavailable until the official prompt editor is present through `#prompt-textarea` or `[data-testid="prompt-textarea"]` and belongs to its composer form. Missing official composer yields `ready=false` and cannot count as a clean poll.

The pre-stage clean proof requires two stable polls with:

- the official composer mounted;
- exact-basename association enabled;
- exact empty attachment evidence;
- zero observed role-group labels;
- zero observed removal-control labels.

The shared evidence binding is replaced at the newest layer, so schema-10 semantics are also used by post-stage stable evidence and schema-7's atomic final validate+click.

## Exact basename association

Schema 10 also removes substring filename aliases. Requested `report.txt` must not be satisfied by `old-report.txt`, `report.txt.bak`, or `Remove old-report.txt`.

Role-group evidence requires exact basename equality. Removal controls may contain UI wording such as `Remove report.txt`, but the requested basename must appear as the complete tail token with a valid UI-wording boundary before it. Cross-channel exactness from schema 9 remains mandatory.

## Deadline-bounded pre-stage debugger setup

Schema 8 added debugger setup for the clean-composer proof, but fresh review found raw awaits on `chrome.debugger.attach` and `Runtime.enable` outside the absolute deadline runner.

Schema 10 bounds both operations by the one outer rich-turn deadline. Because a Chrome debugger attach is not cancellable after dispatch, schema 10 also handles the late-completion case: if the local deadline wins but the pending attach later succeeds, a best-effort detach is immediately dispatched so stale debugger ownership cannot block a later turn. Normal pre-stage detach is likewise best-effort and non-blocking.

## Durable stale-composer fence and destructive cleanup

Before `DOM.setFileInputFiles`, PR9.2 persists a durable local fence containing the runtime tab ID and random runtime identity, plus matching browser-session identity in `chrome.storage.session`.

The local fence survives Manifest V3 worker suspension/restart and remains the safety authority. Session identity is destructive-cleanup authority only. Clearing `input.files` is never accepted as composer-cleanup proof.

The generic destructive cleanup proof remains:

`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`

A reused numeric tab ID pointing outside ChatGPT is never closed. A still-live ChatGPT tab with missing, mismatched, or unproven runtime identity remains untouched and keeps the durable fence fail-closed.

Before destructive close, schema 8 observes relevant tab/storage ownership changes and immediately re-reads both fence identities, the current extension runtime-tab ID, and current ChatGPT tab/URL. Any mismatch or intervening change fails closed. No awaited operation occurs between the final authority guard and dispatch of `chrome.tabs.remove(tabId)`; the authorized close is then awaited under the remaining deadline and followed by explicit absence proof.

## Extension parser and package-data hardening

Source review previously found a real JavaScript syntax defect that Python text assertions did not detect. PR9.2 now runs `node --check` over every packaged extension `.js` asset.

The release gate also compares the complete source browser-extension `*.js`/`*.json` asset set with the built wheel, so a new authority overlay cannot exist only in the source tree while the installed package silently ships an older runtime.

## Schema-10 zero-write support gate

Schema-7 through schema-9 gate modules remain packaged for provenance but cannot graduate schema 10. The authoritative current module is:

`product_rich_input_live_gate_schema10_pr9_2`

Its support phase performs characterization-only RPCs containing no text and no attachment paths. It preserves every earlier validator requirement and additionally requires:

- `officialComposerRequiredForAttachmentEvidence=true`;
- `exactBasenameAssociationRequired=true`;
- `preStageDebuggerSetupDeadlineBounded=true`;
- `latePreStageDebuggerAttachAutoDetached=true`.

Inherited requirements include schema-9 cross-channel exactness, schema-8 clean-composer/destructive-close guarantees, schema-7 atomic submit/session identity guarantees, one total deadline, page-owned evidence, no rich raw-CDP fallback, no automatic retry, and no fallback transport.

Schema 9 and earlier cannot satisfy the authoritative schema-10 gate.

## Bounded authenticated live evidence

The authenticated phase remains explicit opt-in and has an exact budget of **three** real product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

Expected answers are absent from the prompts. Every turn must depend on attachment-only content, produce exactly one browser-native write event and one canonical readback event with attachment count `1`, prove `CANONICAL_READBACK` finality, and preserve continuation conversation identity.

The authoritative command is:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_schema10_pr9_2 \
  --acknowledge-live-writes
```

Authenticated rich-input writes have **not** been run while closure review is pending.

## Deterministic closure rule

A previously green CI run is not sufficient after a new authority generation or a head-changing synchronization commit. The final schema-10 head requires:

- full Ubuntu/Windows Python 3.10–3.14 test matrix;
- release build and package-data contract validation;
- installed exact-wheel smoke on Ubuntu/Windows Python 3.10/3.14;
- zero unresolved current inline review threads;
- a fresh Codex closure review of that exact head.

Until this closure is clean:

- authenticated rich-input writes are not run;
- `images`, `files`, and `multimodal_continuation` remain conservative;
- no capability is graduated from implementation alone;
- PR9.2 is not merged.

## Capability graduation rule

Implementation, static support claims, deterministic CI, and source review are still not live product evidence. Graduation requires all three attachment-dependent authenticated turns, exact browser-native write/readback evidence, canonical finality, conversation identity preservation, and the complete schema-10 recovery/deadline/official-composer/exact-basename/cross-channel-exact/atomic-submit/session-identity/destructive-cleanup contract.

Until that bounded gate succeeds, no rich-input capability is claimed `AVAILABLE`.
