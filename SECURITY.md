# Security

`chatgpt-web-adapter` works with existing `chatgpt.com` session material. Treat that material as sensitive.

## Sensitive Data

The following should be treated as secrets:

- `accessToken`
- session cookies
- the persistent Chromium profile
- proof tokens
- Turnstile tokens
- the local browser-native bridge descriptor/token while the Native Messaging host is running
- sanitized traces before you verify they are actually sanitized

## Do Not Commit

Do not commit:

- `auth_data.json`
- copied or repository-local browser profiles
- browser-native runtime descriptor files
- `.env` files containing session material
- raw browser or network captures
- local debug trace directories
- copied request headers that still contain auth/session values

## Local Debugging

If you use debug trace mode or manual traffic scans:

- store artifacts in a local-only directory
- sanitize auth/session headers before sharing
- prefer repository-local exclusions such as `.git/info/exclude` for temporary trace directories

The browser-native bridge binds its SDK-facing broker to loopback only and authenticates each local request with a random per-process token stored in the user's local state directory. The token is never sent to `chatgpt.com` and the extension never returns cookies, Sentinel credentials, Turnstile state, or raw conversation SSE through Native Messaging.

The browser-native extension has the high-trust Chrome `debugger` permission. Load only the extension shipped with this package/source tree and treat modification of those extension files as security-sensitive code changes.

## Scope

This project provides local browser-assisted login, reusable credential storage,
session refresh, and an experimental browser-native turn runtime for a ChatGPT
web session. These features do not turn the undocumented web backend into an
official or supported authentication API.

The project does not provide:

- an alternative username/password login protocol
- a challenge solver or anti-abuse bypass
- server-side secret storage
- guarantees that a copied `auth_data.json` works without its related profile
- a mechanism for exporting or replaying browser-native Sentinel / Turnstile credentials

The SDK profile uses the normal ChatGPT login page and must be protected like any
other signed-in browser profile. The browser-native runtime intentionally leaves
a protected write inside the official logged-in ChatGPT page and uses the SDK's
existing authenticated read path only after that page-owned turn completes.

See [docs/authentication.md](docs/authentication.md) for the session lifecycle and
[docs/browser_native_runtime.md](docs/browser_native_runtime.md) for the bridge
security boundary.

## Reporting

If you discover a security issue in the repository itself, report it privately to the maintainer instead of opening a public issue with sensitive details.
