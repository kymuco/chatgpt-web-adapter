# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / schema-8 deterministic closure pending / authenticated live graduation pending**

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
schema-8 clean-composer proof
        |
        v
durable local fence + browser-session runtime identity
        |
        v
DOM.setFileInputFiles on official ChatGPT page
        |
        v
stable page-owned EXACT attachment-set evidence
        |
        v
Send readiness
        |
        v
ONE page task:
  absolute page deadline check
  + final exact attachment-set validation
  + Send button validation
  + button.click()
        |
        v
Network.requestWillBeSent proves protected conversation write
        |
        v
existing browser-owned completion + canonical assistant readback
```

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint. After the full prior worker chain is assembled, PR9.2 loads the primary, deadline, and closure layers, then the historical schema-7 compatibility filename. That compatibility loader imports the immutable reviewed schema-7 core and immediately imports the schema-8 closure repair.

In other words, the manifest and long-lived service-worker entrypoint remain unchanged while authority progresses as:

```text
historical worker chain
  -> PR9.2 primary rich-input layer
  -> deadline/fence repair
  -> page-owned closure repair
  -> schema-7 core
  -> schema-8 closure repair
```

Text-only turns continue through the historical product path. Schema-8 changes authority only while rich input is active or while a durable rich-input fence must be recovered.

## Input and transport boundary

- The existing public `MediaItem` contract remains compatible with local paths, bytes/bytearray, base64 `data:` URIs, HTTP(S) URLs, and `(source, filename)`.
- Non-path inputs are materialized before browser delegation.
- Native Messaging carries only validated local paths; attachment bytes never cross the bridge.
- `media=[]` is text-only.
- Browserless rich input fails before write.
- Temporary Chat rich input fails before write until independently characterized.
- Injected/custom/subclassed browser-owned transports cannot gain rich-input authority merely by using the `browser-owned` transport identity.
- A rich custom provider result must confirm the exact requested attachment count.
- No browserless fallback, challenge bypass, protected-request reconstruction, or automatic write retry is introduced.

## Recovery and one total deadline

Attachment staging occurs only after PR8.11 stale-UI recovery, so an authorized reload cannot silently erase an already-selected file.

One outer rich-turn deadline governs recovery/reload, runtime-tab waits, clean-composer proof, staging, protected submission, post-submit observation, and cleanup. Raw CDP `Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` are not protected-submit authority for rich turns.

A potentially protected page click is guarded by an absolute page deadline. The debugger acknowledgement of a command that may click is not awaited, because an acknowledgement timeout after the page has already submitted would create response-loss ambiguity. The already-installed `Network.requestWillBeSent` observation of the protected conversation POST is the first post-submit proof. Missing observation fails without retry; canonical assistant readback remains final completion authority.

## Schema-8 exact page-owned attachment evidence

`DOM.setFileInputFiles` path count is not evidence that ChatGPT accepted an attachment. Likewise, merely finding every requested filename is not enough: a persistent composer can already contain a manual attachment or an old same-name chip.

Schema 8 therefore enforces two independent conditions.

### 1. Clean composer before staging

Before selecting any requested file, the official page must show **zero page-owned attachment evidence across two stable polls**. If a pre-existing attachment is visible, the rich turn fails before `DOM.setFileInputFiles` with no protected write.

This prevents an old same-name chip from being mistaken for the newly requested upload.

### 2. Exact set after staging and at submit

After staging, page-owned composer evidence must describe the **exact requested attachment set**, not a superset. Matching every requested basename while leaving unused attachment labels/chips is rejected.

The exact-set evidence is used throughout the later rich-input path, including the schema-7 atomic final validator. The last evidence validation and `button.click()` execute synchronously inside one page-side expression:

`PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`

There is therefore no separate CDP/page-task window in which the page can remove or add an attachment between final validation and the protected click.

## Durable stale-composer fence

Before `DOM.setFileInputFiles`, PR9.2 persists a durable local fence containing the runtime tab ID and a random runtime identity, plus a matching identity in `chrome.storage.session`.

The local fence survives Manifest V3 worker suspension/restart and remains the safety authority. Session identity is only destructive-cleanup authority. Clearing `input.files` is never accepted as composer-cleanup proof.

The only generic destructive cleanup proof remains:

`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`

A reused numeric tab ID pointing outside ChatGPT is never closed. A still-live ChatGPT tab with missing, mismatched, or unproven runtime identity remains untouched and keeps the durable fence fail-closed.

## Schema-8 destructive-close authority revalidation

Schema 7 verified the candidate ChatGPT URL, current extension runtime-tab ID, and matching local/session identities before destructive cleanup. Fresh closure review identified a remaining time-of-check/time-of-use window: those proofs could become stale while later asynchronous reads were pending.

Schema 8 closes that boundary.

While destructive authority is assembled, the extension observes relevant tab navigation/removal and local/session storage ownership changes. Immediately before `chrome.tabs.remove(tabId)` it re-reads:

1. the durable local fence identity;
2. the browser-session fence identity;
3. the currently stored extension runtime-tab ID;
4. the current tab and ChatGPT URL.

Any intervening ownership/navigation change fails closed. After the final authority guard there is **no awaited operation before dispatch of `chrome.tabs.remove(tabId)`**. Only the already-authorized close is then awaited under the remaining outer deadline, followed by explicit tab-absence proof.

## Extension JavaScript parser regression

During schema-8 source review, the exact schema-7 release artifact exposed a separate packaging/runtime blocker: the closure overlay contained a nested unescaped template literal inside a generated `Runtime.evaluate` expression. Python regressions had treated the JavaScript as text and therefore did not parse it.

The closure expression is repaired, and PR9.2 now includes a regression that runs `node --check` over every packaged extension `.js` file. A syntactically invalid service-worker asset can no longer pass the deterministic test suite merely because Python string assertions are green.

## Schema-8 zero-write support gate

The frozen schema-7 gate remains in the package for provenance and intentionally cannot graduate schema 8. The authoritative current gate is:

`product_rich_input_live_gate_schema8_pr9_2`

Before any authenticated product write it performs only zero-write characterization RPCs. It preserves every schema-7 support assertion and additionally requires all four schema-8 closure guarantees:

- `preStageComposerAttachmentClean=true`;
- `exactComposerAttachmentSetRequired=true`;
- `destructiveCleanupAuthorityRevalidatedAtClose=true`;
- `destructiveCleanupOwnershipChangeFailsClosed=true`.

The inherited schema-7 contract still requires, among other invariants:

- `DOM.setFileInputFiles` staging and Native Messaging path-only transport;
- official-page upload/protected-write ownership;
- recovery before staging and restart-persistent durable fence;
- one total rich-turn deadline and bounded cleanup;
- stable page-owned attachment evidence;
- raw-CDP Input and rich Enter fallback disabled;
- atomic final attachment validation + Send click in one page task;
- protected submit primitive exactly `PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`;
- late execution prevented by the page-side absolute deadline;
- post-click debugger acknowledgement not required;
- protected-submit outcome proved by `NETWORK_REQUEST_OBSERVATION`;
- sufficient submit-observation reserve;
- destructive cleanup requires browser-session runtime identity;
- mismatched/unproven identity fails closed and never authorizes tab destruction;
- automatic write retry disabled;
- no fallback transport;
- support characterization performs no write.

Schema 7 and earlier cannot satisfy the authoritative schema-8 gate.

## Bounded authenticated live evidence

The authenticated phase remains explicit opt-in and has an exact budget of **three** real product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

Expected answers are absent from the prompts. Every turn must depend on attachment-only content, produce exactly one browser-native write event and one canonical readback event with attachment count `1`, and prove `CANONICAL_READBACK` finality. The continuation must preserve conversation identity.

The current authoritative command is:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_schema8_pr9_2 \
  --acknowledge-live-writes
```

The command has **not** been run while deterministic closure/review is pending.

## Deterministic closure rule

A previously green CI run is not sufficient after a new authority repair. Schema 8 requires a fresh exact-head full CI/release/wheel result plus a fresh Codex closure review of the same implementation head.

Until that deterministic closure is clean:

- authenticated rich-input writes are not run;
- `images`, `files`, and `multimodal_continuation` remain conservative;
- no capability is graduated from implementation alone;
- PR9.2 is not merged.

## Capability graduation rule

Implementation, static support claims, and deterministic CI are not live product evidence. Graduation requires all three attachment-dependent authenticated turns, exact write/readback evidence, canonical finality, conversation identity preservation, and the complete schema-8 recovery/deadline/exact-attachment/atomic-submit/session-identity/destructive-cleanup contract.

Until that bounded gate succeeds, no rich-input capability is claimed `AVAILABLE`.
