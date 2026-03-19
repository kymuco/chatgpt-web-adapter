# webchat-adapter

Minimal Python SDK for `chatgpt.com` web sessions, extracted from `webchat-openai-cli`.

The goal of this repository is to keep the transport layer reusable, dependency-free at runtime, and close to standard Python. The package intentionally does not include the CLI, localization, or local chat-history management from the original project.

## Features

- zero runtime Python dependencies
- sync chat API with optional token callback for streaming output
- `auth_data.json` and `.env` auth loading
- image uploads from local paths, `Path`, URL, data URI, or raw bytes
- local `curl`-based transport for compatibility with stock Python

## Requirements

- Python 3.10+
- system `curl` available in `PATH`
- valid `auth_data.json` or `.env` with `accessToken`

## Install

```bash
python -m pip install -e .
```

For tests:

```bash
python -m pip install -e .[test]
pytest -q
```

## Quick Start

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Give me a short summary of this project.",
    model="gpt-4o-mini",
)

print(response.text)
print(response.metrics.total)
```

## Detailed Guide

For the full SDK walkthrough, including auth flows, `warmup()`, `temporary`, `web_search`,
`reasoning_effort`, conversation continuation, image inputs, response objects, and error handling,
see [USAGE.md](USAGE.md).

## Streaming Callback

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Stream the answer token by token.",
    on_token=lambda token: print(token, end="", flush=True),
)
```

## Continue a Conversation

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

first = client.send("Start a conversation.")
second = client.send(
    "Continue it.",
    conversation=first.conversation,
)
```

## Auth Notes

This repository only consumes existing auth data. If you still need browser-based capture, you can generate `auth_data.json` with `webchat-openai-cli` and reuse it here.

## Status

Initial SDK baseline. The repository is intentionally small and focused on the transport layer first.
