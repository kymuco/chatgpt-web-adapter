# CWA v0.4.0 — release candidate

Candidate review updated: **2026-10-30**. **Not yet tagged, published on GitHub Releases, or uploaded to PyPI.** The `CHANGELOG.md` date is staged for 2026-10-30; if the actual publication date differs, update it before tagging. Source evidence: `main` `9519d390` and pre-documentation candidate `a84bba9e` (CI 16/16). Reverify the final head and CI after documentation changes.

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

- Isolated experimental Qwen Web Python/CLI/Native Host and Windows-verified text/continuation/network streaming. Capability metadata now reports those four verified operations as AVAILABLE (#225); canonical readback, files, and other unproven features remain unpromoted.
- Experimental DeepSeek/Gemini conversational providers and separate module-only Google Translate / Gemini Notebook consumer capabilities.
- Stronger provider semantics, provenance, required-action observations, auth sync and release/installed-wheel packaging gates; other experimental provider surfaces remain explicit rather than forced into the ChatGPT API.

### Pre-release cleanup and package boundaries

- Integrated cleanup [#250](https://github.com/kymuco/chatgpt-web-adapter/pull/250) removed 21 historical files and a net 5,985 lines over 66 changed paths. It retired obsolete UI smoke and repeated Python live-acceptance runners, retaining schema8–28 read-only support validators, schema29 diagnostics, the active HTTP runtime and all packaged Chrome extension JavaScript.
- The built candidate still includes some historical diagnostic Python modules because they retain test/compatibility dependencies. Cleanup is not a claim that all research files have been removed.
- The exact candidate wheel and sdist passed metadata/release checks, and installed-wheel smoke passed on Windows/Linux Python 3.10/3.14. CI does not replace live-product compatibility evidence.

### Browser-owned and canonical-read hardening

- #233: current structural Send-button selection within guarded rich submission.
- #234: exact multiline text readback after asynchronous Composer render.
- #235: bounded clean, fresh, inactive new-chat Composer mount recovery.
- #236: narrowly gated cleanup after proven pre-submit failure without erasing an uncertain attachment fence.
- #232: bounded canonical browser-native HTTP 429 retry delays to the active read deadline (closes #168).
- #246: reject incomplete curl transfers even when response headers returned HTTP 200; preserve sanitized transport errors without an automatic retry.
- 2026-10-30 canonical-read fix: structured curl exit 28 allows bounded **read-only** `num_turns` step-down (20 → 10 → 5) on canonical GET, not repeat-send or guaranteed recovery.

These are code-level repairs with deterministic CI coverage; they do **not** certify current three-file browser-owned live success.

## Known limitations and outstanding release decision

1. **Browser-owned multi-file acceptance is an explicit v0.4.0 limitation, not a success claim.** The 2026-10-29 UI attempt visibly attached only one file and did not complete; its exact failure stage is unknown. Browser-owned remains secondary/`EXPERIMENTAL`. Historical [draft #211](https://github.com/kymuco/chatgpt-web-adapter/pull/211) must not be merged wholesale. Publishing requires an explicit maintainer decision accepting this documented limitation; never automatically replay an ambiguous turn.
2. **Browser-native canonical HTTP 500:** [draft #221](https://github.com/kymuco/chatgpt-web-adapter/pull/221) proposes a size step-down fallback but lacks proof that it fixes the original 500. Not included in this candidate.
3. **Auth, prompts and private protocols:** `BrowserlessHTTPClient.send()` does not inherit automatic browser auth sync from the legacy canonical reader. No automatic browser, provider or transport fallback; no automatic replay after an ambiguous send.
4. **Provider tiers:** Qwen, DeepSeek/Gemini, Translate and Notebook stay experimental and scoped. Qwen capability evidence from #225 is included; Linux Qwen [#217](https://github.com/kymuco/chatgpt-web-adapter/pull/217), Qwen CLI refactor [#223](https://github.com/kymuco/chatgpt-web-adapter/pull/223), unverified Qwen history [#226](https://github.com/kymuco/chatgpt-web-adapter/pull/226), and resumable history [#114](https://github.com/kymuco/chatgpt-web-adapter/issues/114) are deferred.

## Compatibility and package integrity

- Python 3.10–3.14; existing package/import names, stable CLI and public contracts retained.
- Four console scripts: `cwa`, `chatgpt-web-adapter`, `chatgpt-web-adapter-native-host`, `qwen-web-adapter-native-host`.
- Exact-wheel release smoke validates the installed `[browser]` extra, the primary root import `BrowserlessHTTPClient`, and the post-0.3 Direct HTTP / Deep Research / generated-image / governed-handoff imports. PEP 561 `py.typed` must exist in wheel, sdist and installed site-packages (#172); the marker does not imply all historical modules are strict-type-check clean. These are package-level checks, not a live-product compatibility guarantee.
- No automatic browser fallback, speculative challenge bypass, Headless Chromium transport, general provider router or new Work/agent authorization.

## Release verification still required

Before a `v0.4.0` tag or published GitHub release:

1. Confirm the **final** post-documentation candidate commit of Draft #238 and explicitly approve the release scope with browser-owned multi-file support unverified.
2. Recheck CI for that exact final head: Windows/Linux Python 3.10–3.14, wheel/sdist, release gate, and installed-wheel smoke (pre-documentation `a84bba9e` passed 16/16).
3. Confirm `pyproject.toml` version `0.4.0`, actual publication date in the `CHANGELOG.md` heading and eventual tag `v0.4.0` agree. The untagged candidate gate is not tagged-release verification.
4. Merge only after final review. Publish solely with separate explicit approval and then verify a clean PyPI-installed `0.4.0` distribution.

Until then, latest published package remains `v0.3.0` (2026-09-01).
