# PR8.2 — Supported Browserless ChatGPT Product Transport Feasibility, Product/Execution Boundary Mapping and Minimal Runtime Governance

PR8.2 answers a bounded question: can an ordinary authenticated ChatGPT product turn be executed from a standalone process without Chrome, Chromium, WebView, or another browser runtime while preserving the consumer ChatGPT product/session surface?

## Current verdict

`SUPPORTED_BROWSERLESS_PRODUCT_WRITE_NOT_FOUND`

This is deliberately not `IMPOSSIBLE`. It means that no supported browser-independent ordinary ChatGPT product write surface has been identified. The verdict may be reopened if OpenAI later documents such an interface.

## Capability map

- **B0 — canonical conversation read:** PASS. Existing SDK HTTP/curl reads can inspect an existing conversation without a browser process.
- **B1 — saved-session reuse:** PASS_WITH_PRECONDITION. Browserless reads require still-valid saved authorization and do not perform interactive repair.
- **B2 — interactive auth bootstrap:** BROWSER_REQUIRED in the current adapter.
- **B3 — supported consumer ChatGPT turn API:** SUPPORTED_BROWSERLESS_PRODUCT_WRITE_NOT_FOUND.
- **B4 — Sign in with ChatGPT:** IDENTITY_ONLY for this objective; it is not an ordinary ChatGPT conversation/memory turn API.
- **B5 — Apps SDK / MCP:** REVERSE_DIRECTION; tools and data are connected into ChatGPT rather than exposing ChatGPT as a client turn service.
- **B6 — OpenAI API:** SEPARATE_PRODUCT; browserless, but not the same consumer ChatGPT subscription/session surface.
- **B7 — minimum supported product-write runtime:** BROWSER_NATIVE_BASELINE. PR8.1/PR8.1.1 remain the minimum proven substrate because the official page owns the protected write.

## Governance

PR8.2 is read-only research. It does not add or extend direct protected writes, browser fingerprint emulation, challenge solvers, Sentinel/Turnstile emulation, or extraction/replay of browser protection credentials.

A future `BrowserlessTurnProvider` may only graduate when a supported browser-independent ChatGPT product write interface is identified and documented. Absence of such an interface must not be papered over by reverse-engineering protective mechanisms.

## Live B0 probe

With Chrome fully closed and existing saved authorization still valid:

```powershell
python examples/browserless_feasibility.py `
  --conversation <conversation-id>
```

The probe constructs `ChatGPTWebClient` with:

```text
auto_refresh_auth = false
auto_login        = false
auto_sentinel     = false
```

It performs only `get_status()` and `get_messages()` against an existing conversation. It never sends a prompt, performs product-write preparation, or invokes the browser-native provider.

The JSON report intentionally excludes message text. It emits only bounded metadata such as status, sampled message count, and the last sampled message id.

## Graduation rule

PR8.2 may close with a negative product-write verdict if B0 is live-proven and no supported browser-independent ordinary ChatGPT product write surface exists. That is a useful architectural result: HDE must then choose between the browser-native ChatGPT product substrate and a separate browserless API-based runtime with HDE-owned continuity.
