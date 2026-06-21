# webchat-adapter

[![CI](https://github.com/kymuco/webchat-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/kymuco/webchat-adapter/actions/workflows/ci.yml)

Minimal Python SDK for `chatgpt.com` web sessions, extracted from `webchat-openai-cli`.

The goal of this repository is to keep the transport layer reusable, dependency-free at runtime, and close to standard Python. The package intentionally does not include the CLI, localization, or local chat-history management from the original project.

## Features

- zero runtime Python dependencies
- sync chat API with optional token callback for streaming output
- `auth_data.json` and `.env` auth loading
- image uploads from local paths, `Path`, URL, data URI, or raw bytes
- experimental browserless tool-approval helpers for web-agent flows
- experimental raw payload escape hatch for advanced users
- local `curl`-based transport for compatibility with stock Python

## Requirements

- Python 3.10+
- system `curl` available in `PATH`
- valid `auth_data.json` with `accessToken`, or an optional `.env` fallback with `accessToken`

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

## Authentication at a Glance

`webchat-adapter` does not log you in and does not capture auth by itself. It only reuses existing `chatgpt.com` web-session data.

Recommended `auth_data.json` shape:

```json
{
  "accessToken": "eyJhbGciOi...",
  "cookies": {
    "__Secure-next-auth.session-token": "..."
  },
  "headers": {
    "user-agent": "Mozilla/5.0 ..."
  }
}
```

- `accessToken` is the ChatGPT web access token from your browser session. It is not an official OpenAI API key.
- `cookies` and `headers` should come from the same account/session as the token.
- `.env` is optional, not required. If present, `accessToken=...` is used only as a fallback when the file token is missing or expired.
- Older files that still use `api_key` are accepted for backward compatibility, but new examples and new files should use `accessToken`.
- If you need to generate this file, capture it with `webchat-openai-cli` and then reuse it here.

## Detailed Guide

For the full SDK walkthrough, including auth flows, `warmup()`, `temporary`, `web_search`,
`reasoning_effort`, conversation continuation, image inputs, response objects, and error handling,
see [USAGE.md](USAGE.md).

## Experimental Features

The SDK also includes experimental browserless helpers for web-agent/tool approval flows:

- `approve_pending_action()`
- `wait_and_approve_pending_actions()`
- `send_and_auto_approve()`

These APIs are useful for ChatGPT web connector flows such as GitHub file creation, but they rely
on reverse-engineered web behavior and should be treated as less stable than the base `send()` API.

See [USAGE.md](USAGE.md) and [examples/github_auto_approve.py](examples/github_auto_approve.py).

The SDK also includes an experimental raw payload escape hatch for advanced users:

- `PayloadBuilder`
- `validate_payload()`
- `send_payload()`

See [docs/raw_payload.md](docs/raw_payload.md).

This API sends raw ChatGPT web backend payloads. It is not an official or stable API.

The example script includes:

- a neutral repository placeholder instead of a hard-coded demo repo
- live assistant token printing
- structured approval progress events

## Streaming Callback

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Stream the answer token by token.",
    on_token=lambda token: print(token, end="", flush=True),
)
```

## Continue an Existing ChatGPT Web Conversation

```python
from webchat_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send_to_conversation(
    "https://chatgpt.com/c/...",
    "Продолжи с этого места.",
)

print(response.text)
```

`send_to_conversation()` attaches to the latest web conversation state, resolves the current parent message automatically, and preserves the detected model when possible. Model detection is best-effort because ChatGPT web payloads can change. If the model cannot be detected, the SDK uses the normal `send()` default model.

## Continue from an SDK Response

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

This repository only consumes existing auth data. If you still need browser-based capture, generate `auth_data.json` with `webchat-openai-cli` first and then reuse it here.

## Future Rename

The project may later move to the clearer name `chatgpt-web-adapter`, with Python package import `chatgpt_web_adapter`.

The current `webchat_adapter` import remains the only supported import today. See [docs/rename_compatibility.md](docs/rename_compatibility.md).

## Status

Initial SDK baseline. The repository is intentionally small and focused on the transport layer first.
GitHub Actions validates tests on Python 3.10-3.13 across Ubuntu and Windows, and also checks that the package builds successfully.
