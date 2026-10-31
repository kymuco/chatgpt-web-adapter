# Security

`chatgpt-web-adapter` (CWA) works with authenticated consumer AI web sessions. The **primary ChatGPT SDK** is the Direct HTTP `BrowserlessHTTPClient`, and `cwa send` defaults to it since `v0.4.1`. A separate, high-trust Chrome extension / Native Messaging bridge remains for **experimental** browser-owned interactions; DeepSeek Web and Gemini Web are also experimental. Treat all provider-session, browser and product-capability material as sensitive.

## Sensitive material

The following must be treated as secrets or high-sensitivity local data:

- `auth_data.json` and equivalent reusable auth/session stores;
- access, refresh and session tokens;
- provider session cookies and equivalent authenticated browser state;
- persistent signed-in Chromium profiles used by supported providers;
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

## Browser-owned bridge

Browser-owned is a **secondary experimental ChatGPT UI transport**, kept as a legacy SDK default for compatibility, not a preferred production path. Experimental DeepSeek/Gemini provider proofs also use the same local browser bridge with provider-specific page semantics. Direct HTTP is a separate SDK and does not silently fall back to this bridge.

The browser-native extension has Chrome's high-trust `debugger` permission. Load only the extension shipped with this package/source tree and treat changes to extension/service-worker/Native Messaging/provider code as security-sensitive product-runtime changes.

The local broker binds to loopback and authenticates SDK-facing requests with a random per-process token stored in local state. That token is not sent to `chatgpt.com`.

The extension/native bridge is designed not to return provider cookies, authorization headers, Sentinel/Turnstile material, raw conversation streams, arbitrary page state, or equivalent provider credentials through its ordinary SDK-facing contract.

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

The shared canonical ChatGPT client supports a **narrow, governed**
`handoff_generated_artifact(...)` operation for a uniquely identified,
conversation-owned product file. It requires an explicit caller-chosen
destination, enforces no implicit overwrite, and verifies retrieved bytes.
User uploads, arbitrary sandbox links, unrelated conversations and guessed
artifact identifiers are not covered.

Generated image/report readback has separate experimental and read-only limits.
Never expose signed file locators or assume a tool-generated filename alone
proves identity. Historical [PR10.1](docs/generated_artifact_handoff_pr10_1.md)
records an earlier unsupported state; it is not the current handoff contract.

## Challenge and anti-abuse boundary

This boundary applies across providers. CWA does not provide or seek to provide:

- Turnstile solving;
- proof-token synthesis;
- anti-abuse challenge bypass;
- replay-oriented protection credential machinery;
- an alternative username/password authentication protocol.

The experimental ChatGPT `browserless-request` transport fails closed when current product protections require evidence that CWA cannot legitimately provide. It does not silently fall back to another write transport or provider.

## Session and profile safety

For ChatGPT's stable authentication workflow, the SDK uses the normal ChatGPT login page. Experimental page-owned providers rely on the corresponding product already being authenticated in the browser profile. Protect every persistent provider profile like any other signed-in browser profile.

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
