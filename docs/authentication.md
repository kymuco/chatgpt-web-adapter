# Authentication and Session Lifecycle

`chatgpt-web-adapter` uses an existing ChatGPT web account session. It does not
use an OpenAI API key and does not implement an alternative login protocol.

## Install

For the released primary Direct HTTP SDK:

```bash
python -m pip install chatgpt-web-adapter
```

The Direct HTTP SDK requires Node.js 24+, curl and a valid saved ChatGPT web
auth file, but no Chrome tab for sending. To obtain initial authorization, `auth login` requires the optional `[browser]`
extra and uses an interactive browser; an existing signed-in Chrome session
can also be synced by the separately authorized browser sync flow.

For secondary browser-owned UI interaction and legacy login support:

```bash
python -m pip install "chatgpt-web-adapter[browser]"
```

Published `v0.4.1` includes the primary Direct HTTP SDK and uses it by default
for `cwa send`. A source checkout of current `main` also includes later
Project/GPT conversation URL parsing not present in that tagged wheel.

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

Recommended ChatGPT client for operations with Direct HTTP live evidence:

```python
from chatgpt_web_adapter import BrowserlessHTTPClient

client = BrowserlessHTTPClient(auth_file="auth_data.json")
```

This client intentionally does not launch a browser or enable automatic
`auto_login`/`auto_sentinel` on send. It also does not inherit the legacy
client's automatic session-refresh behavior. Obtain valid authorization
separately and reconcile uncertain sends before any new write.

Historical compatibility-only `ChatGPTWebClient` settings:

```python
from chatgpt_web_adapter import ChatGPTWebClient

legacy = ChatGPTWebClient(
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

For the historical `ChatGPTWebClient` auth lifecycle, a missing or near-expiry
access token on construction is refreshed
through `GET https://chatgpt.com/api/auth/session`. The refresh uses the saved
session cookies, updates access/session metadata, preserves the structured
browser cookie jar, and atomically rewrites `auth_data.json`. It does not launch
Chromium.

Refresh explicitly with:

```bash
chatgpt-web-adapter auth refresh --auth-file auth_data.json
```

or with `client.refresh_auth()`.

Canonical conversation reads (including paginated full-history GETs) can also
recover **once per read operation** if the server specifically returns
`401` with `error.code=token_expired`. With the default
`auto_refresh_auth=True`, CWA refreshes the stored session via the existing
bounded auth worker and retries **only the failed GET with the same URL/cursor**;
previously fetched pages are retained. `auto_refresh_auth=False` disables this
read recovery too. If the saved session cookie has expired, refresh fails and
normal interactive reauthentication is required.

This is strictly a **read-only** convenience. It never retries a ChatGPT
message submit, attachment upload, or any other potentially effectful request.
A generic `401`, `403`, failed refresh, or a second `token_expired` still fails
closed; there is no silent browser-login or transport fallback.

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

## Historical browser-owned use on Linux without a desktop

This section concerns legacy browser-owned / Sentinel-dependent workflows, **not**
Direct HTTP sending after an authenticated session has already been saved.
The historical sequence is:

1. Perform the first interactive login where Chromium can display a window, or
   through a temporary desktop/X session on the target machine.
2. Preserve the SDK profile and `auth_data.json` on that same trusted machine.
3. Run later writes with `sentinel_headless=True`.

Copying only `auth_data.json` to a clean server is not guaranteed to reproduce
the **browser-owned** session. For the separate primary Direct HTTP send path,
Chromium is not required during sending; see the SDK setup requirements above.

## Sync existing Chrome session through CWA (opt-in)

For an authenticated Chrome profile with a connected CWA extension, use:

```powershell
chatgpt-web-adapter auth sync-browser --auth-file auth_data.json
```

The extension service worker requests `/api/auth/session` with
`credentials: "include"` and reads only ChatGPT-scoped cookies via the
`chrome.cookies` API. **No ChatGPT tab is needed**, and the operation never
launches Zendriver, opens or activates windows, navigates tabs, or attaches
the debugger. The existing browser process and extension **must** still be
running; this is not a credential-free HTTP login.

The feature introduces the Chrome extension `cookies` permission, in
addition to its existing `https://chatgpt.com/*` host permission. Chrome
may require reviewing the new permission when reloading/upgrading CWA.
The resulting credentials are sent only via CWA's authenticated local
Native Messaging bridge and atomically stored in `auth_data.json`; never
print or upload this file. If the browser profile has no usable session,
cookie access is disallowed, or the request fails, synchronization fails
closed without replacing the existing auth file.

To enable automatic browser synchronization on a canonical conversation
`401 token_expired`, opt in once in your SDK constructor:

```python
client = ChatGPTWebClient(
    auth_file="auth_data.json",
    auto_browser_auth_sync=True,
)
```

The SDK then synchronizes the browser session and repeats **only that GET**,
at most once. Without the opt-in, existing auth-refresh behavior is unchanged.
This is a deliberate exception to the normal Native Messaging policy of not
exporting credentials. It is restricted to the authenticated local broker;
do not enable it on untrusted local machines or expose the bridge descriptor.
A successfully updated file is **not** proof that an independent curl request
will be accepted by the ChatGPT backend.

