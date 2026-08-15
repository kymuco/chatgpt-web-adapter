# PR8.3 — Production Browser-Owned ChatGPT Transport Integration

PR8.3 promotes the proven PR8.2.4–PR8.2.5 browser-owned ordinary-ChatGPT write path from an experimental side API into a production runtime contract suitable for HDE, Python SDK callers, and terminal use.

## Outcome

The new public assembly path is:

```text
assemble_product_runtime(transport="browser-owned")
  -> ChatGPTProductRuntime
      -> browserless canonical read/status/session plane
      -> BrowserOwnedProductWriteRuntime for exactly one page-owned write
      -> canonical browserless assistant readback
```

The production runtime does not silently select or fall back to the legacy direct-web write path.

## Public contract

`ChatGPTProductRuntime` exposes:

- `health()` / `readiness()`
- `send()` / `send_text()`
- `send_text_observed()`
- `get_status()`
- `get_messages()`
- `attach_conversation()`
- `governance()`

The supported production transport set is intentionally closed:

```text
browser-owned
```

An unsupported transport name fails before any write can be delegated.

## Lifecycle assembly

`assemble_product_runtime()` creates `ChatGPTWebClient` with:

```text
auto_refresh_auth = true
auto_login        = false
auto_sentinel     = false
```

This preserves the already-proven browserless saved-session renewal/read plane while preventing production runtime construction from silently launching an interactive login browser or enabling the legacy Sentinel/direct-write machinery.

Callers may inject an already-configured client or a `BrowserNativeTurnProvider` for tests/integration ownership.

## New chat

A runtime tab is not required before a new turn.

If Native Messaging and the extension are connected, `health(None)` may be ready with:

```text
runtime_tab_id = null
runtime_tab_preexisting = false
```

The extension may then provision one inactive ChatGPT runtime tab on demand. PR8.2.4a.3 owns reconciliation and reuse.

## Continuation

For an existing conversation, readiness remains gated on browserless canonical status:

```text
canonical_status == completed
```

The underlying browser-owned writer repeats that canonical check at the commit point before delegation.

## Write ambiguity

No automatic retry is introduced.

Once delegation to the browser-owned write plane begins, an ambiguous outcome remains reconciliation-required. PR8.3 does not transform transport errors into retries and does not fall back to another write provider.

## Process reconstruction / daily use

Runtime assembly does not own the browser process or runtime-tab lifetime. A newly constructed `ChatGPTProductRuntime` observes the already-running Native Messaging broker/extension state through `BrowserNativeTurnProvider.status()`.

Therefore a terminal/HDE process can restart while the reusable inactive ChatGPT tab remains owned by the extension/browser runtime.

## CLI

Production runtime status:

```powershell
chatgpt-web-adapter runtime status \
  --transport browser-owned \
  --conversation <conversation-id>
```

Production turn:

```powershell
chatgpt-web-adapter runtime send "hello" \
  --transport browser-owned \
  --conversation <conversation-id>
```

Omit `--conversation` for a new chat.

CLI output is structured JSON so HDE or shell tooling can consume conversation id, message id, model, backend status, and runtime-tab observation without parsing rendered ChatGPT DOM.

## Governance invariants

```text
transport selection is closed-set
fallback transport = none
legacy direct-write fallback = false
interactive login during assembly = false
Sentinel/direct-write enablement during assembly = false
canonical readback required = true
automatic ambiguous-write retry = false
browser process launch owned by runtime = false
foreground activation requested = false
```

## Acceptance gates

```text
P0  production browser-owned provider is publicly selectable
P1  unsupported transport fails closed
P2  browserless read/session ownership remains unchanged
P3  assembly cannot auto-login or auto-enable Sentinel
P4  new-chat readiness works without a preexisting runtime tab
P5  continuation readiness requires canonical completed
P6  send delegates exactly once to BrowserOwnedProductWriteRuntime
P7  no legacy direct-write fallback exists
P8  canonical final assistant readback remains required
P9  runtime-tab reconciliation/reuse is inherited from PR8.2.4a.3
P10 process reconstruction observes external reusable-tab state
P11 CLI status/send use the same production assembly contract
P12 HDE can consume one stable runtime object (`send`) for write + canonical lifecycle inspection
```

## Non-goals

PR8.3 does not:

- make the inactive ChatGPT runtime tab disappear from Chrome;
- add a non-tab execution surface (PR8.2.5 closed that supported-surface search);
- reconstruct private protected ChatGPT writes;
- extract/replay browser protection credentials;
- add challenge solving or browser fingerprint emulation;
- change model-selection or tool/media support of the browser-native text-turn provider;
- remove the legacy `ChatGPTWebClient.send()` API in this PR.
