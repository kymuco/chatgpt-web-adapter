# PR8.2.4 — Minimal Browser-Owned Product Write Runtime, Read/Session Plane Separation and Failure-Safe Provider Governance

PR8.2.0–PR8.2.3 established that ordinary ChatGPT canonical reads and session renewal can operate browserlessly, while no documented supported non-browser external ordinary-ChatGPT write surface was found. PR8.2.4 therefore productionizes the smallest proven browser-owned write boundary instead of expanding private protected-write reconstruction.

## Runtime split

- **Read plane:** `BROWSERLESS_CANONICAL_HTTP`
- **Session plane:** `BROWSERLESS_SESSION_HTTP`
- **Write plane:** `BROWSER_NATIVE_PAGE_OWNED_WRITE`

The production facade never launches a browser. Browser/session bootstrap remains an explicit operator concern. Once Chrome + the packaged extension are connected, the extension may create or recover its dedicated inactive ChatGPT runtime tab on demand.

## Health contract

`BrowserOwnedProductWriteRuntime.health()` returns a structured readiness snapshot.

For a new conversation, readiness requires only a live Native Messaging bridge and connected extension. A pre-existing runtime tab is diagnostic only.

For continuation, canonical browserless status must also be `completed`, and it is rechecked at the commit point immediately before browser delegation. A running, tool-active, unknown, or unreadable conversation is rejected before browser-native delegation.

## Failure semantics

Two failure classes are intentionally separated:

1. **Preflight failure** — write delegation never started. `write_may_have_been_submitted=false`; automatic retry remains disabled, but `manual_retry_safe_after_repair=true`.
2. **Delegated write failure** — no automatic retry. Once the provider is invoked, the page-owned POST may already have happened. The facade marks the outcome as unknown and requires canonical reconciliation before another user turn.

If the browser-owned write succeeded but canonical final assistant readback times out, the stronger `BROWSER_OWNED_WRITE_ACCEPTED_READBACK_INCOMPLETE` classification is used. Retrying the prompt is forbidden because it could duplicate a turn that ChatGPT already accepted.

## Invariants

- no direct private product write;
- no Sentinel/Turnstile/challenge expansion;
- no cookie/credential extraction;
- no automatic write retry;
- no foreground activation requirement;
- runtime tab may be created lazily by the already connected extension;
- canonical SDK readback remains the source of assistant response truth.

## Operator probe

Health only:

```powershell
python examples/browser_owned_write_runtime.py `
  --conversation <CONVERSATION_ID>
```

Explicit write:

```powershell
python examples/browser_owned_write_runtime.py `
  --conversation <CONVERSATION_ID> `
  --send "Reply with exactly: SDK_RUNTIME_OK"
```

The second command is intentionally explicit: PR8.2.4 does not send a product turn during a health probe.
