# Authentication and Session Lifecycle

`chatgpt-web-adapter` uses an existing ChatGPT web account session. It does not
use an OpenAI API key and does not implement an alternative login protocol.

## Install the Browser Extra

```bash
python -m pip install "chatgpt-web-adapter[browser]==0.1.7"
```

The core HTTP transport has no Python runtime dependencies, but current
protected ChatGPT writes require the optional Chromium integration.

## First Login

```bash
chatgpt-web-adapter auth login --auth-file auth_data.json
```

The command opens the SDK's persistent Chromium profile. Complete the normal
ChatGPT login in that window and leave it open until the command reports that
authorization was saved.

Default profile locations:

- Windows: `%LOCALAPPDATA%\chatgpt-web-adapter\browser-profile`
- macOS: `~/Library/Application Support/chatgpt-web-adapter/browser-profile`
- Linux: `$XDG_STATE_HOME/chatgpt-web-adapter/browser-profile`, or
  `~/.local/state/chatgpt-web-adapter/browser-profile`

Set `CHATGPT_WEB_ADAPTER_PROFILE_DIR` or pass `--profile-dir` to override it.

## What Is Stored

The login command creates two related pieces of reusable state:

1. `auth_data.json` contains the current access token, flat cookies used by the
   HTTP transport, structured `browserCookies`, request headers, and expiry
   metadata.
2. The persistent Chromium profile contains the browser-side session needed to
   run the official ChatGPT page and obtain current one-shot Sentinel evidence.

`browserCookies` preserves cookie domain, path, expiry, SameSite, priority, and
source metadata. The flat `cookies` mapping remains for HTTP compatibility.

Neither `proof_token` nor `turnstile_token` is persisted by the current auth
flow. Sentinel credentials are short-lived, single-use values kept in memory.

Treat both the JSON file and profile directory as secrets. Do not commit, share,
or attach them to bug reports.

## Normal Startup

Recommended client for an application that sends messages:

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(
    auth_file="auth_data.json",
    auto_login=True,
    auto_sentinel=True,
    sentinel_headless=True,
)
```

- `auto_login=True` opens the persistent profile only if auth is missing or
  `/api/auth/session` refresh fails.
- `auto_sentinel=True` obtains a fresh official-page Sentinel bundle for a
  protected write.
- `sentinel_headless=True` runs Chromium without a visible window after the
  first interactive login.

Headless is not browserless: Chromium is still running as the browser engine.

## Refresh Behavior

On client construction, a missing or near-expiry access token is refreshed
through `GET https://chatgpt.com/api/auth/session`. The refresh uses the saved
session cookies, updates access/session metadata, preserves the structured
browser cookie jar, and atomically rewrites `auth_data.json`. It does not launch
Chromium.

Refresh explicitly with:

```bash
chatgpt-web-adapter auth refresh --auth-file auth_data.json
```

or with `client.refresh_auth()`.

## Status Without Exposing Secrets

```bash
chatgpt-web-adapter auth status --auth-file auth_data.json
```

The command reports token/session expiry, structured cookie count, persistent
profile location, and whether the profile exists. It does not print credential
values.

## Forced Reauthentication

Use a forced login when ChatGPT rejects the saved session or the persistent
profile belongs to the wrong account:

```bash
chatgpt-web-adapter auth login --force --auth-file auth_data.json
```

`--force` deletes ChatGPT session-cookie variants from the SDK profile before
opening the login page. It does not delete unrelated browser data.

## Concurrent Processes

Only one process can use the same persistent Chromium profile at a time. The SDK
uses a cross-process lock around login and Sentinel capture. A second process
waits briefly and then raises a clear profile-busy error instead of corrupting
the profile.

Use separate `browser_profile_dir` values if truly independent concurrent
browser sessions are required.

## Linux Without a Desktop

The supported sequence is:

1. Perform the first interactive login where Chromium can display a window, or
   through a temporary desktop/X session on the target machine.
2. Preserve the SDK profile and `auth_data.json` on that same trusted machine.
3. Run later writes with `sentinel_headless=True`.

Copying only `auth_data.json` to a clean server is not guaranteed to reproduce
the browser session. A completely Chromium-free protected-write mode is not
currently supported.
