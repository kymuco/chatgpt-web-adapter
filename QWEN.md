# Qwen Web — quickstart (Windows)

**Want only Qwen in your terminal? Start here.** You do not need to configure ChatGPT, HDE, Gemini, DeepSeek or the normal CWA extension.

This guide uses the **browser-backed Qwen SDK**: Python sends your message through a **separate Qwen Chrome extension** to your signed-in account at [chat.qwen.ai](https://chat.qwen.ai/). The extension can work with a background tab. It is not the official Qwen API or a browserless client.

**Requirements:** Windows, Python **3.10–3.14**, Git, Chrome, and your own Qwen account. The Qwen provider is **experimental**; text conversations and network streaming have been verified with the installed Windows SDK, but the site's behavior can change.

## First-time setup (once)

### 1. Get the project and install it

In PowerShell:

```powershell
git clone https://github.com/kymuco/chatgpt-web-adapter.git
cd chatgpt-web-adapter
python -m pip install -e .
```

The repository checkout is needed because `qwen_sdk.py` is a source-tree CLI; it is **not** a separate `qwen` executable installed by `pip`. Use the same Python environment for installation and launch. No ChatGPT authentication or shared CWA setup is required.

### 2. Create the isolated Qwen extension

```powershell
python -m chatgpt_web_adapter.qwen_native
```

The command prints its unpacked extension directory. On a standard Windows installation it is:

```text
%LOCALAPPDATA%\chatgpt-web-adapter\qwen-native\extension
```

In Chrome:

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked**, then select the **Qwen extension directory** above.
3. Copy the newly installed **Qwen Web Adapter (isolated)** extension's ID.

This is *not* your existing ChatGPT/CWA extension. Do not reuse the ChatGPT extension ID.

### 3. Connect this Qwen extension to its own local native host

Replace `YOUR_QWEN_EXTENSION_ID` with the actual ID from Chrome:

```powershell
python -m chatgpt_web_adapter.qwen_native --extension-id YOUR_QWEN_EXTENSION_ID
```

Reload **Qwen Web Adapter (isolated)** from `chrome://extensions`. This registers the independent host `com.kymuco.qwen_web_adapter`, not the production `com.kymuco.chatgpt_web_adapter` host.

Open [chat.qwen.ai](https://chat.qwen.ai/) in Chrome and sign in to your Qwen account. Keep Chrome running while using the **browser** transport.

## Start the terminal chat (one command)

From the `chatgpt-web-adapter` directory:

```powershell
python .\qwen_sdk.py --stream network
```

**That's the actual interactive Qwen SDK CLI** — no test prompts, no probe script, no manual token copying.

```text
Qwen SDK · transport=browser · /exit для выхода
Вы: привет
[Qwen response streams here]
Вы:
```

Type a question and press Enter. The SDK streams answer fragments as they are observed. Use `/exit` to quit. The terminal maintains the returned conversation within that run.

> **Why `--stream network`?** The CLI defaults to `dom` snapshots; hidden-tab DOM may be incomplete even after Qwen finishes. The network mode is the preferred, Windows-live-verified text-streaming path. Neither mode proves canonical/durable Qwen conversation readback.

## Everyday commands (same CLI)

Run these **from the same repository directory**:

| Goal | Command |
| --- | --- |
| Interactive terminal chat (**recommended**) | `python .\qwen_sdk.py --stream network` |
| Send a single message | `python .\qwen_sdk.py --stream network "Привет!"` |
| Continue an existing chat | `python .\qwen_sdk.py --chat YOUR_CHAT_UUID --stream network` |
| Use an exact Qwen chat URL | `python .\qwen_sdk.py --chat "https://chat.qwen.ai/c/YOUR_CHAT_UUID" --stream network` |
| Confirm age when Qwen explicitly asks | `python .\qwen_sdk.py --auto-confirm-age --birth-year YOUR_BIRTH_YEAR --stream network` |
| Explicitly bring the Qwen tab to the foreground | `python .\qwen_sdk.py --foreground-tab --stream network` |

`YOUR_CHAT_UUID` is the UUID from the **real** `chat.qwen.ai/c/...` conversation URL. `YOUR_BIRTH_YEAR` must be replaced with your actual year; the age option is not an eligibility bypass.

During an interactive chat:

- `/exit` or `/quit` ends the CLI.
- `/retry` is **only** for a visibly confirmed Qwen *busy/high-demand* response with an available **Regenerate** control. It regenerates the response once in the same chat; it does **not** send a duplicate user message. Do not use it as a blind retry after an ambiguous write.

## Use it in Python instead of the terminal

```python
from chatgpt_web_adapter.qwen_client import QwenClient

client = QwenClient(transport="browser")
first = client.send_text(
    "Привет!",
    on_token=lambda chunk: print(chunk, end="", flush=True),
)
print()

second = client.send_text(
    "А что я спросил сначала?",
    conversation=first.conversation,
)
print(second.text)
```

For a fresh process, use `QwenClient.chat("YOUR_CHAT_UUID")` and pass the returned conversation to `send_text`.

## Troubleshooting and limits

**Extension unavailable:** verify that you loaded the *Qwen* unpacked folder, registered **its own** 32-character extension ID, and reloaded it. Check that Chrome is running and logged in at `chat.qwen.ai`.

**Wrong Python or missing CLI:** run `python -m pip install -e .` again from the checkout using the same Python environment; invoke `python .\qwen_sdk.py` from the project root.

**Qwen says busy:** use `/retry` only when the last Qwen response is the site's high-demand message. If submission/readback was ambiguous, **inspect the conversation before sending anything again**.

**Looking for completely browser-free chat?** `python .\qwen_sdk.py --transport http` exists as a separate experiment, but successful direct Qwen Web generation is **not verified** and Qwen may return verification/HTML responses. The recommended path above requires Chrome.

**Supported here:** browser-backed text, new chat, continuation, network stream, explicit existing-chat attachment. **Not claimed:** Qwen Web images/files, browser model choice, automatic long-term HTTP token refresh, canonical finality, and complete two-answer feedback selection.

For the full reference (all Python/CLI examples, failure semantics, and evidence), see **[docs/qwen.md](docs/qwen.md)**. For the reasons behind isolation, see the [Qwen browser isolation plan](docs/engineering/qwen_browser_isolation_plan.md).
