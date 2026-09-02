# Security

`chatgpt-web-adapter` (CWA) works with an existing authenticated `chatgpt.com` session and, on the current production write path, a high-trust local Chrome extension / Native Messaging bridge. Treat all session, browser and product-capability material accordingly.

## Sensitive material

The following must be treated as secrets or high-sensitivity local data:

- `auth_data.json` and equivalent reusable auth/session stores;
- access, refresh and session tokens;
- ChatGPT session cookies;
- the persistent signed-in Chromium profile;
- Native Messaging runtime descriptors and per-process bridge tokens;
- Sentinel, Turnstile, proof and conduit credentials/tokens;
- authorization headers and copied request headers;
- signed URLs or other capability-bearing locator values;
- raw connector arguments/results and retrieved private connector content;
- raw network/browser captures before verified sanitization;
- debug traces before verified sanitization.

A value being observable inside the browser does not make it safe to export through the SDK.

## Do not commit or publish

Do not commit, attach to public issues, or paste into public PRs:

- `auth_data.json`;
- copied/repository-local signed-in browser profiles;
- `.env` files containing session material;
- browser-native runtime descriptor/token files;
- raw browser/network traffic captures;
- unsanitized trace directories;
- raw connector payloads or provider responses containing private data;
- signed generated-artifact download URLs or similar locator credentials;
- request headers containing auth/session/protection credentials.

Use local-only directories and repository-local exclusions such as `.git/info/exclude` for temporary traffic/debug material.

## Production browser-owned bridge

The production protected-write transport is `browser-owned`.

The browser-native extension has Chrome's high-trust `debugger` permission. Load only the extension shipped with this package/source tree and treat changes to extension/service-worker/Native Messaging code as security-sensitive product-runtime changes.

The local broker binds to loopback and authenticates SDK-facing requests with a random per-process token stored in local state. That token is not sent to `chatgpt.com`.

The extension/native bridge is designed not to return cookies, authorization headers, Sentinel credentials, Turnstile state, raw conversation SSE, or arbitrary page state through its ordinary SDK-facing runtime contract.

The explicit `browser_login_current_tab()` operation is a narrow credential-capture exception. It may return only the current `chatgpt.com` access/session material needed to atomically replace the caller-selected local auth file. The extension filters cookie domains and payload size before crossing Native Messaging; Python validates the same boundaries again. The operation is authenticated by the loopback descriptor token, shares the browser-authority lane, never logs credential values, and never reads Chrome profile databases. Treat invocation of this operation as authorization to export the current signed-in ChatGPT session into the selected local auth file.

## Product observation privacy

Structured product observations are intentionally narrower than the underlying web-product data.

The typed observation layer must not export:

- private reasoning/thought content;
- raw tool arguments or results;
- arbitrary raw product metadata/SSE;
- connector/provider credentials;
- OAuth/access/refresh tokens;
- cookies or authorization headers;
- retrieved private connector content;
- arbitrary raw DOM text/HTML;
- capability-bearing signed locator values.

Source/citation URLs additionally reject known credential-bearing/signed URL forms before entering the public observation boundary.

Observation never grants approval, connector authorization, write/retry authority, canonical finality, or local filesystem/Git/workspace authority.

## Generated-artifact boundary

PR10.1 deliberately does **not** implement generated-artifact download/materialization on the current product surface.

Current frozen status:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

CWA does not export candidate artifact locator values and does not synthesize artifact identity from filename, assistant prose, DOM position, message order, URL similarity, or minified React/update-queue internals.

A future handoff may reopen only after a stable product-owned artifact identity and a safe browser-owned resolution path are separately proven. Any eventual local write must also require explicit caller destination/overwrite authority and must keep capability-bearing locators private.

See [`docs/generated_artifact_handoff_pr10_1.md`](docs/generated_artifact_handoff_pr10_1.md).

## Challenge and anti-abuse boundary

CWA does not provide or seek to provide:

- Turnstile solving;
- proof-token synthesis;
- anti-abuse challenge bypass;
- replay-oriented protection credential machinery;
- an alternative username/password authentication protocol.

The experimental `browserless-request` transport fails closed when current product protections require evidence that CWA cannot legitimately provide. It does not silently fall back to another write transport.

## Session and profile safety

The SDK uses the normal ChatGPT login page for interactive authentication. Protect the persistent browser profile like any other signed-in browser profile.

A copied `auth_data.json` is sensitive even when it is insufficient by itself to reproduce a complete signed-in environment. Do not use that uncertainty as a reason to handle it less carefully.

See [`docs/authentication.md`](docs/authentication.md).

## Debugging and traces

When investigating product drift or transport behavior:

- capture the minimum evidence needed;
- prefer structural/key-presence diagnostics over raw values;
- redact auth/session/protection headers before sharing;
- do not export private reasoning or connector/private-provider payloads;
- keep raw traces local;
- delete or isolate traffic captures after the investigation when they are no longer needed.

Research/diagnostic code is not exempt from the security boundary merely because it is not part of the production API.

## Dependency and release integrity

Release CI validates source tests, built distribution metadata/contracts, packaged extension assets, and exact installed-wheel behavior. Security-sensitive packaging or extension changes should preserve those gates rather than weakening them to accept an unexpected artifact shape.

See [`docs/release_checklist.md`](docs/release_checklist.md).

## Reporting security issues

If you discover a security issue in the repository itself, report it privately to the maintainer instead of opening a public issue containing sensitive reproduction data.

If a public issue is appropriate for a non-sensitive bug, remove all session/account/browser/connector/locator material before posting.
