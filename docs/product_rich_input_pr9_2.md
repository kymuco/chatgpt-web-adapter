# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / schema-12 code closure green / final docs-synchronized exact-head closure pending / authenticated live graduation pending**

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
schema-12 governed official-composer clean proof
        |
        v
durable local fence + browser-session runtime identity
        |
        v
DOM.setFileInputFiles on official ChatGPT page
        |
        v
deadline-bounded post-stage debugger setup
        |
        v
stable cross-channel exact page-owned attachment evidence
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

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint. The historical schema-7 compatibility filename also remains stable and loads immutable authority generations in order:

```text
schema-7 reviewed core
  -> schema-8 clean-composer / destructive-close repair
  -> schema-9 cross-evidence-channel exactness repair
  -> schema-10 official-composer / basename / pre-stage-deadline repair
  -> schema-11 structured-basename / evidence-read-deadline repair
  -> schema-12 post-stage-debugger / send-readiness-deadline repair
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

One outer rich-turn deadline governs recovery/reload, runtime-tab waits, clean-composer proof, pre-stage and post-stage debugger setup, every page-owned attachment evidence read, staging, the complete Send-readiness wait, protected submission, post-submit observation, and cleanup. Raw CDP `Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` are not protected-submit authority for rich turns.

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

### Schema 10 — official composer and pre-stage debugger deadline

Schema 10 removed fallback `form`/`document.body` cleanliness proof. Attachment evidence is unavailable until the official prompt editor is present through `#prompt-textarea` or `[data-testid="prompt-textarea"]` and belongs to its composer form. Missing official composer yields `ready=false` and cannot count as a clean poll.

The pre-stage clean proof requires two stable polls with the official composer mounted, exact empty attachment evidence, and zero observed attachment labels. Schema 10 also bounded pre-stage `chrome.debugger.attach` and `Runtime.enable` by the one outer deadline, including best-effort detach when a non-cancellable attach completes only after the local deadline.

### Schema 11 — literal structured basename association and bounded evidence reads

The schema-10 closure review found two remaining gaps.

First, delimiter-based tail matching could still alias a filename containing spaces: requested `report.txt` could be satisfied by a removal label such as `Remove old report.txt`. Schema 11 removes tail inference completely. Role-group evidence still requires exact label equality. Removal-control evidence must begin with an anchored recognized removal action (`remove`, `delete`, `discard`, or `удалить`); the **entire trimmed payload after that action is treated literally as the candidate basename**, and that candidate must equal the requested basename exactly.

Therefore:

- `Remove report.txt` may confirm `report.txt`;
- `Remove old report.txt` cannot confirm `report.txt`;
- `Remove old-report.txt` cannot confirm `report.txt`;
- `Remove report.txt.bak` cannot confirm `report.txt`;
- ambiguously decorated `Delete "report.txt"` fails closed rather than silently stripping quotes.

No suffix, delimiter, quote, punctuation, or substring heuristic may manufacture basename equality. Schema-9 cross-channel exactness remains mandatory.

Second, the shared page-owned evidence reader previously awaited raw `Runtime.evaluate` and only checked the deadline before and after the command. Schema 11 wraps the complete shared evidence-read primitive in `_pr92Schema7RunUntil` against the same absolute rich-turn deadline. This applies to pre-stage clean polls and all later stable/final attachment evidence reads. A late evidence read has no write authority and cannot extend the active request past the governed deadline.

The shared evidence-expression and evidence-read bindings are replaced at the newest evidence layer, so schema-11 semantics are consumed by pre-stage proof, post-stage stable evidence, and schema-7's atomic final validate+click.

### Schema 12 — bounded post-stage debugger setup and Send readiness

The fresh exact-head schema-11 closure review found two additional deadline gaps outside the already bounded evidence reader.

First, after `DOM.setFileInputFiles`, the observer that attaches to the runtime tab and enables the Runtime domain still raw-awaited `chrome.debugger.attach` and `Runtime.enable`. Schema 12 replaces that post-stage observer boundary. Both operations consume the same absolute rich-turn deadline through `_pr92Schema7RunUntil`. Because `chrome.debugger.attach` itself is non-cancellable, a late successful attach after local timeout immediately dispatches best-effort detach and cannot extend or change the already reported timeout outcome.

Second, schema 7's final atomic submit waited for `waitForSendButtonPoint`, whose inner `querySendButtonPoint` can itself stall in `Runtime.evaluate`. A local `readyBudget` cannot re-check elapsed time while that command is pending. Schema 12 therefore wraps the **complete Send-readiness helper invocation** in `_pr92Schema7RunUntil(context.deadlineAt, ...)`. A late readiness read has no write authority; the only possible rich write remains the later page-deadline-guarded atomic validate-and-click expression.

Schema 12 advertises all three new support guarantees:

- `postStageDebuggerSetupDeadlineBounded=true`;
- `latePostStageDebuggerAttachAutoDetached=true`;
- `sendReadinessWaitDeadlineBounded=true`.

## Durable stale-composer fence and destructive cleanup

Before `DOM.setFileInputFiles`, PR9.2 persists a durable local fence containing the runtime tab ID and random runtime identity, plus matching browser-session identity in `chrome.storage.session`.

The local fence survives Manifest V3 worker suspension/restart and remains the safety authority. Session identity is destructive-cleanup authority only. Clearing `input.files` is never accepted as composer-cleanup proof.

The generic destructive cleanup proof remains:

`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`

A reused numeric tab ID pointing outside ChatGPT is never closed. A still-live ChatGPT tab with missing, mismatched, or unproven runtime identity remains untouched and keeps the durable fence fail-closed.

Before destructive close, schema 8 observes relevant tab/storage ownership changes and immediately re-reads both fence identities, the current extension runtime-tab ID, and current ChatGPT tab/URL. Any mismatch or intervening change fails closed. No awaited operation occurs between the final authority guard and dispatch of `chrome.tabs.remove(tabId)`; the authorized close is then awaited under the remaining deadline and followed by explicit absence proof.

## Extension parser and package-data hardening

Every packaged extension `.js` asset is parsed with `node --check`.

The release gate compares the complete source browser-extension `*.js`/`*.json` asset set with the built wheel, so a new authority overlay cannot exist only in the source tree while the installed package silently ships an older runtime.

## Schema-12 zero-write support gate

Schema-7 through schema-11 gate modules remain packaged for provenance but cannot graduate schema 12. The authoritative current module is:

`product_rich_input_live_gate_schema12_pr9_2`

Its support phase performs **six characterization-only RPCs**, each containing no text and no attachment paths. It preserves every earlier validator requirement and additionally requires:

- `postStageDebuggerSetupDeadlineBounded=true`;
- `latePostStageDebuggerAttachAutoDetached=true`;
- `sendReadinessWaitDeadlineBounded=true`.

Inherited requirements include schema-11 literal structured basename association and bounded evidence reads, schema-10 official-composer evidence and pre-stage debugger deadline guarantees, schema-9 cross-channel exactness, schema-8 clean-composer/destructive-close guarantees, schema-7 atomic submit/session identity guarantees, one total deadline, page-owned evidence, no rich raw-CDP fallback, no automatic retry, and no fallback transport.

Schema 11 and earlier cannot satisfy the authoritative schema-12 gate.

## Bounded authenticated live evidence

The authenticated phase remains explicit opt-in and has an exact budget of **three** real product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

Expected answers are absent from the prompts. Every turn must depend on attachment-only content, produce exactly one browser-native write event and one canonical readback event with attachment count `1`, prove `CANONICAL_READBACK` finality, and preserve continuation conversation identity.

The authoritative command is:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_schema12_pr9_2 \
  --acknowledge-live-writes
```

Authenticated rich-input writes have **not** been run while deterministic/source-review closure is pending.

## Deterministic closure evidence

Schema-12 code head `0186e99189a98449d3f8723f1f2a7906d237dac1` passed CI #381 (`33153270464`) completely:

- Ubuntu/Windows Python 3.10–3.14 matrix: **10/10 PASS**;
- Ubuntu Python 3.10 reference: **1494 passed, 1 warning**;
- release build / metadata / complete browser-extension package-data contract: **PASS**;
- installed exact-wheel smoke Ubuntu/Windows Python 3.10/3.14: **4/4 PASS**.

The two fresh schema-11 exact-head closure-review findings were replied to and resolved against this evidence.

A previously green CI run is not sufficient after a head-changing synchronization commit. Therefore this documentation synchronization creates a new final candidate that must itself pass:

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

Implementation, static support claims, deterministic CI, and source review are still not live product evidence. Graduation requires all three attachment-dependent authenticated turns, exact browser-native write/readback evidence, canonical finality, conversation identity preservation, and the complete schema-12 recovery/deadline/official-composer/literal-basename/cross-channel-exact/atomic-submit/session-identity/destructive-cleanup contract.

Until that bounded gate succeeds, no rich-input capability is claimed `AVAILABLE`.
