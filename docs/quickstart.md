# CWA Quickstart

CWA is a local bridge from your software to ordinary hosted AI products that you
already use in the browser.

It is not an official API client and it does not turn visible product state into
implicit write, retry, or finality authority.

Choose the shortest path that matches what you are building. For ChatGPT,
Direct HTTP is the primary supported Python SDK for live-verified operations.
The browser-owned UI path remains secondary/experimental and the historical
`assemble_product_runtime()` default for compatibility only.

## Path A - ChatGPT Direct HTTP (recommended)

Published `v0.4.1` and current `main` use Direct HTTP by default for `cwa send`.
The newest `main` also contains post-release Project/GPT conversation URL parsing,
which is not included in the tagged `v0.4.1` wheel.
Obtain a signed-in `auth_data.json` via existing browser authentication.
If you need initial `auth login`, install the optional `[browser]` extra and
sign in once:

```bash
python -m pip install "chatgpt-web-adapter[browser]"
chatgpt-web-adapter auth login --auth-file auth_data.json
```

This browser step obtains credentials; subsequent Direct HTTP **sending** does
not open a Chrome tab. Sending requires Node.js 24+ and curl.

```python
from chatgpt_web_adapter import BrowserlessHTTPClient

client = BrowserlessHTTPClient(auth_file="auth_data.json")
response = client.send("Give me a two-sentence project summary.")
print(response.text)
print(client.get_status(response.conversation.conversation_id).status)
```

On released `v0.4.1` and current `main`, the same Direct HTTP SDK is
selected by default in `cwa send "Hello" --profile HIGH`.
The `cwa status`, `cwa doctor`, `cwa capabilities`, and `cwa messages` commands
still inspect the legacy product-runtime transport (`browser-owned` by default),
not Direct HTTP send health. The browser extension is not required for sending
with the new CLI default. For CLI errors, `--json` reports a safe operation
phase such as `file_upload`; a timeout can still have an unknown outcome.
Never resend automatically if the first send has an uncertain outcome. See
[Direct HTTP SDK](browserless_http_sdk.md) for model, files, continuation and
setup limitations.

## Existing conversation links: regular and Project chats

Every public CWA method that accepts a ChatGPT conversation reference can
receive a raw conversation ID, a standard
`https://chatgpt.com/c/<conversation-id>` URL, or a Project/GPT-scoped
`https://chatgpt.com/g/<project-or-gpt-id>/c/<conversation-id>` URL.
The `ConversationRef` parser selects the **conversation ID** and never
mistakes the scope identifier for the conversation.

For example, this pattern supports either URL without rewriting it:

```python
from chatgpt_web_adapter import ChatGPTWebClient, ConversationRef

url = "https://chatgpt.com/g/g-p-my-project/c/my-conversation-id"
client = ChatGPTWebClient(auth_file="auth_data.json", timeout=120)
ref = ConversationRef.from_any(url)
payload = client._get_full_conversation_payload(ref.conversation_id)
```

The last line is a historical private payload API, included to match existing
scripts; for public reads prefer `client.get_messages(url, limit=None)`,
`client.attach_conversation(url)` or the `cwa snapshot` / `cwa export`
commands. The input URL is an address, **not authorization**; access still
depends on the current authenticated account. Normalizing a URL to a
conversation ID does not retain or recreate the original Project URL or imply
that a Project-specific read has been live-verified.

## Path B - browser-owned CLI (secondary, explicit transport)

Install CWA with the browser bridge:

```bash
python -m pip install "chatgpt-web-adapter[browser]"
```

Prepare ChatGPT authentication:

```bash
chatgpt-web-adapter auth login --auth-file auth_data.json
chatgpt-web-adapter auth status --auth-file auth_data.json
```

Install the Native Messaging bridge and print the packaged extension directory:

```bash
chatgpt-web-adapter browser-native install
chatgpt-web-adapter browser-native extension-dir
```

In Chrome/Chromium:

1. open `chrome://extensions`;
2. enable Developer mode;
3. choose **Load unpacked**;
4. select the directory printed by `browser-native extension-dir`;
5. keep an authenticated ChatGPT web session available.

Verify the local runtime:

```bash
chatgpt-web-adapter browser-native status
cwa doctor --json
```

Send a governed text turn:

```bash
cwa send "Give me a two-sentence summary of what CWA does." --transport browser-owned --profile HIGH
```

If the command reports a reconciliation-required outcome, do not blindly replay the
write. CWA intentionally distinguishes an unknown product outcome from retry
permission.

## Path C - browser-owned Python runtime (secondary)

The historical browser-owned application runtime is `ChatGPTProductRuntime`.
It is **EXPERIMENTAL** for the current UI and retains the SDK default only
for backward compatibility:

```python
from chatgpt_web_adapter import assemble_product_runtime

runtime = assemble_product_runtime(
    transport="browser-owned",
    auth_file="auth_data.json",
)

health = runtime.health()
if not health.ready:
    raise RuntimeError(health.reason)

execution = runtime.send_text_observed(
    "Give me a short project summary."
)

print(execution.response.text)
print(execution.provenance.to_dict())
```

Read/status/finality remain explicit runtime operations rather than being inferred
from the visible page.

## Path D - experimental non-chat capability

Current `main` also contains a module-only Google Translate Web capability:

```python
from chatgpt_web_adapter.google_translate_web import GoogleTranslateWebCapability

translator = GoogleTranslateWebCapability()

result = translator.translate_text(
    "hello",
    source_language="en",
    target_language="es",
)

print(result.translated_text)
```

The live-proven result model is:

```text
text + source language + target language
-> Google Translate Web
-> PAGE_DOM_STABLE_TRANSLATION
```

This surface is experimental, non-conversational, and deliberately not forced into
`ProductProviderBoundary schema 2`.

## Path E - local assistant or agent

If you already have a local assistant, coding agent, or multi-agent system, start with
[agent integration](agent_integration.md).

Today the clean integration boundary is Python or the stable CLI. A dedicated MCP
adapter is a future integration layer; it is not shipped yet.

## What to read next

- [Capabilities](capabilities.md) - what is actually proven today;
- [Providers](providers.md) - chat-provider support/finality matrix;
- [Architecture](architecture.md) - authority and finality boundaries;
- [Agent integration](agent_integration.md) - local assistants and tool wrappers;
- [Security](../SECURITY.md) - session and credential handling;
- [Troubleshooting](troubleshooting.md) - operational diagnostics.
