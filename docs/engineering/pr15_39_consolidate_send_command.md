# PR15.39 — Consolidate sendCommand ownership

## Purpose

Continue #107 by removing the remaining source-order replacement of the shared
CDP command function:

```text
sendCommand(debuggee, method, params)
```

Historically the effective production chain was:

```text
service_worker.js base CDP transport
→ service_worker_hotfix.js mouse-release submit fallback
→ service_worker_ordinary_text_identity_authority.js commit-boundary observation
```

Both later layers captured the previous public binding and replaced the same
global name.

PR15.39 makes those stages explicit and gives the public name one owner.

## Explicit stages

Base transport:

```text
_cwaBaseSendCommand(...)
```

Hotfix transport:

```text
_cwaHotfixSendCommand(...)
→ _cwaBaseSendCommand(...)
```

Ordinary-text observation:

```text
_cwaOrdinaryIdentitySendCommand(...)
→ observe protected commit boundary when active
→ _cwaHotfixSendCommand(...)
```

The sole public production owner is:

```text
service_worker_send_command.js
```

with final composition:

```text
sendCommand(...)
→ _cwaOrdinaryIdentitySendCommand(...)
→ _cwaHotfixSendCommand(...)
→ _cwaBaseSendCommand(...)
→ chrome.debugger.sendCommand(...)
```

## Preserved hotfix behavior

The hotfix layer still owns only the reviewed mouse-submit fallback behavior:

- non-mouse CDP commands delegate directly to the base transport;
- mousePressed initializes submit observation and forces `buttons: 1`;
- mouseReleased delegates with `buttons: 0`, then runs the existing bounded
  fallback ladder;
- fallback commands intentionally use the base transport directly so they do not
  recursively re-enter the mouse-release hotfix.

No hotfix fallback behavior is moved into ordinary-text identity logic.

## Preserved ordinary-text identity boundary

The ordinary-text layer still observes the exact protected commit boundary
before transport delegation.

When an ordinary identity context is active and an official page turn is in
progress:

```text
Input.dispatchMouseEvent / mouseReleased / left
or
Input.dispatchKeyEvent / keyDown / Enter
```

may arm the existing ordinary-text request-correlation state.

The layer then delegates the unchanged arguments to
`_cwaHotfixSendCommand`.

The observer does not itself grant write, retry, or finality authority.

## Bootstrap placement

The extension bootstrap loads base and hotfix helpers through the existing
recovery/observability chain. The write domain later loads ordinary-text
identity and then the sole public owner:

```text
...
service_worker_text_submit_commit_hardening_pr11_3.js
→ service_worker_ordinary_text_identity_authority.js
→ service_worker_send_command.js
```

Earlier modules define functions that resolve `sendCommand` dynamically when
invoked; no reviewed import-time path requires a completed CDP command before
the write-domain owner is installed.

## Static target

```text
sendCommand public definitions = 1
sendCommand runtime assignments = 0
_originalCoreSendCommand aliases = 0
_cwaOrdinaryIdentityPriorSendCommand aliases = 0
```

## Authority

PR15.39 changes ownership/composition only.

It does not add:

- new CDP methods;
- new submit strategies;
- retry authority;
- request identity authority;
- navigation authority;
- canonical finality.

## Out of scope

After this slice, the remaining obvious shared-name wrapper is the smaller
`connectNativeBridge` product-state chain.

Tracking: #107
