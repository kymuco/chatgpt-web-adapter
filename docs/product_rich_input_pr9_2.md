# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / schema-9 deterministic closure pending / authenticated live graduation pending**

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
schema-9 cross-channel exact page-owned attachment evidence
        |
        v
Send readiness
        |
        v
ONE page task:
  absolute page deadline check
  + final cross-channel exact attachment validation
  + Send button validation
  + button.click()
        |
        v
Network.requestWillBeSent proves protected conversation write
        |
        v
existing browser-owned completion + canonical assistant readback
```

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint. The historical schema-7 compatibility filename is also preserved; it now loads immutable authority generations in order:

```text
schema-7 reviewed core
  -> schema-8 clean-composer / destructive-close repair
  -> schema-9 cross-evidence-channel exactness repair
```

Text-only turns continue through the historical product path. These later overlays change authority only while rich input is active or while a durable rich-input fence must be recovered.

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

## Schema-8 clean composer and exactness baseline

`DOM.setFileInputFiles` path count is not evidence that ChatGPT accepted an attachment. Likewise, merely finding every requested filename is not enough: a persistent composer can already contain a manual attachment or an old same-name chip.

Schema 8 first requires the official composer to show **zero page-owned attachment evidence across two stable polls** before staging. A pre-existing/manual or old same-name attachment therefore blocks the rich turn before `DOM.setFileInputFiles` and before any protected write.

After staging, schema 8 strengthened each observed page-owned evidence channel from subset matching to exact matching. It also retained the existing synchronous final authority primitive:

`PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`

The last evidence evaluation and `button.click()` execute inside one page task, so no page task can add/remove an attachment between final validation and protected click.

## Schema-9 cross-channel exactness

Independent source review after schema-8 CI found one remaining exactness hole. The page exposes attachment evidence through more than one observable channel, currently role-group labels and attachment-removal controls. Schema 8 required exactness *inside* each channel, but accepted the final state when **either** channel was exact.

That permitted a cross-channel counterexample such as:

```text
requested attachment: requested.txt
role-group channel:   requested.txt        -> exact
removal channel:      Remove extra.txt     -> not exact
```

The exact role-group channel could mask incompatible evidence in the removal channel.

Schema 9 closes this by requiring:

- every **non-empty** page-owned evidence channel to independently match the requested attachment set exactly;
- at least one channel to prove the requested set when attachments are expected;
- for the pre-stage empty-composer proof, all observed evidence channels to be empty/exact.

Therefore an exact channel can no longer hide an extra, partial, or different attachment in another channel. The schema-9 evidence expression is installed as the shared page-owned evidence primitive, so it is consumed by schema-8 pre-stage cleanliness, post-stage stable evidence, and schema-7's synchronous atomic final validate+click.

## Durable stale-composer fence and destructive cleanup

Before `DOM.setFileInputFiles`, PR9.2 persists a durable local fence containing the runtime tab ID and a random runtime identity, plus a matching identity in `chrome.storage.session`.

The local fence survives Manifest V3 worker suspension/restart and remains the safety authority. Session identity is only destructive-cleanup authority. Clearing `input.files` is never accepted as composer-cleanup proof.

The only generic destructive cleanup proof remains:

`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED`

A reused numeric tab ID pointing outside ChatGPT is never closed. A still-live ChatGPT tab with missing, mismatched, or unproven runtime identity remains untouched and keeps the durable fence fail-closed.

Schema 8 closes the destructive-close TOCTOU boundary. While destructive authority is assembled, the extension observes relevant tab navigation/removal and local/session storage changes. Immediately before `chrome.tabs.remove(tabId)` it re-reads both fence identities, the current extension runtime-tab ID, and the current ChatGPT tab/URL. Any intervening ownership/navigation change fails closed. After the final guard there is **no awaited operation before dispatch of `chrome.tabs.remove(tabId)`**; only the already-authorized close is then awaited under the remaining outer deadline and followed by explicit absence proof.

## Extension JavaScript parser regression

During schema-8 source review, the previous schema-7 release artifact exposed a separate packaging/runtime blocker: the closure overlay contained a nested unescaped template literal inside a generated `Runtime.evaluate` expression. Python regressions had treated JavaScript as text and did not parse it.

The expression is repaired, and PR9.2 now runs `node --check` over every packaged extension `.js` asset. Because package data uses `browser_native_extension/*.js`, the release gate additionally verifies that the complete source extension asset set is present in the wheel.

## Schema-9 zero-write support gate

Schema-7 and schema-8 gate modules remain packaged for provenance and intentionally cannot graduate schema 9. The authoritative current gate is:

`product_rich_input_live_gate_schema9_pr9_2`

Before any authenticated product write it performs characterization-only RPCs with no text and no attachment paths. It reuses every schema-8 validator requirement and additionally requires:

- `crossEvidenceChannelExactness=true`.

The inherited schema-8 contract still requires:

- `preStageComposerAttachmentClean=true`;
- `exactComposerAttachmentSetRequired=true`;
- `destructiveCleanupAuthorityRevalidatedAtClose=true`;
- `destructiveCleanupOwnershipChangeFailsClosed=true`;
- every earlier schema-7 recovery/deadline/page-owned-evidence/atomic-submit/session-identity guarantee;
- `automaticWriteRetry=false`;
- no fallback transport;
- zero writes during support characterization.

Schema 8 and earlier cannot satisfy the authoritative schema-9 gate.

## Bounded authenticated live evidence

The authenticated phase remains explicit opt-in and has an exact budget of **three** real product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

Expected answers are absent from the prompts. Every turn must depend on attachment-only content, produce exactly one browser-native write event and one canonical readback event with attachment count `1`, and prove `CANONICAL_READBACK` finality. The continuation must preserve conversation identity.

The authoritative command is:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_schema9_pr9_2 \
  --acknowledge-live-writes
```

The command has **not** been run while deterministic closure/review is pending.

## Deterministic closure rule

A previously green CI run is not sufficient after a new authority generation. Schema 9 requires a fresh exact-head full test matrix, release/package validation, installed-wheel smoke, and a fresh Codex closure review of the same head.

Until that deterministic closure is clean:

- authenticated rich-input writes are not run;
- `images`, `files`, and `multimodal_continuation` remain conservative;
- no capability is graduated from implementation alone;
- PR9.2 is not merged.

## Capability graduation rule

Implementation, static support claims, deterministic CI, and review are still not live product evidence. Graduation requires all three attachment-dependent authenticated turns, exact write/readback evidence, canonical finality, conversation identity preservation, and the complete schema-9 recovery/deadline/clean-composer/cross-channel-exact/atomic-submit/session-identity/destructive-cleanup contract.

Until that bounded gate succeeds, no rich-input capability is claimed `AVAILABLE`.
