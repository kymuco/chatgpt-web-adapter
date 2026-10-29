# Providers

_Last updated: 2026-10-29_

This document describes the provider-specific support surface on current `main`.

CWA does not assume that every provider exposes the same concepts. Provider capability
state and runtime support tier are evidence-backed independently.

## Shared provider contract

A provider runtime is inspected through:

```python
from chatgpt_web_adapter import product_provider_boundary

boundary = product_provider_boundary(runtime)
```

`ProductProviderBoundary` is metadata/validation over an existing runtime, not a
request router.

Schema 2 currently freezes:

```text
provider_id
product_semantics
transport

canonical_readback_required
canonical_interface

write_transport_interface = ProductWriteTransport
capability_model = ProductCapabilities
provenance_model = ProductExecutionProvenance

automatic_write_retry = false
fallback_transport = none
ambiguous_write_requires_reconciliation = true
incremental_observation_is_canonical_finality = false
```

## Support matrix

| Surface | ChatGPT | DeepSeek Web | Gemini Web |
| --- | --- | --- | --- |
| Provider id | `chatgpt` | `deepseek` | `gemini` |
| Product semantics | `ordinary-chatgpt` | `ordinary-deepseek` | `ordinary-gemini` |
| Transport | `browser-owned` (legacy SDK default) | `deepseek-web` | `gemini-web` |
| Support tier | **EXPERIMENTAL / secondary UI** | **EXPERIMENTAL** | **EXPERIMENTAL** |
| Text turns | AVAILABLE | AVAILABLE | AVAILABLE |
| New chat | AVAILABLE | AVAILABLE | AVAILABLE |
| Continuation | AVAILABLE | AVAILABLE | AVAILABLE |
| Canonical readback | AVAILABLE / required | UNIMPLEMENTED | UNIMPLEMENTED |
| Conversation attach/read/status | AVAILABLE | UNIMPLEMENTED | UNIMPLEMENTED |
| Streaming | AVAILABLE on proven paths | UNIMPLEMENTED | UNIMPLEMENTED |
| Images/files | Limited historic E2E; 2026-10-29 multi-file UI incomplete | UNIMPLEMENTED | UNIMPLEMENTED |
| Web search | AVAILABLE observation on proven path | UNKNOWN | UNKNOWN |
| Temporary chat | AVAILABLE text path | UNIMPLEMENTED | UNIMPLEMENTED |
| Model selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Reasoning selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Tools/connectors | Conservative / UNKNOWN overall | UNIMPLEMENTED | UNIMPLEMENTED |
| Multimodal continuation | AVAILABLE on proven path | UNIMPLEMENTED | UNIMPLEMENTED |

The table describes current `main`, not necessarily the latest published wheel.

### Qwen Web (isolated experimental provider)

Qwen is intentionally described separately from the shared-provider table above:
its browser worker runs in a **dedicated extension and native host** rather than
through production CWA. An installed Windows Python SDK session verified new chat,
multiple text turns, network SSE response delivery and cross-process `--chat`
reattachment. The explicit `/retry` operation is implemented for a confirmed
Qwen high-demand response; it is not automatic message replay. Browser model
selection, rich input and canonical/durable readback are not claimed.

For copyable, implementation-aligned setup and code examples, use
[**Qwen SDK — setup and reference examples**](qwen.md). Qwen Direct HTTP
remains experimental; one real generation was observed, but reliable repeated
generation, canonical finality and renewal are not independently proven.


## ChatGPT

For ChatGPT, the standalone `BrowserlessHTTPClient` is the **primary
public SDK** for operations with live HTTP proof (new chat, continuation,
streaming, attachments, Temporary Chat, canonical readback). It is root-exported
and has `PRIMARY_PRODUCTION` public surface classification. Its private web
protocol and auth requirements can still change. It is **not** one of the
`ChatGPTProductRuntime` transport choices and must not be conflated with
the historical `browserless-request` transport.

`ChatGPTProductRuntime` remains the secondary browser-owned UI runtime. The
older default remains for compatibility; its current transport support tier
is **EXPERIMENTAL** after a failed-to-complete 2026-10-29 multi-file test.
Do not retry any uncertain prior Send or silently switch transports.

Application boundary:

```text
ChatGPTProductRuntime
```

The default mutation transport is:

```text
browser-owned = EXPERIMENTAL (secondary UI; compatibility default)
```

The alternative direct-request transport is:

```text
browserless-request = EXPERIMENTAL
```

ChatGPT also has a canonical conversation/session plane. Successful turns can therefore
use canonical readback as completion authority where the runtime contract requires it.

HTTP and browser-owned capabilities are separately evidenced. On 2026-10-29,
Direct HTTP returned exact markers from three Markdown attachments, streamed
and passed independent canonical status/ID/text readback. The corresponding
browser-owned three-file submission remained incomplete. Requested model or
reasoning settings are not proof of actual server model selection.

## DeepSeek Web

Module:

```python
from chatgpt_web_adapter.deepseek_web import DeepSeekWebRuntime
```

Current proof:

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
```

Conversation identity uses a local opaque id mapped to the exact observed page route.

Completion evidence:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

This is intentionally weaker than ChatGPT canonical readback and is never relabeled as
canonical finality.

## Gemini Web

Module:

```python
from chatgpt_web_adapter.gemini_web import GeminiWebRuntime
```

Current proof:

```text
text new chat      AVAILABLE
text continuation  AVAILABLE
canonical readback UNIMPLEMENTED
support tier       EXPERIMENTAL
```

Conversation identity uses the same architectural model as DeepSeek: a local opaque id
bound to an exact observed product route, without hardcoding the provider's internal
conversation-id schema.

Completion evidence:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

## Qwen Web — experimental candidate

```python
from chatgpt_web_adapter.qwen_web import QwenWebRuntime
```

The Qwen browser adapter uses its **own experimental extension and Native
Messaging host**, targeting `https://chat.qwen.ai`. The shared CWA extension
and its ChatGPT/HDE Native Messaging bridge remain unchanged. The Qwen runtime
uses Qwen-specific
composer, send-button, answer-phase and stop-generation DOM evidence rather than
exporting credentials or reproducing Qwen's private HTTP protocol.

Text new-chat, multi-turn continuation, network-streamed responses and
`--chat` reattachment have **user-confirmed installed Windows SDK evidence**
from 2026-10-15. The advertised capability states remain `UNKNOWN` in the
current experimental metadata until separately reviewed/updated. This does
not imply absent live evidence: the user/Codex attributed earlier failing
turns to Qwen overload, with an explicit `/retry` recovery now implemented.
Advanced feature gaps remain. Canonical/durable answer finality is still not
generally proven.

An ambiguous result after potential submission requires reconciliation, never
an automatic retry. This experiment does not export Qwen tokens/cookies or
modify the separate experimental browserless HTTP client.

## Finality is provider-specific

The shared architecture does not require all providers to have the same finality plane.

```text
ChatGPT
→ canonical readback can prove durable completion

DeepSeek / Gemini
→ current proof observes stable page completion
→ canonical completion remains unproven
```

This distinction is intentional.

## Write uncertainty

All page-owned providers preserve:

```text
automatic_write_retry = false
fallback_transport = none
```

For DeepSeek/Gemini, once the click-capable submit evaluation may have executed,
uncertainty becomes reconciliation-required.

A caller must not interpret an ambiguous outcome as permission to replay the turn.

## Why provider-specific runtimes are module-only

DeepSeek/Gemini live acceptance proves that the current implementations work against
the observed product revisions.

It does **not** prove that:

- current DOM selectors are durable API;
- route behavior will never change;
- page finality can be upgraded to canonical finality;
- all visible features should be implemented;
- the provider is ready for root-package production support.

Therefore concrete runtimes remain module-only and experimental while the
provider-neutral boundary remains the stable public contract.

## Adding or promoting a provider

Do not add a provider only to increase provider count.

A new provider should be justified by a real consumer or by evidence that tests the
existing architecture.

Promotion requires stronger evidence than “a live turn worked once”. At minimum,
review:

- repeatable product behavior;
- capability scope;
- finality semantics;
- conversation identity;
- ambiguous-write behavior;
- support burden under product drift;
- deterministic regression coverage;
- whether public construction/selection is actually needed.

See [architecture.md](architecture.md) and
[engineering/pr15_56_provider_architecture_closure.md](engineering/pr15_56_provider_architecture_closure.md).

> **Shared CWA runtime quarantined (2026-10-15):** A production HDE/ChatGPT
> submit failure (`CHATGPT_SUBMIT_NOT_OBSERVED:send_button_click`) cleared
> after reverting the two shared Qwen extension modifications. This is a
> correlated rollback observation, not proof of a specific JavaScript collision.
> The separate Qwen extension and native host source now exist in PR #213,
> and the **installed Qwen SDK already passed a user-run text/continuation
> end-to-end baseline**. Intermittent reliability defects remain open.
> Qwen browser modules are **not imported** by the normal CWA service worker,
> and `chat.qwen.ai` is not included in its host permissions.
> The Qwen **browser CLI cannot use the quarantined shared extension**; it
> requires the independent Qwen installation. Do not re-add the Qwen imports or run the Qwen browser CLI against
> the HDE/Codexia production extension. The Qwen source and unit tests are
> retained for isolated development; experimental direct HTTP is separate.

## Qwen two transport experiment (PR #213)

The Qwen provider now offers explicit browser and HTTP modes through `QwenClient`.
Neither transport silently retries a possibly completed write or falls back to
the other transport. Both remain experimental; live basic browser operation
is user-confirmed but full reliability and advanced behaviors are not.

```python
from chatgpt_web_adapter.qwen_client import QwenClient

# Background Chrome tab using the separately installed Qwen extension and login.
browser = QwenClient(transport="browser")
reply = browser.send_text("Hello")

# Opt-in Qwen session import from the existing signed-in Chrome tab.
direct = QwenClient(transport="http")
direct.import_browser_auth()
reply = direct.send_text("Hello over HTTPS")
print(reply.text)

# Subsequent process launches can load the already imported credentials:
direct = QwenClient(transport="http")
reply = direct.send_text("New Qwen HTTPS conversation")
```

The session import is explicit and scoped to Qwen. It reads the access token
from Qwen page storage and Qwen-origin cookies from Chrome CDP; the native
bridge does not read or export Google account credentials. The credentials
are written outside Git to `%LOCALAPPDATA%/chatgpt-web-adapter/qwen_auth.dat`.
On Windows, the file is encrypted with user-scoped DPAPI; on POSIX,
the file uses mode `0600`.

Direct HTTP uses the `curl` executable and Qwen's private `/api/v2/chats/new` and
`/api/v2/chat/completions` endpoints; this is not an official stable API.
Token refresh is never guessed: callers must supply a separately verified
`refresh_path`. Without it, an expiry hint does not trigger renewal; the client
attempts the operation once and reports the server response.
Neither HTTP generation nor browser completion can safely auto-replay an
ambiguous write. `QwenHttpConversation` can explicitly carry chat and parent
ids between HTTP calls; cross-transport migration is not established.

Authentication export has been verified on the user machine. A direct generation
with `qwen3.7-plus` succeeded once; repeated operation and independent token
renewal remain unverified.

## Recommended Qwen usage

Install the independent Qwen native extension (see
[installation instructions](engineering/qwen_native_setup.md)), sign in to
Qwen, and keep an authenticated Qwen session. The SDK reuses an empty Qwen tab or
creates a background tab for a new conversation. Choose the model
and thinking mode in the Qwen interface. An existing empty tab preserves your selected model; a newly created tab uses
Qwen's site defaults. Tabs are not activated automatically.

```sh
python qwen_sdk.py "Hello"
python qwen_sdk.py
# Explicit diagnostic mode: make Qwen's tab active before sending.
python qwen_sdk.py --foreground-tab --auto-confirm-age --birth-year 2000
```

For comparing active and inactive tabs, `--foreground-tab` is an **opt-in
diagnostic mode**, **not** a proven remedy for unobserved Qwen POSTs. It activates Qwen's browser tab
(and visibly changes the currently selected tab) before the single Send click.
The ordinary browser mode remains in the background and unchanged; neither
mode auto-retries a potentially submitted prompt. A successful foreground run alone does not prove hidden-tab lifecycle effects;
the earlier failure was also reproduced in a visible tab. It is not a
guarantee of Qwen responsiveness. The visible-tab failure was reproduced
before the separate-bridge update; the user later confirmed basic operation
without requiring the diagnostic flag.

The default transport is `browser`. Interactive mode preserves the returned
conversation for subsequent messages; `/exit` ends the session. A new process starts a new SDK conversation. Existing conversations are never
replaced to start a new one. Continuation requires its original tab to remain open. Keep the selected tab open and avoid editing its composer
while a turn is running.

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient()  # browser
first = client.send_text("Remember ORCHID")
second = client.send_text("What word?", conversation=first.conversation)
print(second.text)
```

Qwen's browser composer input uses one Chrome DevTools Protocol
`Input.insertText` operation after the empty textarea is focused and checked.
This replaces synthetic `textarea.value` + `InputEvent` writes, which could
leave Qwen's internal React composer state stale: text remained visible but
`control.click()` produced no turn. The Send control is still clicked exactly
once. If a previous ambiguous prompt remains in the textarea, the SDK stops
with `QWEN_PRE_SUBMIT_COMPOSER_NOT_EMPTY` instead of overwriting it; inspect
and reconcile the previous turn on Qwen before clearing the field manually.
The focus/input path was checked both in the background CDP diagnostic and
by successful user-run Python SDK turns through the separate native extension.
The historical failing turns were attributed by the user and Codex to
Qwen high demand; the SDK implements an explicit gated `/retry` command.

In `--stream network` mode, the browser transport returns the verified SSE
answer reconstructed from Qwen's own stream; this is the recommended mode for
completeness. The default `--stream dom` remains a **heuristic fallback**:
a hidden-tab DOM can be incomplete even after SSE has finished. The optional `on_text` callback receives full answer-text snapshots approximately
every 250 ms while the DOM changes. Replace the displayed answer with each
snapshot; do not concatenate them. Thinking text is excluded. The CLI displays
updates automatically. These are page updates, not individual model tokens. Model selection through SDK
arguments, attachments and temporary-chat controls are not implemented for this
transport. Login or verification must be completed on the Qwen site. Failed or
ambiguous generations are never automatically replayed.

**User-run installed Qwen SDK (2026-10-15):** `--stream network`
successfully delivered `привет`, a complete count from **1 to 100**, and a
third reply in one conversation. Another turn (Formula 1) showed
`POST_SUBMIT_UI_UNOBSERVED_AFTER_WRITE_OR_NAVIGATION` despite
`write=completion network=finished http=200`. After restarting the CLI and
using `--chat e7f86959-2bf8-4803-a244-ba19cd8e3b08`, Qwen listed the
previous questions **including** the Formula 1 prompt. Thus message
persistence succeeded even though SDK response observation failed. A separate
first-send attempt failed with `write=none network=unobserved`. The user
and Codex attributed these historical failures to Qwen's busy/high-demand
state; the error strings alone do not identify that cause, but do not
establish a separate SDK defect either. `/retry` is implemented as a
one-shot, user-invoked **Regenerate** of the same response, gated on Qwen's
visible high-demand message. Basic end-to-end operation is confirmed;
dual-response handling and accurate TTFT benchmarks remain open.
No automatic replay is permitted.

### Experimental direct HTTP

```sh
python qwen_sdk.py --import-auth
python qwen_sdk.py --transport http "Hello"
```

Auth import never sends a message or opens a tab. It may reload an existing Qwen
tab if its token is near expiry. Credentials are stored outside the repository.
HTTP is an explicit experimental option: importing valid credentials does not
guarantee generation access, and there is no automatic browser fallback.

### Qwen HTTP with periodic browser session snapshots (experimental)

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="http", model="qwen3.7-plus",
                    browser_session_refresh=True, session_refresh_interval=300)
response = client.send_text("Hello", on_token=print)
```

Before a send, the opt-in mode imports the existing Qwen tab session when the
interval expires or imported expiry is near. If the page token is near expiry,
the extension reloads the existing tab and waits up to 15 seconds for a different,
unexpired token. This renewal branch still needs live verification. Keep an authenticated Qwen tab
available; if it needs login or verification, complete that on the site. The
HTTP client never sends a prompt through the browser or replays a failed write.
`refresh_browser_auth()` explicitly refreshes the snapshot while preserving the
HTTP conversation parent. Default HTTP mode never contacts the browser.

Snapshots preserve cookies and browser User-Agent in the existing private auth
store. This does not implement Aliyun CAPTCHA solving or guarantee that imported
credentials satisfy per-request WAF checks. Live standalone HTTP generation has
passed once, but subsequent probes received `FAIL_SYS_USER_VALIDATE`; sustained
operation and independent token refresh are still unverified.

Live check on 2026-10-15: the installed extension exported an unexpired token
and 19 cookies, but the first direct chat-creation request returned HTTP 200
with HTML instead of JSON. No completion was sent and the series stopped.
Refreshing account credentials alone therefore did not establish stable HTTP
access; there is no successful TTFT measurement for this run.

### Controlled browser/HTTP comparison (2026-10-15)

A fresh browser chat returned `QWEN_COMPARE_OK`. With the same captured account
session, direct chat creation failed with the SDK headers, both for a generated
`chatId` and an empty `chatId`. The SDK now matches the observed empty value.
Adding the ordinary application headers (`Accept`, `Version`, `source`,
`Timezone`, `X-Request-Id`) allowed creation; changing only `Accept` did not.
The individual necessary headers have not been isolated. Captured values should
not be treated as permanent defaults or shipped as authentication fixtures.

Two separate direct generations, each in a newly created chat, returned
`FAIL_SYS_USER_VALIDATE`: one with ordinary browser request headers and one
also carrying the captured `bx-*` headers. No failed generation was replayed.
The browser completion used HTTP/1.1 and received `text/event-stream`; the
completion body had the same top-level/message fields and feature configuration
as the SDK. This rules out a simple HTTP/2 requirement or missing body field in
this sample, but does not identify the exact verification dependency. Stable
browserless generation remains unsupported by the live evidence.

Browser completion latency: after observing generation and then disappearance of
the Stop control, the adapter waits 500 ms of unchanged answer text and idle UI
(poll interval 250 ms). Resumed generation resets that wait. If generation was
never observed, the conservative 9-second text-stability fallback remains.
This is DOM completion detection, not token streaming or server finality.

```python
client = QwenClient()
reply = client.send_text("Explain briefly", on_text=lambda text: print(repr(text)))
# reply.text is the final answer; partial snapshots do not prove completion.
```

### Age dialog

`QwenClient(auto_confirm_age=True, birth_year=2000)` selects the configured birth
year and clicks Continue once in Qwen's age dialog, before sending the message.
Use your actual year. The configurable default is 2000, matching the site's
initial selection; automatic confirmation is disabled unless explicitly enabled.
CLI: `python qwen_sdk.py --auto-confirm-age --birth-year 2000`.
Without opt-in the SDK reports `QWEN_AGE_CONFIRMATION_REQUIRED` instead of waiting
for the blocked composer. This does not handle CAPTCHA or other dialogs.

### Browser network streaming (experimental)

`client.send_text("Hello", on_token=lambda delta: print(delta, end="", flush=True))`
uses Chrome `Network.streamResourceContent` to observe the site's own completion
SSE request. It emits answer-phase content deltas, excluding thinking summaries.
Chunks can contain multiple model tokens. No direct HTTP generation is issued.
The final response still uses the page completion/route checks. Missing stream
support or incomplete SSE finality raises an error without resending the prompt
or silently substituting DOM snapshots. Partial output may precede an error.

CLI: `python qwen_sdk.py --stream network`. The default `--stream dom` remains
available. Network streaming is both unit-tested and **live-verified by the
user** on the installed Qwen SDK (including a complete 1–100 answer).
No reliable latency benchmark has been established yet.
