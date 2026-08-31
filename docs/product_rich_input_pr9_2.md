# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / schema-15 code closure green / final docs-synchronized exact-head closure pending / authenticated live graduation pending**

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
        +-- attachmentPaths + requiredModelMode
        |      -> schema-14 fail closed before staging / PR8.10 selector / write
        |
        v
PR8.11 stale-UI recovery
        |
        v
official-composer clean proof
        |
        v
schema-15 successful clean-proof debugger detach handoff
        |
        v
schema-13 fully deadline-governed attachment staging
        |
        +-- debugger attach / Runtime.enable / DOM.enable
        +-- composer readiness
        +-- file-input lookup/reveal
        +-- durable fence persistence
        +-- DOM.setFileInputFiles
        +-- bounded successful release/detach
        |
        v
schema-12 deadline-bounded post-stage debugger setup
        |
        v
stable cross-channel exact page-owned attachment evidence
        |
        v
schema-15 successful observer debugger detach handoff
        |
        v
deadline-bounded Send readiness
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

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint. The historical schema-7 compatibility filename remains stable and loads immutable authority generations in order:

```text
schema-7 reviewed core
  -> schema-8 clean-composer / destructive-close repair
  -> schema-9 cross-evidence-channel exactness repair
  -> schema-10 official-composer / basename / pre-stage-deadline repair
  -> schema-11 structured-basename / evidence-read-deadline repair
  -> schema-12 post-stage-debugger / send-readiness-deadline repair
  -> schema-13 actual-staging-primitive deadline / durable-fence repair
  -> schema-14 rich-input/model-profile composition guard
  -> schema-15 successful debugger-ownership handoff repair
```

Text-only turns continue through the historical product path. Later overlays change authority only for rich input, durable rich-input fence recovery, the explicitly unproven rich-input/model-profile composition, or debugger ownership between already-reviewed rich-input phases.

## Input and transport boundary

- The public `MediaItem` contract remains compatible with local paths, bytes/bytearray, base64 `data:` URIs, HTTP(S) URLs, and `(source, filename)`.
- Non-path inputs are materialized before browser delegation.
- Native Messaging carries validated local paths only; attachment bytes never cross the bridge.
- `media=[]` remains text-only.
- Browserless and Temporary Chat rich input fail before write.
- Rich input combined with `model_profile` is **not** a proven PR9.2 composition and fails closed in schema 14 before attachment staging, PR8.10 selector mutation, or protected write.
- Text-only `model_profile` turns retain their independently proven PR8.10 behavior.
- Injected/custom/subclassed browser-owned transports cannot gain rich-input authority merely by reusing the `browser-owned` transport identity.
- Rich provider results must confirm the exact requested attachment count.
- No browserless fallback, challenge bypass, protected-request reconstruction, automatic write retry, or silent rich-input-to-text fallback is introduced.

## One total deadline and protected-submit authority

Attachment staging occurs only after PR8.11 stale-UI recovery, so an authorized reload cannot erase a selected file after staging.

For the **supported PR9.2 rich-input scope**—ordinary browser-owned normal turns without a `model_profile` requirement—one outer rich-turn deadline governs recovery/reload, runtime-tab waits, clean-composer proof, successful clean-proof debugger release, the complete attachment-staging primitive, pre-stage and post-stage debugger setup, page-owned attachment evidence reads, successful post-stage observer debugger release, Send readiness, protected submission, post-submit observation, and governed cleanup.

PR8.10 model-profile selection was proven independently before PR9.2 and still owns fixed/raw prewrite selector operations. PR9.2 does not claim those selector operations are governed by the rich-turn deadline. Schema 14 therefore prevents the new `media + model_profile` composition from entering either rich staging or the PR8.10 selector.

Raw CDP `Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` are not protected-submit authority for rich turns. The only rich protected-submit primitive is:

`PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`

The final page expression checks an absolute deadline, validates current attachment evidence, validates the Send button, and synchronously calls `button.click()`. No page task can run between final attachment validation and the protected click.

The debugger acknowledgement of the command that may click is deliberately not awaited. A slow acknowledgement must not convert an already-issued write into a local timeout. The already-installed `Network.requestWillBeSent` observation of the protected conversation POST is the first post-submit proof. Missing observation fails without retry; canonical assistant readback remains final completion authority.

## Page-owned attachment evidence generations

`DOM.setFileInputFiles` path count is not evidence that ChatGPT accepted an attachment. PR9.2 derives attachment authority from page-owned composer state.

### Schema 8 — clean composer and exact per-channel sets

Schema 8 introduced stable pre-stage clean-composer proof, exact-set matching after staging, and destructive stale-runtime cleanup revalidation at the destructive boundary.

### Schema 9 — cross-channel exactness

Every non-empty page-owned evidence channel must independently describe the requested attachment set exactly. One correct channel cannot mask extra, partial, or different evidence in another channel.

### Schema 10 — official composer and pre-stage debugger deadline

Schema 10 removed fallback `form`/`document.body` cleanliness proof. Evidence is unavailable until the official prompt editor is present through `#prompt-textarea` or `[data-testid="prompt-textarea"]` and belongs to its composer form. Pre-stage debugger attach and `Runtime.enable` are bounded by the outer deadline, with best-effort late-attach cleanup after an already reported failure.

### Schema 11 — literal basename association and bounded evidence reads

Schema 11 removed suffix/delimiter/quote heuristics that could alias filenames. Role-group evidence requires exact label equality. Removal-control evidence must use a recognized anchored removal action and the complete remaining payload is treated literally as the candidate basename.

The shared page-owned evidence reader is also bounded through `_pr92Schema7RunUntil` against the same absolute rich-turn deadline. These semantics are consumed by clean proof, post-stage evidence, and final atomic validation.

### Schema 12 — bounded post-stage debugger setup and Send readiness

Schema 12 bounded post-stage debugger attach and `Runtime.enable`, including late successful attach cleanup, and bounded the complete Send-readiness helper invocation. Its support guarantees include:

- `postStageDebuggerSetupDeadlineBounded=true`;
- `latePostStageDebuggerAttachAutoDetached=true`;
- `sendReadinessWaitDeadlineBounded=true`.

### Schema 13 — fully governed actual staging primitive

Schema 13 removed the captured historical file-selection primitive from the current path. The current staging implementation explicitly bounds, against the same `context.deadlineAt`:

- staging debugger attach with late-success auto-detach;
- `Runtime.enable` and `DOM.enable`;
- composer readiness;
- initial and post-reveal file-input lookup;
- optional reveal evaluation and settle wait;
- durable stale-composer fence persistence;
- `DOM.setFileInputFiles` acknowledgement;
- successful `Runtime.releaseObject`;
- successful debugger detach.

`DOM.setFileInputFiles` is never dispatched until durable fence persistence has completed inside the outer deadline and the in-memory fenced tab identity matches the staging tab. If file selection executes or acknowledges only after the local deadline race is lost, the turn remains failed and the durable fence remains authoritative. The next write must first prove destructive stale-composer cleanup or fail closed; there is no automatic retry.

Schema 13 advertises and the authoritative support chain requires:

- `attachmentStagingPrimitiveDeadlineBounded=true`;
- `stagingDebuggerSetupDeadlineBounded=true`;
- `stagingComposerReadinessDeadlineBounded=true`;
- `stagingFileInputLookupDeadlineBounded=true`;
- `stagingFencePersistenceDeadlineBounded=true`;
- `stagingFileSelectionDeadlineBounded=true`;
- `stagingPostSelectionCleanupDeadlineBounded=true`;
- `lateStagingDebuggerAttachAutoDetached=true`;
- `lateFileSelectionFailsClosedBehindDurableFence=true`;
- `postSelectionCleanupBestEffortAfterTimeout=true`.

### Schema 14 — fail-closed rich-input/model-profile composition boundary

A manual exact-head source audit found the high-level runtime could combine `media=[...]` with `model_profile=...`, while PR8.10's independently proven model selector contains fixed/raw prewrite selector operations outside the PR9.2 rich-turn deadline proof.

Schema 14 does not rewrite or weaken PR8.10. It detects non-empty `attachmentPaths` together with non-empty `requiredModelMode` and throws `PR9_2_RICH_INPUT_MODEL_PROFILE_COMBINATION_UNAVAILABLE` before delegating to the prior worker chain.

Therefore the rejected composition performs no rich staging, creates no attachment fence, selects no attachment, starts no PR8.10 selector mutation, performs no protected conversation write, and does not fall back or retry.

Schema 14 requires:

- `richInputModelProfileCombinationSupported=false`;
- `richInputModelProfileCombinationFailsBeforeStaging=true`;
- `richInputModelProfileCombinationFailsBeforeWrite=true`;
- `pr810RawPrewriteSelectorExcludedFromRichInput=true`.

### Schema 15 — completed debugger ownership handoffs

The schema-14 exact-head closure review found two remaining successful-path debugger ownership races.

First, schema 10's clean-composer observer dispatched a best-effort detach and returned immediately. Schema 13 could then try to attach the same runtime tab for file selection while the prior detach was still pending. This could reject an otherwise valid rich turn before file selection.

Second, schema 12's post-stage attachment observer also dispatched detach without awaiting successful completion. The inherited protected-dispatch path could attempt the next debugger attach while the observer still owned or was still releasing the tab. Because files were already staged, this could force fenced recovery instead of submitting an otherwise valid turn.

Schema 15 replaces only those two current observer bindings. On the successful path:

- clean-proof detach is awaited through `_pr92Schema7RunUntil(context.deadlineAt, ...)` before schema-13 staging may attach;
- post-stage observer detach is awaited through the same outer deadline before page-owned evidence is returned to protected dispatch;
- debugger ownership is therefore fully relinquished before the next attach begins.

On error or timeout paths, detach remains best-effort and non-authoritative so cleanup cannot extend or rewrite an already reported failure. A pre-stage detach timeout occurs before file selection. A post-stage detach timeout occurs after durable-fenced staging, so the existing stale-composer fence remains fail-closed authority for the next write. No automatic retry is introduced.

Schema 15 advertises and the authoritative support gate requires:

- `preStageSuccessfulDebuggerDetachDeadlineBounded=true`;
- `postStageSuccessfulDebuggerDetachDeadlineBounded=true`;
- `debuggerOwnershipHandoffCompletedBeforeNextAttach=true`;
- `failurePathDebuggerDetachBestEffort=true`.

All schema-14 through schema-7 authority remains inherited.

## Durable stale-composer fence and destructive cleanup

Before any `DOM.setFileInputFiles` dispatch, PR9.2 persists a durable local fence containing the runtime tab ID and random runtime identity, plus matching browser-session identity in `chrome.storage.session`. The local fence survives Manifest V3 worker suspension/restart and remains the safety authority. Session identity is destructive-cleanup authority only; clearing `input.files` is never accepted as composer-cleanup proof.

The generic destructive cleanup proof remains:

`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`

A reused numeric tab ID pointing outside ChatGPT is never closed. A still-live ChatGPT tab with missing, mismatched, or unproven runtime identity remains untouched and keeps the durable fence fail-closed.

Before destructive close, schema 8 immediately re-reads fence identity, browser-session identity, current runtime-tab ownership, and current ChatGPT tab/URL. Any mismatch or intervening ownership change fails closed. No awaited operation occurs between the final destructive authority guard and dispatch of `chrome.tabs.remove(tabId)`; the authorized close is then awaited under the remaining deadline and followed by explicit absence proof.

## Extension parser and package-data hardening

Every packaged extension `.js` asset is parsed with `node --check`.

The release gate compares the complete source browser-extension `*.js`/`*.json` asset set with the built wheel. A new authority overlay cannot exist only in source while the installed package silently ships an older runtime.

## Schema-15 zero-write support gate

Schema-7 through schema-14 gate modules remain packaged for provenance but cannot graduate schema 15. The authoritative current module is:

`product_rich_input_live_gate_schema15_pr9_2`

Its support phase performs **nine characterization-only RPCs**, each containing no text and no attachment paths. It preserves every earlier validator requirement and additionally requires the complete schema-15 debugger ownership handoff contract above.

Inherited requirements include the schema-14 composition boundary, schema-13 complete staging deadline/fence guarantees, schema-12 debugger/readiness deadlines, schema-11 literal basename association and bounded evidence reads, schema-10 official-composer proof and pre-stage debugger deadlines, schema-9 cross-channel exactness, schema-8 clean-composer/destructive-close guarantees, schema-7 atomic submit/session identity guarantees, one total deadline within the supported rich-input scope, page-owned evidence, no rich raw-CDP submit fallback, no automatic retry, and no fallback transport.

Schema 14 and earlier cannot satisfy the authoritative schema-15 gate.

## Bounded authenticated live evidence

The authenticated phase remains explicit opt-in and has an exact budget of **three** real product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

These fixtures deliberately do not request a model profile; schema 14 defines that composition as unavailable rather than silently pretending it belongs to the proven rich-input surface.

Expected answers are absent from the prompts. Every turn must depend on attachment-only content, produce exactly one browser-native write event and one canonical readback event with attachment count `1`, prove `CANONICAL_READBACK` finality, and preserve continuation conversation identity.

The authoritative command is:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_schema15_pr9_2 \
  --acknowledge-live-writes
```

Authenticated rich-input writes have **not** been run while deterministic/source-review closure is pending.

## Deterministic closure evidence

Schema-15 code head `cf984b370431985408679b134f5984e577e8dd44` passed CI #400 (`33158551451`) completely:

- Ubuntu/Windows Python 3.10–3.14 matrix: **10/10 PASS**;
- Ubuntu Python 3.10 reference: **1516 passed, 1 warning**;
- release build / metadata / complete browser-extension package-data contract: **PASS**;
- installed exact-wheel smoke Ubuntu/Windows Python 3.10/3.14: **4/4 PASS**.

The two schema-14 closure-review debugger-handoff P2 findings were fixed by schema 15, replied to with the exact #400 evidence above, and resolved. The first active schema-15 candidate exposed two mistakes only in the newly added static regression assertions: they matched the initialization `attached = false` instead of the successful post-detach assignment. The assertions were corrected without changing runtime code; CI #400 is the resulting clean code-head evidence.

Earlier schema-14 code head `309d6784e364e994f45b45a1618ce4be27bd45e9` had passed CI #394. Earlier schema-13 heads and reviews are retained as provenance but are not reused as schema-15 closure evidence.

A previously green CI run is not sufficient after a head-changing synchronization commit. Therefore this documentation synchronization creates a new final candidate that must itself pass:

- full Ubuntu/Windows Python 3.10–3.14 test matrix;
- release build and package-data contract validation;
- installed exact-wheel smoke on Ubuntu/Windows Python 3.10/3.14;
- zero unresolved current inline review threads;
- a fresh Codex closure review of that exact head.

Until this closure is clean:

- authenticated rich-input writes are not run;
- `images`, `files`, and `multimodal_continuation` remain conservative;
- rich input + `model_profile` remains explicitly unavailable;
- no capability is graduated from implementation alone;
- PR9.2 is not merged.

## Capability graduation rule

Implementation, static support claims, deterministic CI, and source review are still not live product evidence. Graduation requires all three attachment-dependent authenticated turns, exact browser-native write/readback evidence, canonical finality, conversation identity preservation, the complete schema-15 debugger ownership handoff contract, the schema-14 composition boundary, and the inherited schema-13 staging/fence/recovery/deadline/official-composer/literal-basename/cross-channel-exact/atomic-submit/session-identity/destructive-cleanup contract.

Until that bounded gate succeeds, no rich-input capability is claimed `AVAILABLE`.
