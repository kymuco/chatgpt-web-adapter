# Qwen browser isolation gate (PR #213)

Status: **INSTALLED WINDOWS QWEN SDK LIVE BASELINE VERIFIED — RELIABILITY
GAPS OPEN** (2026-10-15). The user and Codex ran Python SDK → isolated
Qwen bridge → Chrome → Qwen end-to-end *before* pushing `bec72b31`.
Normal ChatGPT/HDE CWA remains separate; later commits repaired the
release/package gate and added isolation regression tests.

## Observed evidence

- The user's shared CWA installation, also used by HDE/Kaguya, reported
  `CHATGPT_SUBMIT_NOT_OBSERVED:send_button_click` during a protected work request.
- The user restored `service_worker_runtime.js` and `manifest.json` from
  `origin/main`, redeployed the extension and confirmed that the ordinary
  ChatGPT transport worked again.
- This is strong rollback evidence implicating the shared extension deployment
  or its runtime coupling. It **does not isolate** one of the two modified files
  or prove that the Qwen provider JS itself directly caused the failure.
- Qwen browser previously produced `QWEN_POST_SUBMIT_START_UNOBSERVED`
  and an ambiguous observation after a Formula 1 prompt with
  `write=completion network=finished http=200`. The user's subsequent
  `--chat` attachment proved the latter prompt was stored, so NEVER
  blindly replay it. **User/Codex attributed these incidents to Qwen
  busy/high demand**; they should not be listed as independently established
  SDK Send or DOM defects. The SDK now provides an explicit overload-recovery
  command `/retry`, gated on Qwen's high-demand response and an enabled
  Regenerate button. The broad error signatures alone do not prove busy.

## Current source boundary

In PR #213 the production `manifest.json` and
`service_worker_runtime.js` are byte-identical to `main`.
Experimental `service_worker_qwen_provider.js` and
`service_worker_qwen_stream.js` remain in the source tree but are not imported
by the production extension. The production manifest does not grant Qwen host
permission. Therefore `qwen_sdk.py --transport browser` is **not enabled**
through the shared installed extension.

Preserve this quarantine. Do not re-enable Qwen by editing the production
service-worker import graph or running the normal
`install_native_messaging_host()` from a Qwen-enabled artifact.

## Why another Chrome profile alone is insufficient

The existing browser worker hardcodes
`com.kymuco.chatgpt_web_adapter` as its native host. The host writes a bridge
descriptor to the shared per-user `browser-native/bridge.json` path.
Two browser profiles connecting to the **same** native host identity and bridge
path can displace each other's descriptor and local request routing.
Different tabs/profiles are not an independent safety boundary unless the
native messaging name and state root are also separate.

## Independent experimental architecture

The branch now includes a dedicated Qwen extension/host implementation.
A separate Chrome profile is an optional additional safeguard, not a
substitute for native host and bridge isolation. The essential boundaries are:

1. A distinct unpacked-extension directory and dedicated extension identity.
   Never overwrite the production extension directory. The same Chrome profile
   can host two different extension identities, but switching profiles is
   appropriate for more conservative acceptance testing.
2. A distinct extension identity and native-messaging host name, with its
   allowlisted extension ID matching only that experimental extension.
3. An independent native host process and **independent descriptor/state
   directory**. No writes to the production
   `%LOCALAPPDATA%/chatgpt-web-adapter/browser-native` deployment, bridge,
   native-host registration, or browser runtime tab state.
4. Explicit diagnostics/read-only dry runs first. No background automated
   Qwen prompt replay; first authenticated turn requires its own opt-in.
5. An isolated, deterministic test of page-owned input and one Send attempt:
   check textarea focus, browser-generated input, button state, CDP request
   observation, network completion and DOM readback **separately**.
6. Stable finality and two-response feedback semantics. Neither the first
   streamed candidate nor the last DOM answer is automatically canonical.

## Acceptance protocol

- **Production invariant:** snapshot the ordinary CWA deployment identity,
  native host registration and state root before testing; compare after testing.
  No production file, bridge descriptor or Chrome profile mutation is allowed.
- **Static/CI gate:** verify isolation identifiers, host permissions, runtime
  imports, independent deployment paths and installer safeguards.
- **Offline integration gate:** simulate one Send, one ambiguous Send and
  a stale previous prompt. Any unconfirmed commit must remain fenced and
  must never be retried automatically.
- **Live Qwen baseline:** user-confirmed installed end-to-end text, SSE and
  `--chat` attach are already accepted. Busy incidents are diagnosed and the
  explicit `/retry` recovery is implemented. New probes should focus only
  on newly observed regressions, not repeat known overload scenarios or
  invent separate send/readback defects. If needed, measure
  `compose_ready → insertion → Send → POST → first fragment →
  SSE finality → DOM readback` without request bodies or credentials.
- **Production regression gate:** confirm ordinary ChatGPT/HDE remains healthy.
  If not, stop and restore the last known-good shared deployment.
- **Promotion:** do not merge experimental Qwen browser integration into
  the shared runtime merely because one Qwen turn succeeded. Prefer an
  independently maintained provider/extension until repeated isolated
  acceptance tests justify otherwise.

## Scope boundaries

The separate Qwen direct-HTTP experiment can continue without modifying the
production Chrome extension, but it has its own experimental auth/refresh and
completion semantics. A single successful HTTP generation is not proof of
long-term session renewal or product compatibility.

The independent extension/host code now exists. This document is still an
**acceptance gate**: the user's actual Windows SDK runs prove the installed
text/continuation/reattachment baseline. GitHub tests and those transcripts
still do not prove long-run reliability, correct two-response selection,
all future Qwen busy-UI variants or production HDE health under prolonged use.
  The `/retry` operation is implemented; no need to treat its absence as a
  remaining feature gap.
