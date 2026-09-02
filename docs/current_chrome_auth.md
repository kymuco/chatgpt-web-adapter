# Current-Chrome Authorization

_Last updated: 2026-09-02_

`browser_login_current_tab()` authorizes CWA through the ChatGPT account in the
operator's already-running Chrome. It exists for local applications where a
separate SDK browser profile creates avoidable account and login friction.

## Contract

The caller first installs the CWA Native Messaging host and loads the packaged
extension. A login invocation then:

1. enters the same browser-authority lane used by browser-owned writes,
   canonical reads, and runtime-tab disposal;
2. creates one active additional `https://chatgpt.com/` tab in the current
   Chrome instance;
3. waits for the normal page session, allowing the operator to complete login,
   MFA, or account selection in that tab;
4. reads `/api/auth/session` in page context and applicable `chatgpt.com`
   cookies through `chrome.debugger` / CDP;
5. validates cookie domain, record count, field sizes, token sizes, and total
   payload in the extension and again in Python;
6. atomically replaces the caller-selected auth file and records the non-secret
   provenance `authSource=current-chrome-tab`;
7. detaches the debugger and closes only the tab created by this successful
   operation.

If the operation times out, its new tab remains visible so account recovery can
continue or the failure can be inspected. The bridge reports the operation as
failed and does not retry it automatically.

## Security boundary

The operation exports reusable account/session material and must be invoked
only by a trusted local caller. The broker accepts it only over loopback with
the per-process descriptor token. Credential values are excluded from errors,
logs, documentation, tests, and ordinary runtime observations.

The implementation does not:

- stop, restart, or launch Chrome;
- create or select a separate browser profile;
- read Chrome's `Cookies` database or other profile files;
- use `chrome.cookies` or `document.cookie`;
- delete, import, or rewrite browser-owned cookies;
- preserve old account credentials when a new capture succeeds;
- retry after a response is lost following delegation;
- grant ChatGPT product-write, connector, Git, or filesystem authority beyond
  writing the explicitly selected local auth file.

`fresh=True` only makes the caller's intent explicit. Current Chrome is always
the source of truth, and a successful capture replaces prior saved credentials.
It never signs the browser out or clears browser data.

## Current evidence

Deterministic tests cover the public API, double validation, strict cookie
domain matching, bounded messages, atomic cross-account replacement, sanitized
errors, public auth status, extension composition, and shared authority-lane
serialization. A signed-in Windows/Chrome live gate remains required before a
release claim. That gate must confirm the current Chrome process stays running,
one additional tab becomes active, the selected account is captured, the
debugger detaches, and no credential value reaches output or repository files.
