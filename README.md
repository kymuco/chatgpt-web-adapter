# chatgpt-web-adapter

[![CI](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml)

Python SDK for controlling existing ChatGPT web sessions without browser UI.

> [!WARNING]
> Not the official OpenAI API.
> Uses an existing ChatGPT web session.
> Web backend behavior may change.

`chatgpt-web-adapter` is a small Python SDK with a dependency-free core for sending prompts, continuing conversations, reading conversation state, uploading images, and handling selected ChatGPT web workflows from Python.

It is designed for terminal tools that use a reusable ChatGPT web session. The
optional browser extra can create that session once and recover it later; normal
requests continue without browser UI.

## What This Is

`chatgpt-web-adapter` wraps the existing ChatGPT web backend behavior used by a logged-in web session. It focuses on reusable transport, request formatting, response parsing, and conversation helpers.

The package includes a small auth-management CLI and optional browser bootstrap.
It does not include localization or local chat-history management from
`webchat-openai-cli`.

## When It Is Useful

- controlling long ChatGPT conversations without loading the browser UI
- building local tools or CLIs on top of an existing ChatGPT web session
- continuing existing ChatGPT web conversations by id or URL
- streaming assistant tokens into terminal or app UIs
- reading messages and polling conversation status from Python
- uploading images through the web-session flow
- inspecting live SSE, websocket handoff, and polling events in a terminal
- experimenting with browserless approval workflows

## When Not To Use This

- when you need a stable, documented API contract
- when you need OpenAI-supported authentication and long-term platform guarantees
- when browser automation is acceptable and product-level UI behavior matters more than backend reuse
- when the workflow depends heavily on approval cards or other fast-changing connector behavior
- when your tool cannot tolerate breakage from undocumented `chatgpt.com` changes

## What This Is Not

`chatgpt-web-adapter` is not:

- the official OpenAI API
- a replacement for the OpenAI Python SDK
- a browser automation framework
- a stable contract for undocumented ChatGPT web internals

## Stable vs Experimental

The SDK has two support levels.

Stable core:

- `ChatGPTWebClient.send()`
- `send_to_conversation()`
- `attach_conversation()`
- `get_messages()`
- `get_status()`
- `wait_until_completed()`
- image upload for multimodal prompts

Experimental features:

- `approve_pending_action()`
- `wait_and_approve_pending_actions()`
- `send_and_auto_approve()`
- `PayloadBuilder`
- `validate_payload()`
- `send_payload()`

Current new-chat, continuation, and multimodal writes can opt into the
official-page Sentinel path:

```bash
pip install "chatgpt-web-adapter[browser]"
```

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json", auto_sentinel=True)
response = client.send("Start a new chat from the SDK.")
```

This provider observes a fresh prepare/finalize bundle produced by ChatGPT's own
page, blocks the browser's conversation POST, and keeps the unused one-shot
credentials in memory only.
It is experimental because the web contract and page behavior are undocumented.

The stable core is the main surface intended for building tools on top of an existing ChatGPT web session. Experimental features are exposed because they are useful, but they rely more directly on changing web-client behavior.

## Compatibility Policy

- Stable core APIs are the main compatibility target of the package.
- Experimental APIs may need faster iteration when the ChatGPT web client changes.
- A package release does not guarantee that undocumented web behavior on `chatgpt.com` has remained unchanged.
- When the site changes, experimental flows are expected to break before the stable core send/continue/read flows.

## Known Failure Modes

- expired or mismatched session auth
  - `accessToken`, cookies, and headers can drift out of sync
- changed anti-abuse requirements
  - `chat-requirements`, proof-of-work, or Turnstile expectations can change
- changed backend payload schema
  - send/continue flows can fail if required request fields move or change meaning
- changed SSE response shape
  - token streaming, finish-reason parsing, or conversation-id extraction can break
- changed conversation payload schema
  - attach, status, model detection, and message extraction depend on unstable fields
- changed upload flow
  - file creation, upload, or attachment metadata contracts can shift
- changed approval protocol
  - approval helpers are especially sensitive to connector and web-client changes

## Features

- zero runtime Python dependencies
- sync `ChatGPTWebClient`
- streaming via `on_token` and structured events via `on_event`
- conversation continuation with returned conversation metadata
- attach/read/status helpers for existing conversations
- `auth_data.json` and `.env` auth loading
- one-time browser login and automatic session refresh
- image uploads from local paths, `Path`, URL, data URI, or raw bytes
- experimental browserless tool-approval helpers for web-agent flows
- experimental raw payload escape hatch for advanced users
- local `curl`-based transport for compatibility with stock Python
- example live watcher for SSE, websocket handoff, polling, and approvals

## Requirements

- Python 3.10+
- system `curl` available in `PATH`
- either a valid `auth_data.json`, or the optional browser extra for first login

## Install

```bash
python -m pip install chatgpt-web-adapter
```

For local development and tests:

```bash
python -m pip install -e .[test]
pytest -q
```

## Quick Start

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json", auto_sentinel=True)

response = client.send(
    "Give me a short summary of this project.",
    model="gpt-4o-mini",
)

print(response.text)
```

## Authentication at a Glance

Install the browser extra and authorize once:

```bash
pip install "chatgpt-web-adapter[browser]"
chatgpt-web-adapter auth login --auth-file auth_data.json
```

Use `chatgpt-web-adapter auth login --force` when the saved session is rejected
and you need a completely fresh interactive login.

The command opens a persistent Chromium profile, waits for you to finish the
normal ChatGPT login, and saves reusable cookies and tokens without sending a
probe chat message. When the access token is missing or near expiry, the client calls
`/api/auth/session`, updates the access/session metadata, preserves the
browser-issued cookie jar, and atomically updates the same `auth_data.json`.

Recommended `auth_data.json` shape:

```json
{
  "accessToken": "eyJhbGciOi...",
  "cookies": {
    "__Secure-next-auth.session-token": "..."
  },
  "browserCookies": [
    {
      "name": "__Secure-next-auth.session-token.0",
      "value": "...",
      "domain": ".chatgpt.com",
      "path": "/",
      "secure": true
    }
  ],
  "headers": {
    "user-agent": "Mozilla/5.0 ..."
  }
}
```

- `accessToken` is the ChatGPT web access token from your browser session. It is not an official OpenAI API key.
- `cookies` and `headers` should come from the same account/session as the token.
- `browserCookies` preserves domain/path/expiry metadata needed to recreate a browser session without flattening scoped cookie chunks. Older files without it remain supported.
- Automatic refresh requires `__Secure-next-auth.session-token` (including chunked variants) or a top-level `sessionToken` in the file.
- Call `client.refresh_auth()` to refresh immediately. Pass `auto_refresh_auth=False` or `persist_refreshed_auth=False` to opt out of automatic refresh or file updates.
- Pass `auto_login=True` to `ChatGPTWebClient` to reopen the persistent browser profile only when auth is missing or session refresh fails.
- `.env` is optional, not required. If present, `accessToken=...` is used only as a fallback when the file token is missing or expired.
- Older files that still use `api_key` are accepted for backward compatibility, but new examples and new files should use `accessToken`.
- Inspect or refresh auth without exposing tokens with `chatgpt-web-adapter auth status` and `chatgpt-web-adapter auth refresh`.
- After the first interactive login, `auto_sentinel=True, sentinel_headless=True` can run protected writes without a visible browser window. Chromium is still required as the browser engine.

## Common Workflows

### Streaming Callback

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send(
    "Stream the answer token by token.",
    on_token=lambda token: print(token, end="", flush=True),
)
```

### Continue an Existing ChatGPT Web Conversation

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send_to_conversation(
    "https://chatgpt.com/c/...",
    "Continue from this point.",
)

print(response.text)
```

### Send an Image in a New Chat

```python
response = client.send(
    "What is shown in this image?",
    media=["screenshot.png"],
)
print(response.text)
```

`send_to_conversation()` attaches to the latest web conversation state, resolves the current parent message automatically, and preserves the detected model when possible. Model detection is best-effort because ChatGPT web payloads can change. If the model cannot be detected, the SDK uses the normal `send()` default model.

### Continue from an SDK Response

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

first = client.send("Start a conversation.")
second = client.send(
    "Continue it.",
    conversation=first.conversation,
)
```

Other common APIs:

- read conversation messages with `client.get_messages(...)`
- poll conversation status with `client.get_status(...)`
- wait for completion with `client.wait_until_completed(...)`
- approve selected tool flows with experimental `client.send_and_auto_approve(...)`
- inspect request latency with [examples/diagnose_latency.py](examples/diagnose_latency.py)
- inspect live transport events with [examples/watch_conversation.py](examples/watch_conversation.py)

## Examples

- [examples/basic_send.py](examples/basic_send.py) - send one prompt and print response metadata
- [examples/continue_saved.py](examples/continue_saved.py) - save `ChatConversation` metadata and continue later
- [examples/attach_existing.py](examples/attach_existing.py) - attach to an existing conversation URL or id
- [examples/read_messages.py](examples/read_messages.py) - read messages from an existing conversation
- [examples/status_polling.py](examples/status_polling.py) - poll conversation lifecycle status
- [examples/approve_tools.py](examples/approve_tools.py) - approve pending tool actions after review
- [examples/raw_payload.py](examples/raw_payload.py) - send an experimental raw web backend payload
- [examples/diagnose_latency.py](examples/diagnose_latency.py) - print request and streaming diagnostics
- [examples/watch_conversation.py](examples/watch_conversation.py) - watch SSE, websocket handoff, polling, and approvals live
- [examples/github_auto_approve.py](examples/github_auto_approve.py) - specialized GitHub connector approval demo

## Experimental Features

The SDK includes experimental browserless helpers for web-agent/tool approval flows:

- `approve_pending_action()`
- `wait_and_approve_pending_actions()`
- `send_and_auto_approve()`

These APIs are useful for ChatGPT web connector flows such as GitHub file creation, but they rely on reverse-engineered web behavior and should be treated as less stable than the base `send()` API.

Approval helpers are not a stable contract of this SDK. They are best-effort compatibility layers over changing ChatGPT web approval behavior and may require updates even when the base send/continue flows still work.

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

## Auth Notes

The optional browser extra creates the initial `auth_data.json` itself. Subsequent
access-token refreshes are browserless while the session cookie remains valid.
Interactive login is needed again only after ChatGPT rejects the reusable session.

## Detailed Guide

For the full SDK walkthrough, including auth flows, `warmup()`, `temporary`, `web_search`, `reasoning_effort`, conversation continuation, image inputs, response objects, and error handling, see [USAGE.md](USAGE.md).

Operational docs:

- [docs/live_smoke_checklist.md](docs/live_smoke_checklist.md)
- [docs/release_checklist.md](docs/release_checklist.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/building_on_top.md](docs/building_on_top.md)

## Package Naming

Canonical package naming is:

- repository: `chatgpt-web-adapter`
- distribution: `chatgpt-web-adapter`
- import: `chatgpt_web_adapter`

See [docs/rename_compatibility.md](docs/rename_compatibility.md).

## Status

Initial SDK baseline. The repository is intentionally small and focused on the transport layer first.
GitHub Actions validates tests on Python 3.10-3.13 across Ubuntu and Windows, and also checks that the package builds successfully.

Repository docs:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CHANGELOG.md](CHANGELOG.md)
