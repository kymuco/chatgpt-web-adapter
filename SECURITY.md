# Security

`chatgpt-web-adapter` works with existing `chatgpt.com` session material. Treat that material as sensitive.

## Sensitive Data

The following should be treated as secrets:

- `accessToken`
- session cookies
- the persistent Chromium profile
- proof tokens
- Turnstile tokens
- sanitized traces before you verify they are actually sanitized

## Do Not Commit

Do not commit:

- `auth_data.json`
- copied or repository-local browser profiles
- `.env` files containing session material
- raw browser or network captures
- local debug trace directories
- copied request headers that still contain auth/session values

## Local Debugging

If you use debug trace mode or manual traffic scans:

- store artifacts in a local-only directory
- sanitize auth/session headers before sharing
- prefer repository-local exclusions such as `.git/info/exclude` for temporary trace directories

## Scope

This project provides local browser-assisted login, reusable credential storage,
and session refresh for a ChatGPT web session. These features do not turn the
undocumented web backend into an official or supported authentication API.

The project does not provide:

- an alternative username/password login protocol
- a challenge solver or anti-abuse bypass
- server-side secret storage
- guarantees that a copied `auth_data.json` works without its related profile

The SDK profile uses the normal ChatGPT login page and must be protected like any
other signed-in browser profile. See
[docs/authentication.md](docs/authentication.md) for the session lifecycle.

## Reporting

If you discover a security issue in the repository itself, report it privately to the maintainer instead of opening a public issue with sensitive details.
