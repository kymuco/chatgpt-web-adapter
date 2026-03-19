# `webchat-adapter` Usage Guide

Detailed usage guide for the dependency-free Python SDK that talks to the `chatgpt.com` web backend through a local `curl` transport.

This document covers the public API exposed by the package today and only describes behavior that is present in the codebase.

## Contents

- [What This SDK Does](#what-this-sdk-does)
- [Requirements](#requirements)
- [Install](#install)
- [Authentication](#authentication)
- [Create a Client](#create-a-client)
- [Basic Chat Request](#basic-chat-request)
- [Read the Response Object](#read-the-response-object)
- [Stream Tokens with `on_token`](#stream-tokens-with-on_token)
- [Warm Up the Session](#warm-up-the-session)
- [Use a System Prompt](#use-a-system-prompt)
- [Choose a Model](#choose-a-model)
- [Enable Web Search](#enable-web-search)
- [Use Temporary Chats](#use-temporary-chats)
- [Control Reasoning Effort](#control-reasoning-effort)
- [Continue a Conversation](#continue-a-conversation)
- [Send Images](#send-images)
- [Media Input Formats](#media-input-formats)
- [Handle Errors](#handle-errors)
- [Public Exports](#public-exports)
- [End-to-End Example](#end-to-end-example)
- [Behavior Notes and Gotchas](#behavior-notes-and-gotchas)

## What This SDK Does

`webchat-adapter` is a small sync SDK for working with an existing `chatgpt.com` web session from Python. It is intentionally focused on transport and request formatting.

Current capabilities:

- sync text generation through the web backend
- token streaming via a callback
- conversation continuation
- optional web-search hinting
- optional temporary chats
- optional reasoning-effort control
- image uploads for multimodal prompts
- auth loading from `auth_data.json` and/or `.env`
- zero runtime Python dependencies

Non-goals of this package:

- no CLI
- no browser automation
- no auth capture flow
- no local chat-history storage
- no async client

## Requirements

- Python `3.10+`
- system `curl` available in `PATH`
- a valid `chatgpt.com` web session token

## Install

For local development:

```bash
python -m pip install -e .
```

For tests:

```bash
python -m pip install -e .[test]
pytest -q
```

## Authentication

The SDK consumes existing auth data. It does not create or refresh sessions by itself.

You can authenticate in three main ways:

1. Let the client load `auth_data.json`.
2. Let the client load `accessToken` from `.env`.
3. Pass an `AuthData` object directly.

### `auth_data.json`

In practice, the easiest path is to reuse an existing file captured by another tool, for example `webchat-openai-cli`.

Minimal shape:

```json
{
  "api_key": "eyJhbGciOi...",
  "cookies": {
    "__Secure-next-auth.session-token": "..."
  },
  "headers": {
    "user-agent": "Mozilla/5.0 ..."
  }
}
```

If your captured file also includes `proof_token` or `turnstile_token`, keep them. The SDK can use those fields when the backend requires them.

### `.env`

If `auth_data.json` is missing or its token is expired, the loader can fall back to `.env`.

```dotenv
accessToken=eyJhbGciOi...
```

The loader looks for `.env` in the current working directory and a few nearby project/module locations.

### Loading Auth Manually

```python
from webchat_adapter import load_auth_data

auth = load_auth_data("auth_data.json")

print(auth.api_key_source)
print(bool(auth.cookies))
```

### Auth Resolution Rules

- If `auth_data.json` contains a valid `api_key`, it is used first.
- If that token is missing or expired, `.env:accessToken` can be used instead.
- If every discovered token is expired, `AuthError` is raised.
- If no token is found at all, `AuthError` is raised.

## Create a Client

### Default File-Based Client

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
```

### Pass a Preloaded `AuthData`

```python
from webchat_adapter import AuthData, ChatGPTWebClient

auth = AuthData(
    api_key="eyJhbGciOi...",
    cookies={"__Secure-next-auth.session-token": "..."},
)

client = ChatGPTWebClient(auth=auth)
```

### Custom Timeout and `curl` Binary

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(
    auth_file="auth_data.json",
    timeout=120,
    curl_bin="curl",
)
```

Constructor arguments:

- `auth`: optional prebuilt `AuthData`
- `auth_file`: path to `auth_data.json` if `auth` is not passed
- `timeout`: request timeout in seconds, minimum effective value is `10`
- `curl_bin`: override the detected `curl` executable

## Basic Chat Request

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Give me a short summary of this project.",
    model="gpt-4o-mini",
)

print(response.text)
```

## Read the Response Object

`send()` returns a `ChatResponse` object:

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
response = client.send("Say hello in one sentence.")

print("text:", response.text)
print("title:", response.title)
print("conversation_id:", response.conversation.conversation_id)
print("message_id:", response.conversation.message_id)
print("finish_reason:", response.conversation.finish_reason)
print("first_token:", response.metrics.first_token)
print("last_token:", response.metrics.last_token)
print("total:", response.metrics.total)
```

Fields returned by the SDK:

- `response.text`: full assistant text
- `response.title`: title generated by the backend when available
- `response.conversation`: continuation metadata
- `response.metrics`: timing metrics in seconds

## Stream Tokens with `on_token`

Use `on_token` if you want to print or process chunks as they arrive.

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Write a four-line poem.",
    on_token=lambda token: print(token, end="", flush=True),
)

print("\n---")
print("Final text length:", len(response.text))
```

The callback is optional. The SDK still returns the full concatenated text in `response.text`.

## Warm Up the Session

`warmup()` prefetches the backend requirements/proof information so the next request can start with less setup work.

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

if client.warmup():
    print("Warmup succeeded")
else:
    print("Warmup failed")

response = client.send("Continue after warmup.")
```

Notes:

- `warmup()` returns `True` or `False`
- the prefetched data is short-lived
- if warmup data is missing or stale, `send()` fetches fresh data automatically

## Use a System Prompt

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Explain decorators with a tiny example.",
    system="You are a concise Python tutor.",
)
```

Important behavior: the SDK only sends `system` on the first turn of a conversation. If you continue an existing conversation, the new `system` value is ignored by design.

## Choose a Model

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "List three possible names for a logging package.",
    model="gpt-4o-mini",
)
```

The package default is:

```python
from webchat_adapter import DEFAULT_MODEL

print(DEFAULT_MODEL)  # gpt-4o-mini
```

The client also normalizes some web-style aliases internally, including:

- `gpt-5.1`
- `gpt-4.1`
- `gpt-4.1-mini`
- `gpt-4.5`

## Enable Web Search

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Find recent information about Python packaging trends.",
    web_search=True,
)
```

This sends the backend search hint used by the web client. Availability still depends on the account/session behind your auth data.

## Use Temporary Chats

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Draft a private brainstorming list.",
    temporary=True,
)
```

This sets the web payload flag that disables history/training for the request.

## Control Reasoning Effort

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Solve this step by step: 144 * 37",
    reasoning_effort="extended",
)
```

Accepted values:

- `"standard"`
- `"extended"`
- `"off"`
- `"none"`
- `"-"`

Behavior:

- `"off"`, `"none"`, and `"-"` are normalized to no reasoning flag
- any other value raises `ValueError`

## Continue a Conversation

### Use the Returned `ChatConversation`

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

first = client.send("Start a short conversation about databases.")
second = client.send(
    "Now compare SQLite and PostgreSQL.",
    conversation=first.conversation,
)

print(second.text)
```

### Pass a Plain Dictionary

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

conversation = {
    "conversation_id": "conv_123",
    "message_id": "msg_456",
    "parent_message_id": "msg_456",
    "user_id": "user_789",
}

response = client.send(
    "Continue from this existing thread.",
    conversation=conversation,
)
```

The SDK uses `conversation_id` plus the previous message identifiers to continue the thread.

## Send Images

The current media helper is image-focused. Supported formats are:

- PNG
- JPEG/JPG
- GIF
- WebP

### Local Image from `Path`

```python
from pathlib import Path

from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Describe what is shown in this image.",
    media=["examples/cat.png"],
)
```

### Remote Image by URL

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Summarize the chart in this image.",
    media=["https://example.com/chart.png"],
)
```

The SDK follows redirects when downloading remote media before upload.

### Data URI

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."

response = client.send(
    "Extract the important visual details.",
    media=[data_uri],
)
```

### Raw Bytes with an Explicit Filename

```python
from pathlib import Path

from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
image_bytes = Path("examples/diagram.webp").read_bytes()

response = client.send(
    "What kind of diagram is this?",
    media=[(image_bytes, "diagram.webp")],
)
```

### Multiple Images

```python
from pathlib import Path

from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Compare these two images.",
    media=[
        Path("examples/before.png"),
        Path("examples/after.png"),
    ],
)
```

## Media Input Formats

Accepted media sources:

- `bytes`
- `bytearray`
- local file path strings like `"examples/photo.jpg"`
- `pathlib.Path`
- any `os.PathLike`
- remote URL strings like `https://...`
- data URI strings like `data:image/png;base64,...`

Optional named item format:

```python
media = [
    (Path("examples/photo.jpg"), "photo.jpg"),
]
```

## Handle Errors

Main exception types:

- `AuthError`: auth loading or token problems
- `RequestError`: HTTP/curl/backend failures
- `MediaError`: invalid media input, download issues, unsupported format

Example:

```python
from pathlib import Path

from webchat_adapter import AuthError, ChatGPTWebClient, MediaError, RequestError

try:
    client = ChatGPTWebClient(auth_file="auth_data.json")
    response = client.send(
        "Describe this image.",
        media=[Path("examples/photo.png")],
    )
    print(response.text)
except AuthError as error:
    print("Authentication failed:", error)
except MediaError as error:
    print("Media problem:", error)
except RequestError as error:
    print("Request failed:", error)
```

## Public Exports

The package exports the main types directly:

```python
from webchat_adapter import (
    AuthData,
    AuthError,
    ChatConversation,
    ChatGPTWebClient,
    ChatMetrics,
    ChatResponse,
    DEFAULT_AUTH_FILE,
    DEFAULT_MODEL,
    MediaError,
    RequestError,
    WebChatAdapterError,
    WebChatClient,
    load_auth_data,
)
```

`WebChatClient` is an alias of `ChatGPTWebClient`.

## End-to-End Example

```python
from pathlib import Path

from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json", timeout=120)

client.warmup()

first = client.send(
    "Analyze this image and then suggest a concise alt text.",
    model="gpt-4o-mini",
    system="You are a precise accessibility reviewer.",
    web_search=False,
    temporary=True,
    reasoning_effort="standard",
    media=[Path("examples/ui-screenshot.png")],
    on_token=lambda token: print(token, end="", flush=True),
)

print("\n---")
print("Title:", first.title)
print("Conversation:", first.conversation.conversation_id)
print("Total latency:", first.metrics.total)

follow_up = client.send(
    "Now give me a shorter alt text under 100 characters.",
    conversation=first.conversation,
)

print(follow_up.text)
```

## Behavior Notes and Gotchas

- The SDK is synchronous. There is no async API in this package.
- The transport relies on a local `curl` executable, not Python HTTP dependencies.
- Response cookies from ChatGPT requests are persisted into `client.auth.cookies`.
- Remote media downloads do not merge their cookies into your ChatGPT auth cookies.
- Re-uploading the exact same image bytes within the same client instance can reuse cached upload metadata.
- Image dimensions are detected automatically for PNG, JPEG, GIF, and WebP when possible.
- `response.metrics` values are measured in seconds.
- If the backend requires a Turnstile token and your auth data does not contain one, the request can fail.
- This package is intentionally small; if you need auth capture or a CLI workflow, use a separate tool and feed its auth output into this SDK.
