# PR9.2 — Full Product Input Expansion

Status: **implementation in progress / live graduation pending**

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

The existing proven service-worker chain is not rewritten. The packaged extension
loads `service_worker_rich_input_pr9_2.js`, which imports the previous final worker
and wraps only `executeNativeTurn` for turns carrying `attachmentPaths`. Text-only
turns delegate directly to the previous worker with no attachment argument.

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
