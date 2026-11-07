# Qwen Web SDK — setup and reference examples

> **Want only Qwen running in a terminal?** Follow the shorter **[Qwen-only quickstart](../QWEN.md)**. It includes first-time Chrome extension setup and the exact one-command CLI launch: `python .\qwen_sdk.py --stream network` (from the repository root). The full reference continues below.
>
> **На русском:** [быстрый старт Qwen для Windows](../QWEN.ru.md) — полная инструкция по установке расширения и запуску нашего CLI.

CWA's **Qwen Web adapter** exposes the signed-in [chat.qwen.ai](https://chat.qwen.ai/) product through a Python SDK and CLI. It is an **experimental provider**, not the official Qwen API and not the default ChatGPT/HDE runtime.

This page documents the implementation on `main` after PR #213. Examples marked **verified** match successful user-run Windows SDK sessions on 2026-10-15; other examples are supported by the source and deterministic tests, but are **not** claims of successful live execution under every Qwen site condition.

> [!IMPORTANT]
> Qwen has its **own Chrome extension, Native Messaging host, and bridge state**. Do not install Qwen into the production ChatGPT/HDE extension or replace its `browser-native` deployment.

## What works and what does not

| Feature | Status / evidence |
| --- | --- |
| Browser-backed text, new conversation, and multiple turns | **Verified**, installed Windows SDK |
| Stream answer over Qwen's browser-observed network SSE | **Verified**, including a complete 1–100 response; use `--stream network` |
| Reattach to an existing conversation by URL or UUID | **Verified**, including from a new Python process |
| Explicit overload recovery (`/retry`) | Implemented and offline-tested; gated on Qwen's high-demand message and Regenerate control |
| Browser tab remains in background | Supported; `--foreground-tab` is opt-in |
| DOM text snapshots (`--stream dom`) | Supported but heuristic; **not** equivalent to SSE completeness |
| Session export for direct HTTPS | Explicit opt-in, stored locally; export does not send a model prompt |
| Direct `http` transport | **Experimental / not live-proven**; Qwen can return HTML or require browser verification |
| Browser model selection | Not supported by this SDK |
| Images, files, temporary chats, canonical conversation readback | Not implemented / not claimed |
| Response 1 / Response 2 choice, all Qwen overload UI variants | Not generally proven |

The provider can return a completed network-streamed answer without proving **canonical/durable finality** under every Qwen UI state. Do not turn partial output into action authority.

## 1. Install the isolated Qwen bridge (Windows)

Start with a checkout of this repository. The PyPI `0.3.0` wheel predates this integration; **install from current source**:

```powershell
cd W:\dev\chatgpt-web-adapter
python -m pip install -e .
python -m chatgpt_web_adapter.qwen_native
```

The last command prepares the isolated unpacked extension in:

```text
%LOCALAPPDATA%\chatgpt-web-adapter\qwen-native\extension
```

In Chrome:

1. Open `chrome://extensions`, enable **Developer mode**, then **Load unpacked** from that folder.
2. Copy the **new Qwen extension's ID** (32 characters, not the production CWA ID).
3. Register **only** the independent Qwen Native Messaging host:

```powershell
python -m chatgpt_web_adapter.qwen_native --extension-id YOUR_QWEN_EXTENSION_ID
```

Reload the **Qwen extension** in `chrome://extensions`. Sign in to [chat.qwen.ai](https://chat.qwen.ai/) in Chrome. Do not register the Qwen extension under `com.kymuco.chatgpt_web_adapter`.

| Resource | Experimental Qwen | Production ChatGPT/HDE |
| --- | --- | --- |
| Native host | `com.kymuco.qwen_web_adapter` | `com.kymuco.chatgpt_web_adapter` |
| Bridge descriptor | `qwen-native/bridge.json` | `browser-native/bridge.json` |
| Extension | Separate unpacked Qwen extension | Existing CWA extension |
| Web permission | `https://chat.qwen.ai/*` | Existing production permissions |

This source installer registers the Qwen Native Host on **Windows**. Unit/packaging tests also run on Linux, but do not imply the same native-host installation workflow works there.

## 2. CLI cookbook (browser transport)

Run from the repository root (where `qwen_sdk.py` is located). The CLI defaults to `browser`, and to `dom` streaming. **Specify `--stream network` when completeness matters.**

### New interactive conversation — verified

```powershell
python .\qwen_sdk.py --stream network
```

The prompt is `Вы:`. Enter messages normally; use `/exit` or `/quit` to leave. An interactive session retains the returned conversation for the next turn.

### One message — verified transport

```powershell
python .\qwen_sdk.py --transport browser --stream network "Привет!"
```

Omitting `--chat` requests a **new** conversation; it does not automatically recover the previous process's chat.

### Age confirmation only when your Qwen session requires it

```powershell
python .\qwen_sdk.py --auto-confirm-age --birth-year 2000 --stream network
```

Use **your actual birth year**. This opt-in handles the site's own age dialog; it does not bypass eligibility restrictions.

### Resume a specific chat — verified across processes

```powershell
python .\qwen_sdk.py --chat "00000000-0000-4000-8000-000000000001" --stream network
```

Or use the exact Qwen URL: `https://chat.qwen.ai/c/UUID`. The SDK validates its origin and UUID. It **does not** silently create another conversation when the requested chat is unknown.

### Explicit overload recovery

When Qwen displays its **high-demand / busy** response, enter `/retry` in the *same interactive session*. The SDK checks for the overload response and an enabled **Regenerate** control, then invokes it **once**. It does **not** submit another copy of your user message. There is no automatic replay.

If the process was restarted, supply the known `--chat UUID` and keep the corresponding browser tab available. Do **not** use `/retry` as a generic fix for ambiguous network delivery or a possibly accepted prompt.

### Opt in to activating Qwen's tab

```powershell
python .\qwen_sdk.py --foreground-tab --stream network
```

Ordinary operation is background-oriented. Foreground activation is an explicit option for a particular page/focus situation, **not** a required SDK mode.

### Alternative: DOM updates (heuristic)

```powershell
python .\qwen_sdk.py --stream dom
```

DOM snapshots can be revised and need terminal redraws. In an inactive tab the DOM may lag the verified SSE answer, so **do not use DOM silence as proof of finality**.

## 3. Python API cookbook

Import from the installed `chatgpt_web_adapter` package; browser mode uses the isolated Qwen bridge.

### Single user-authored message

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
result = client.send_text("Привет!")
print(result.text)
print(result.conversation.conversation_id)
```

This example sends exactly the text you provided. There are no SDK-owned demonstration prompts or live probes.

### Stream answer fragments (preferred)

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
result = client.send_text(
    "Посчитай от 1 до 20.",
    on_token=lambda fragment: print(fragment, end="", flush=True),
)
print()  # complete the terminal line
# result.text holds the returned answer text.
```

Passing `on_token` opts into browser-observed **network streaming**. Qwen's SSE is assembled only from answer-phase deltas; completed network text is preferred over a potentially truncated hidden-tab DOM snapshot. This is not a canonical conversation readback guarantee.

### Continue in one Python process

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
first = client.send_text("Запомни слово: орхидея.")
second = client.send_text(
    "Какое слово я попросил запомнить?",
    conversation=first.conversation,
)
print(second.text)
```

Always use the returned `conversation` to preserve conversation identity. A new `send_text` call without a conversation starts a new browser conversation.

### Attach to an existing Qwen chat

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
chat = QwenClient.chat("00000000-0000-4000-8000-000000000001")
result = client.send_text("Продолжим наш разговор.", conversation=chat)
print(result.text)
```

`QwenClient.chat()` accepts a Qwen UUID or an exact `https://chat.qwen.ai/c/UUID` URL. It prepares a reference, **without sending anything**; the following `send_text()` is the write.

### Read Qwen's raw conversation payload (experimental)

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
chat = QwenClient.chat("YOUR_CHAT_UUID")
payload = client.read_history(chat)  # one read-only GET, no model prompt
messages = payload["data"]["chat"]["history"]["messages"]
print("Message IDs:", list(messages))
```

Open this **exact Qwen conversation in Chrome first** with the isolated Qwen extension connected. The SDK reuses that tab in the background; it does **not** open/activate a tab, send a message, export credentials or retry the GET. This path requests `GET /api/v2/chats/{id}/` from the authenticated page and returns the **unmodified JSON envelope**, not a synthesized transcript. The current expected `data.chat.history.messages` shape is based on third-party source and deterministic tests; it has **not** been live-confirmed in our Qwen session. Schema, pagination/completeness, selected response and durable canonical finality remain unverified. A changed envelope or response over 700 KB fails explicitly rather than silently truncating.

### Regenerate only a Qwen overload response

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
chat = QwenClient.chat("00000000-0000-4000-8000-000000000001")

# Use only after the last answer is visibly Qwen's high-demand error:
result = client.retry(conversation=chat)
print(result.text)
```

This is a gated Regenerate operation on the existing conversation; it is not permission to auto-retry ambiguous writes.

### Opt-in age confirmation and tab activation

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(
    transport="browser",
    auto_confirm_age=True,
    birth_year=2000,  # replace with your actual birth year
    foreground_tab=False,
)
answer = client.send_text("Здравствуйте!")
print(answer.text)
```

Use `foreground_tab=True` only when explicitly wanting Qwen's tab to become active.

### Observe DOM snapshots rather than SSE deltas

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
answer = client.send_text(
    "Объясни градиентный спуск.",
    on_text=lambda full_snapshot: print("snapshot:", full_snapshot),
)
print("final:", answer.text)
```

`on_text` emits **whole mutable snapshots**, not append-only chunks. Do not concatenate those snapshots. For append-style output use `on_token` instead.

## 4. Experimental direct HTTP mode — **not** the verified path

Direct HTTP is a separate, manually selected transport. It is **not** what made the Windows Qwen browser SDK successful. The site's private endpoints and anti-bot/session requirements can change; an authenticated request previously returned `HTTP 200 text/html` instead of the expected JSON. No live browserless acceptance is claimed.

### Import only Qwen authorization, with explicit consent

```powershell
python .\qwen_sdk.py --import-auth
```

This requires the separate Qwen extension and an authenticated Qwen tab. It saves a local Qwen-specific credential snapshot (Windows DPAPI); it does **not** send a chat message. Do not paste access tokens, cookies, `auth_data`, bridge descriptors or browser profiles into issues, logs or git.

### Attempt HTTP mode (experimental)

```powershell
python .\qwen_sdk.py --transport http "Привет!"
```

Or via Python:

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="http")
client.import_browser_auth()  # explicit local transfer, no prompt sent
reply = client.send_text("Привет через HTTPS")
print(reply.text)
```

These are **source-level usage examples, not a guaranteed working Qwen Web API**. The `--model` flag applies **only** to this experimental HTTP path; no model ID has been validated for the browser SDK. The HTTP API also accepts an opt-in `browser_session_refresh=True` when you intentionally want to reimport from Chrome; this is **not** independent long-term refresh while Chrome is closed. A verified direct refresh endpoint is not configured by default.

HTTP and browser conversation objects are **not interchangeable**. No silent fallback between transports is implemented. If you specifically need a supported key-based backend API, use an official provider API separately from this consumer-web adapter.

## 5. Handling failures safely

| Symptom | Safe next step |
| --- | --- |
| Qwen displays a high-demand response | Use **explicit** `/retry` in that chat, when its Regenerate control is present |
| `QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED` or post-submit observation lost | Inspect/reattach the actual Qwen chat. **Never automatically resend** |
| Stream callback received some text, but finality not proven | Treat output as partial; do not use it as a completed action result |
| `QWEN_NETWORK_STREAM_NOT_VERIFIED` | Ensure the *isolated Qwen extension* has been reloaded after updating source |
| Bridge/Native Host unavailable | Recheck Qwen extension ID, its registered host name and the `qwen-native` descriptor |
| HTTP returns HTML / verification error | Do not loop through blind retries or assume valid cookies prove API access |
| Default `dom` response truncates | Use `--stream network`, then inspect server/DOM evidence if needed |
| Response 1 / Response 2 feedback | Do not assume the first or last visible candidate is canonical; resolve selection explicitly on the site |

A failed UI readback **may occur after** Qwen stored the user's prompt. The installed SDK run already showed a Formula 1 message recoverable from a fresh `--chat` session despite an earlier readback error. The user and Codex attributed their historical failed turns to Qwen busy/high-demand. That is a diagnosis of those incidents, **not** a guarantee that every future error with a similar string is caused by overload.

## 6. Isolation and maintenance rules

- Keep `com.kymuco.qwen_web_adapter` and its unpacked extension separate from ChatGPT/HDE's `com.kymuco.chatgpt_web_adapter`; installing the Qwen variant must not overwrite the production bridge or service worker.
- Use `python -m pip install -e .` on the intended source checkout. Do not infer that PyPI `0.3.0` contains these modules.
- Don't use `git add .` from a working tree that also contains private research notes, cookies or captured traces.
- No automatic replay after a potentially executed Send. `/retry` is a *different* action: one user-requested Regenerate on a **confirmed overload**.
- Network-stream answer finality is not the same as canonical/durable product-state proof.
- Read the [Qwen isolation plan](engineering/qwen_browser_isolation_plan.md), [engineering lessons](engineering/qwen_provider_lessons_2026_10_15.md), and [native setup notes](engineering/qwen_native_setup.md) for the evidence history.

The Qwen source and documentation are shipped on `main` as an **experimental, isolated** provider. This does **not** change ChatGPT's production support tier.
