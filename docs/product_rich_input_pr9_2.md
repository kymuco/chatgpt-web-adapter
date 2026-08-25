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
execution-local media scope
        |
        +-- path inputs -> validated absolute local paths
        |
        +-- bytes inputs -> private short-lived temp files
        |
        v
Native Messaging: paths only, never attachment bytes
        |
        v
PR9.2 extension overlay
        |
        v
CDP DOM.setFileInputFiles on official ChatGPT page
        |
        v
official page owns upload + protected conversation write
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

- No file bytes are serialized through Native Messaging.
- Local paths are validated before delegation and are not emitted in product events.
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

## Authenticated live gate

`product_rich_input_live_gate_pr9_2` implements the bounded graduation gate. Before
any product write it performs a no-write extension support probe that must prove:

- PR9.2 rich-input schema `1` is loaded by the connected extension;
- the staging primitive is `DOM.setFileInputFiles`;
- Native Messaging does not carry attachment bytes;
- the official page owns upload and the protected write;
- automatic write retry is disabled;
- fallback transport is absent;
- the support probe itself performed no write.

The live phase then has an exact budget of **three** product writes using generated,
deterministic fixtures:

1. PNG image + text in a new durable chat;
2. general `.txt` file + text in another new durable chat;
3. file + text continuation on the first durable conversation.

Every write must produce exactly one browser-native write event and exactly one
canonical readback event, both reporting attachment count `1`. The returned
execution must prove `CANONICAL_READBACK` finality and preserve the expected
conversation identity for the continuation.

The gate is intentionally opt-in because it performs real authenticated product
writes:

```bash
python -m chatgpt_web_adapter.product_rich_input_live_gate_pr9_2 \
  --acknowledge-live-writes
```

A successful command prints a JSON report with `ok: true`, `write_attempts: 3`,
`write_completions: 3`, per-turn identity/finality evidence, and no file contents.

## Capability graduation rule

Implementation presence is not live product evidence. `images`, `files`, and
`multimodal_continuation` must not be promoted to `AVAILABLE` solely because the
code and deterministic tests pass.

Graduation requires bounded authenticated browser-owned live evidence for at least:

1. one image + text new-chat turn;
2. one general file + text turn;
3. one multimodal continuation on an existing durable conversation;
4. canonical final assistant readback after each write;
5. exact attachment-count observation with no hidden fallback or automatic retry.

Until that live gate succeeds, existing capability metadata remains conservative.
