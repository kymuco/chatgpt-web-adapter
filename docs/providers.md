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

Direct HTTP uses `urllib` and Qwen's private `/api/v2/chats/new` and
`/api/v2/chat/completions` endpoints; this is not an official stable API.
Token refresh is never guessed: callers must supply a separately verified
`refresh_path`, and expired credentials without it fail before sending.
Neither HTTP generation nor browser completion can safely auto-replay an
ambiguous write. `QwenHttpConversation` can explicitly carry chat and parent
ids between HTTP calls; cross-transport migration is not established.

Authentication export, model identifiers, Qwen login refresh and live
generation behavior still need user-machine verification.

## Normal usage (no automated probes)

Run `python qwen_sdk.py --import-auth` only once with an already signed-in Qwen tab.
This operation never sends a chat message or opens a new tab. Thereafter
`python qwen_sdk.py "Your message"` uses direct HTTPS without Chrome.

`python qwen_sdk.py --transport browser "Your message"` reuses **only** an
already-open new Qwen chat tab. The SDK never opens, navigates, or activates
Chrome tabs for Qwen. Qwen's account age/onboarding verification must be
completed in Qwen by the account holder; CWA neither bypasses it nor repeatedly
opens the verification page. If no suitable tab exists, it fails clearly.

The old `scripts/prove_qwen_dual_transport.py` live-probe has been removed.


### Optional, browserless Qwen Web client

Qwen Web's unofficial v2 endpoints may return a 200-HTML challenge instead of JSON
even when Chrome auth is imported: the consumer website uses dynamic WAF headers
in addition to the bearer token and cookie jar. Importing only a token does not
prove that `--transport http` will work.

To use an **explicit, optional, third-party** Python HTTP implementation:

```powershell
python -m pip install qwen-reverse==0.1.6
python .\qwen_sdk.py --transport reverse "Привет!"
python .\qwen_sdk.py --transport reverse
```

`reverse` uses the previously saved Qwen account token, remains browserless,
and sends only the user's messages. The experimental `http` transport is left
unchanged; no automatic fallback from `http` to `reverse` is performed.
The optional third-party library is unaffiliated with Qwen and its behaviour
has not been live-verified with this user's account. Review its source and
dependencies before installing it. Browser/account challenges must be handled
by the user through the provider's normal verification flow; the SDK does not
open verification tabs or complete age checks.
