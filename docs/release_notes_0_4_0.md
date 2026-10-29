# CWA v0.4.0 — release candidate

Candidate date: 2026-10-29. **Not yet tagged, published on GitHub Releases, or uploaded to PyPI.** The release date in `CHANGELOG.md` must match the actual publication decision.

CWA 0.4.0 packages the post-0.3 runtime capabilities and promotes the
live-verified Direct HTTP SDK to the primary public ChatGPT API. This does not
make it an official API or guarantee that a private consumer-web protocol
will remain unchanged.

## Highlights

### ChatGPT Direct HTTP — primary SDK for live-verified operations

The existing opt-in `BrowserlessHTTPClient` provides ChatGPT ordinary new-chat and continuation, streaming, attachment upload, Temporary Chat, explicit requested model and reasoning effort, and canonical conversation readback without controlling a Chrome tab. It is the **PRIMARY_PRODUCTION** public ChatGPT SDK for operations backed by
live evidence, but the consumer web protocol can still change.

`assemble_product_runtime()` continues to select browser-owned by default
for backwards compatibility, while that UI transport is reclassified
**EXPERIMENTAL** after an incomplete multi-file E2E. It is now positioned as an **explicitly selected UI alternative**, not an automatic fallback. No Headless Chromium backend, transport router, or automatic replay of an ambiguous write is introduced.

A Windows user-run E2E on 2026-10-29 against source `main` `0e330c5e` exercised exactly one Direct HTTP send, three distinct Markdown attachments, seven prompt lines and two streaming chunks; the response reproduced markers found only inside each attachment. A separate canonical GET reported `completed` and matched the user text, assistant text and assistant message ID. GPT-6 with High effort was **requested**, not independently attested by the server. This specific successful test is not a reliability or protocol-stability guarantee.

### Deep Research and generated images

- Experimental opt-in Deep Research launch from the Direct HTTP SDK and read-only report/status retrieval (#227/#228). An earlier user-run session produced a real research flow and completed 53,965-character report without a duplicate send.
- Experimental `get_generated_images()` read-only correlation between canonical generated-image activity and ready conversation-owned file records (#229).
- Existing governed `handoff_generated_artifact(...)` accepts one caller-specified conversation-owned artifact, requires an explicit destination, checks bytes/integrity and disallows overwrite unless explicitly requested. Previously proven TXT and PNG downloads do not establish arbitrary attachment or sandbox-link support.

### Provider and runtime expansion since v0.3.0

- Isolated experimental Qwen Web Python/CLI/Native Host and Windows-verified text/continuation/network streaming.
- Experimental DeepSeek/Gemini conversational providers and separate module-only Google Translate / Gemini Notebook consumer capabilities.
- Stronger provider semantics, provenance, required-action observations, auth sync and release/installed-wheel packaging gates; other experimental provider surfaces remain explicit rather than forced into the ChatGPT API.

### Browser-owned and canonical-read hardening

- #233: current structural Send-button selection within guarded rich submission.
- #234: exact multiline text readback after asynchronous Composer render.
- #235: bounded clean, fresh, inactive new-chat Composer mount recovery.
- #236: narrowly gated cleanup after proven pre-submit failure without erasing an uncertain attachment fence.
- #232: bounded canonical browser-native HTTP 429 retry delays to the active read deadline (closes #168).

These are code-level repairs with deterministic CI coverage; they do **not** certify current three-file browser-owned live success.

## Known limitations and outstanding release decision

1. **Browser-owned rich-input live acceptance remains incomplete.** On 2026-10-29 the fresh multi-file UI test visibly attached only one file and remained pending. The exact failure stage was not established. The historical [draft #211](https://github.com/kymuco/chatgpt-web-adapter/pull/211) must not be merged wholesale; the operator must explicitly accept a scoped known limitation or require an independent repair before final publication. Never retry the ambiguous previous turn automatically.
2. **Browser-native canonical HTTP 500:** [draft #221](https://github.com/kymuco/chatgpt-web-adapter/pull/221) proposes a size step-down fallback but lacks proof that it fixes the original 500. Not included in this candidate.
3. **Auth, prompts and private protocols:** `BrowserlessHTTPClient.send()` does not inherit automatic browser auth sync from the legacy canonical reader. No automatic browser, provider or transport fallback; no automatic replay after an ambiguous send.
4. **Provider tiers:** Qwen, DeepSeek/Gemini, Translate and Notebook stay experimental and scoped. Linux Qwen [#217](https://github.com/kymuco/chatgpt-web-adapter/pull/217), Qwen [#223/#225/#226](https://github.com/kymuco/chatgpt-web-adapter/pulls), and typing/history [#172](https://github.com/kymuco/chatgpt-web-adapter/issues/172)/[#114](https://github.com/kymuco/chatgpt-web-adapter/issues/114) are outside v0.4.0.

## Compatibility and package integrity

- Python 3.10–3.14; existing package/import names, stable CLI and public contracts retained.
- Four console scripts: `cwa`, `chatgpt-web-adapter`, `chatgpt-web-adapter-native-host`, `qwen-web-adapter-native-host`.
- Exact-wheel release smoke validates the installed `[browser]` extra and the post-0.3 Direct HTTP / Deep Research / generated-image / governed-handoff imports. These are package-level checks, not a live-product compatibility guarantee.
- No automatic browser fallback, speculative challenge bypass, Headless Chromium transport, general provider router or new Work/agent authorization.

## Release verification still required

Before a `v0.4.0` tag or published GitHub release:

1. Confirm the exact candidate commit and that the browser-owned known limitation has been explicitly dispositioned.
2. Obtain green GitHub CI across Windows/Linux Python 3.10–3.14, build, release gate and exact installed-wheel smoke.
3. Confirm `pyproject.toml` `0.4.0`, dated `CHANGELOG.md` heading and eventual tag `v0.4.0` agree; adjust date if necessary.
4. Publish only with a separate explicit approval, then verify the actual PyPI-installed `0.4.0` distribution.

Until then, latest published package remains `v0.3.0` (2026-09-01).
