# Qwen browser isolation gate (PR #213)

Status: **QUARANTINED — NOT ACCEPTED FOR PRODUCTION** (2026-10-15).

## Observed evidence

- The user's shared CWA installation, also used by HDE/Kaguya, reported
  `CHATGPT_SUBMIT_NOT_OBSERVED:send_button_click` during a protected work request.
- The user restored `service_worker_runtime.js` and `manifest.json` from
  `origin/main`, redeployed the extension and confirmed that the ordinary
  ChatGPT transport worked again.
- This is strong rollback evidence implicating the shared extension deployment
  or its runtime coupling. It **does not isolate** one of the two modified files
  or prove that the Qwen provider JS itself directly caused the failure.
- Separately, Qwen browser Send repeatedly failed with
  `QWEN_POST_SUBMIT_START_UNOBSERVED`, including an explicitly foreground tab.
  No authenticated live acceptance proof exists for the latest input changes.

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

## Required experimental architecture

Build a dedicated Qwen test deployment that has:

1. A distinct unpacked-extension build directory and a distinct Chrome
   `--user-data-dir`, never the production extension folder/profile.
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
- **Single live Qwen gate:** only after isolation is proven, send at most one
  user-authorized test prompt and collect timing/evidence for
  `compose_ready → text_inserted → commit_attempted → request_seen →
  first_answer_observed → finality`. No credentials or request bodies in logs.
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

This document is a gate and implementation specification, **not** a claim that
the experimental sidecar, isolated host or live Qwen tests have been built.
