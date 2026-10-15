# Providers

_Last updated: 2026-10-14_

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
| Transport | `browser-owned` (default) | `deepseek-web` | `gemini-web` |
| Support tier | **PRODUCTION** | **EXPERIMENTAL** | **EXPERIMENTAL** |
| Text turns | AVAILABLE | AVAILABLE | AVAILABLE |
| New chat | AVAILABLE | AVAILABLE | AVAILABLE |
| Continuation | AVAILABLE | AVAILABLE | AVAILABLE |
| Canonical readback | AVAILABLE / required | UNIMPLEMENTED | UNIMPLEMENTED |
| Conversation attach/read/status | AVAILABLE | UNIMPLEMENTED | UNIMPLEMENTED |
| Streaming | AVAILABLE on proven paths | UNIMPLEMENTED | UNIMPLEMENTED |
| Images/files | AVAILABLE on proven paths | UNIMPLEMENTED | UNIMPLEMENTED |
| Web search | AVAILABLE observation on proven path | UNKNOWN | UNKNOWN |
| Temporary chat | AVAILABLE text path | UNIMPLEMENTED | UNIMPLEMENTED |
| Model selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Reasoning selection | Evidence-backed | UNKNOWN | UNKNOWN |
| Tools/connectors | Conservative / UNKNOWN overall | UNIMPLEMENTED | UNIMPLEMENTED |
| Multimodal continuation | AVAILABLE on proven path | UNIMPLEMENTED | UNIMPLEMENTED |

The table describes current `main`, not necessarily the latest published wheel.

## ChatGPT

ChatGPT is the mature/default provider.

Application boundary:

```text
ChatGPTProductRuntime
```

The default mutation transport is:

```text
browser-owned = PRODUCTION
```

The alternative direct-request transport is:

```text
browserless-request = EXPERIMENTAL
```

ChatGPT also has a canonical conversation/session plane. Successful turns can therefore
use canonical readback as completion authority where the runtime contract requires it.

The mature ChatGPT surface includes evidence-backed rich input, model profiles,
Temporary Chat, streaming/finality handling and structured product observations.

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

The Qwen adapter runs through the **existing CWA Chrome extension** and Native
Messaging bridge, targeting `https://chat.qwen.ai`. It uses Qwen-specific
composer, send-button, answer-phase and stop-generation DOM evidence rather than
exporting credentials or reproducing Qwen's private HTTP protocol.

Text, new chat and continuation are implemented **but not yet live-verified** on
an authenticated Chrome session. The advertised capability states remain
`UNKNOWN` until a successful live acceptance gate; all other advanced
capabilities remain unimplemented or unknown. Canonical finality is unproven.

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

## Qwen two transport experiment (PR #213)

The Qwen provider now offers explicit browser and HTTP modes through `QwenClient`.
Neither transport silently retries a possibly completed write or falls back to
the other transport. Both remain experimental pending authenticated live proof.

```python
from chatgpt_web_adapter.qwen_client import QwenClient

# Background Chrome tab using the existing CWA extension and Qwen login.
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

Keep Chrome running with CWA connected, sign in to Qwen, and keep an authenticated Qwen session. The SDK reuses an empty Qwen tab or
creates a background tab for a new conversation. Choose the model
and thinking mode in the Qwen interface. An existing empty tab preserves your selected model; a newly created tab uses
Qwen's site defaults. Tabs are not activated automatically.

```sh
python qwen_sdk.py "Hello"
python qwen_sdk.py
```

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

The browser transport returns the complete answer after observing completion in
the page. The optional `on_text` callback receives full answer-text snapshots approximately
every 250 ms while the DOM changes. Replace the displayed answer with each
snapshot; do not concatenate them. Thinking text is excluded. The CLI displays
updates automatically. These are page updates, not individual model tokens. Model selection through SDK
arguments, attachments and temporary-chat controls are not implemented for this
transport. Login or verification must be completed on the Qwen site. Failed or
ambiguous generations are never automatically replayed.

Live SDK verification: a new chat returned `FIRST_OK` and continuation returned
`ORCHID` in the same conversation. Total call durations were 20.68 and 14.57
seconds, including the page completion wait; these are not TTFT measurements.

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
available. Network streaming is implemented and unit-tested, but live validation
requires reloading the updated extension; no latency claim is established yet.
