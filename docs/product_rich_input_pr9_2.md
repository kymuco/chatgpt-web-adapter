# PR9.2 — Full Product Input Expansion

Status: **browser-owned normal-turn implementation complete / authenticated live graduation pending**

PR9.2 expands `ChatGPTProductRuntime` from text-only input to images, files, and
multimodal continuation without weakening the frozen PR9.0 browser-owned production
boundary or the PR9.1 browserless challenge boundary.

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
durable local fence + browser-session runtime identity
        |
        v
DOM.setFileInputFiles on official ChatGPT page
        |
        v
stable page-owned composer attachment evidence
        |
        v
Send readiness
        |
        v
ONE page task:
  absolute page deadline check
  + final attachment evidence validation
  + Send button validation
  + button.click()
        |
        v
Network.requestWillBeSent proves protected conversation write
        |
        v
existing browser-owned completion + canonical assistant readback
```

The packaged extension keeps the historical PR8.7 `0.1.13` manifest entrypoint.
After the full prior worker chain is assembled, PR9.2 loads, in order:

1. `service_worker_rich_input_pr9_2.js`;
2. `service_worker_rich_input_deadline_repair_pr9_2.js`;
3. `service_worker_rich_input_closure_repair_pr9_2.js`;
4. `service_worker_rich_input_schema7_repair_pr9_2.js`.

The schema-7 overlay is loaded last and changes authority only while a rich-input
context is active. Text-only turns continue through the historical product path.

## Input and transport boundary

- The existing public `MediaItem` contract remains compatible with local paths,
  bytes/bytearray, base64 `data:` URIs, HTTP(S) URLs, and `(source, filename)`.
- Non-path inputs are materialized before browser delegation.
- Native Messaging carries only validated local paths; attachment bytes never cross
  the bridge.
- `media=[]` is text-only.
- Browserless rich input fails before write.
- Temporary Chat rich input fails before write until independently characterized.
- Injected/custom/subclassed browser-owned transports cannot gain rich-input
  authority merely by using the `browser-owned` transport identity.
- A rich custom provider result must confirm the exact requested attachment count.
- No browserless fallback, challenge bypass, protected-request reconstruction, or
  automatic write retry is introduced.

## Recovery and one total deadline

Attachment staging occurs only after PR8.11 stale-UI recovery, so an authorized
reload cannot silently erase an already-selected file.

One outer rich-turn deadline governs recovery/reload, runtime-tab waits, staging,
protected submission, post-submit observation, and cleanup. Earlier repair layers
also close historical mouse-to-Enter and Enter-key outcome ambiguities. Raw CDP
`Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` are not protected-submit
authority for rich turns.

## Page-owned attachment evidence

`DOM.setFileInputFiles` path count is not evidence that ChatGPT accepted an
attachment. PR9.2 waits for stable `PAGE_OWNED_COMPOSER_ATTACHMENT_STATE` matching
every expected basename. Explicit upload/attachment rejection fails the turn.

An early evidence check rejects already-bad state before waiting for Send readiness.
The final evidence check is stronger: in schema 7 it executes **inside the same
synchronous page-side expression as `button.click()`**. There is no second CDP
command and therefore no page-task scheduling window between the final attachment
validation and the protected click.

The protected primitive is:

`PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`

The page expression checks an absolute deadline before validation and again before
clicking. A Runtime.evaluate command delivered after that page deadline cannot
produce a late write.

## Post-click outcome and response-loss boundary

A debugger command that can execute `button.click()` is not awaited for its CDP
acknowledgement. Waiting for that acknowledgement could report a local timeout after
the page had already submitted the write.

Instead, before submission the existing browser-owned page runtime has already
installed its Network listener. Schema 7 reserves at least the normal submit
observation window inside the outer deadline, dispatches the page-side atomic
validate+click expression, and then relies on the existing
`Network.requestWillBeSent` observation of the protected conversation POST as the
first post-submit proof. No retry follows a missing observation.

Current support claims are therefore:

- `postClickDebuggerAckRequired=false`;
- `protectedSubmitOutcomeProof=NETWORK_REQUEST_OBSERVATION`;
- a bounded submit-observation reserve is required before dispatch.

Canonical assistant readback remains the final completion authority after the
browser-owned write has been observed.

## Durable stale-composer fence and tab identity

Selecting a file mutates persistent page/composer state. Before
`DOM.setFileInputFiles` may select any file, PR9.2 persists:

- a durable fence in `chrome.storage.local` containing the runtime tab ID and a
  random runtime identity;
- the matching runtime identity in `chrome.storage.session`.

The local fence survives Manifest V3 worker suspension/restart and remains the
safety authority. Session storage is used only as destructive-cleanup authority: it
survives worker suspension within the browser session but does not authorize a tab
across a browser restart.

Clearing `input.files` is never accepted as composer cleanup proof. A later prewrite
may close the fenced runtime tab only when all of the following are proven under the
remaining deadline:

1. the numeric tab still exists and is a ChatGPT tab;
2. it is still the currently stored extension runtime tab;
3. the durable local fence contains a valid runtime identity for that tab;
4. browser-session identity exists for the same tab;
5. the session and durable runtime identities match exactly.

Only then may the extension remove the tab and separately prove its absence.
`RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED` remains the only destructive cleanup
proof that permits fence retirement.

If the numeric tab ID now points outside ChatGPT, the old ChatGPT composer is absent
and the candidate is never closed. If a still-live ChatGPT candidate has a missing,
mismatched, or otherwise unproven runtime identity—including after a browser restart
where session identity is unavailable—the extension **does not close it and does not
clear the durable fence**. The next write fails closed instead of risking destruction
of a user tab or stale attachment reuse.

The existing `storage` permission is reused; PR9.2 does not change extension identity
or version.

## Schema-7 zero-write support gate

Before any authenticated write, `product_rich_input_live_gate_pr9_2` performs a
zero-write support probe. The installed extension must report schema 7 and prove the
complete current contract, including:

- `DOM.setFileInputFiles` staging and Native Messaging path-only transport;
- official-page upload and protected-write ownership;
- recovery before staging;
- durable stale-attachment fencing across worker restart;
- one total rich-turn deadline;
- deadline-bounded cleanup and fence retention;
- page-owned attachment evidence stable across at least two polls;
- rich raw-CDP Input and Enter fallback disabled;
- atomic final attachment validation + Send click in one page task;
- protected primitive exactly
  `PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK`;
- late page execution blocked by the absolute page deadline;
- post-click CDP acknowledgement not required;
- protected-submit outcome proved by `NETWORK_REQUEST_OBSERVATION`;
- sufficient submit-observation reserve before dispatch;
- destructive cleanup requires browser-session runtime identity;
- identity mismatch never closes a tab and fails closed;
- unproven identity fails closed;
- no automatic retry, no fallback transport, and no write by the support probe.

Schema 6 and earlier overlays fail the current gate. An intermediate schema-7 build
that does not expose the final identity-mismatch fail-closed claim also fails the
current gate.

## Bounded authenticated live evidence

The live phase is deliberately opt-in and has an exact budget of **three** real
product writes:

1. image + text new chat using a generated `BLUE | RED | GREEN` image fixture;
2. general file + text new chat using a hidden `EVIDENCE:` marker;
3. multimodal continuation using a distinct newly attached hidden marker.

The expected answers are absent from the prompts. Every turn must therefore depend
on attachment content, and every write must produce exactly one browser-native write
event and one canonical readback event with attachment count `1`. The continuation
must preserve conversation identity, and completion must be proven through
`CANONICAL_READBACK`.

The gate is intentionally explicit because it performs authenticated writes:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_pr9_2 \
  --acknowledge-live-writes
```

## Capability graduation rule

Implementation and deterministic CI are not live product evidence. `images`,
`files`, and `multimodal_continuation` remain conservative until the bounded
schema-7 authenticated gate succeeds.

Graduation requires all three attachment-dependent live turns, exact write/readback
evidence, canonical finality, and the current schema-7 recovery/deadline/atomic
submit/session-identity safety contract. Until then no rich-input capability is
claimed `AVAILABLE` from implementation alone.
