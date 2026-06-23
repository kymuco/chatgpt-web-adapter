# Security

`chatgpt-web-adapter` works with existing `chatgpt.com` session material. Treat that material as sensitive.

## Sensitive Data

The following should be treated as secrets:

- `accessToken`
- session cookies
- proof tokens
- Turnstile tokens
- sanitized traces before you verify they are actually sanitized

## Do Not Commit

Do not commit:

- `auth_data.json`
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

This project does not provide:

- secure login acquisition
- token refresh
- browser credential management
- server-side secret storage

It only consumes auth material that already exists in a local environment.

## Reporting

If you discover a security issue in the repository itself, report it privately to the maintainer instead of opening a public issue with sensitive details.
