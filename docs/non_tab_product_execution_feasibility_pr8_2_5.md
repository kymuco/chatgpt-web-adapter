# PR8.2.5 — Non-Tab Browser-Owned Product Execution Feasibility

PR8.2.5 asks a narrower question than PR8.2.2/PR8.2.3 browserless work:

> Can the browser continue to own the ordinary ChatGPT product write while the
> execution substrate is no longer an ordinary browser tab visible in the tab strip?

The required contract is intentionally strict:

1. the surface must be a supported Chrome/extension primitive;
2. it must not require an ordinary browser tab;
3. the ordinary ChatGPT product page/session semantics must be preserved rather
   than replaced by a model/API emulation;
4. it must not depend on credential extraction/replay, challenge solving,
   browser-protection emulation, or a reconstructed private product write.

## Verdict

```text
SUPPORTED_NON_TAB_ORDINARY_CHATGPT_PRODUCT_EXECUTION_NOT_FOUND
```

This is a supported-surface/product-semantics verdict, not a claim that every
possible iframe experiment or undocumented browser trick is physically
impossible.

The proven minimum remains PR8.2.4a.3:

```text
one reusable inactive chatgpt.com tab
→ official page-owned write
→ no observed foreground activation
→ canonical browserless readback
```

## Candidate boundaries

### Manifest V3 service worker

Chrome extension service workers do not expose DOM or `window`, so they cannot
host the ordinary ChatGPT page runtime directly.

Verdict:

```text
REJECTED_NO_DOM_WINDOW
```

### `chrome.offscreen` top-level document

The Offscreen API provides a real hidden DOM document without opening a user
window or tab. However, Chrome requires the offscreen document URL to be a static
HTML file bundled with the extension.

Therefore its top-level origin is the extension, not `https://chatgpt.com`.

Verdict:

```text
REJECTED_EXTENSION_URL_ONLY
```

### Offscreen document with cross-origin ChatGPT iframe

Chrome explicitly supports cross-origin frames in offscreen documents for
purposes such as iframe scripting and DOM scraping.

That does not satisfy this PR's product contract. ChatGPT would be an embedded
third-party frame under a `chrome-extension://` top-level page, not an ordinary
top-level ChatGPT navigation. Chrome's extension storage/cookie documentation
also distinguishes embedded third-party contexts from direct top-level
navigation and documents partitioning behavior.

This PR therefore does not attempt to manufacture product parity by copying or
replaying cookies or other protected session material.

Verdict:

```text
DOES_NOT_MEET_TOP_LEVEL_PRODUCT_CONTRACT
```

### Offscreen extension API control

Chrome documents `chrome.runtime` as the only extension API available directly
inside an offscreen document. Tab/debugger orchestration would still have to
remain in another extension context.

Verdict:

```text
RUNTIME_API_ONLY
```

### `chrome.debugger` `targetId`

The debugger API can attach to targets identified by `tabId`, `extensionId`, or
`targetId`. Targets can include pages, iframes, and workers.

This is an attachment primitive. The documented API does not, by itself,
establish a supported hidden ordinary-site page creation surface that satisfies
the required top-level ChatGPT product contract.

Verdict:

```text
ATTACHMENT_PRIMITIVE_NOT_EXECUTION_SURFACE
```

### Popup, side panel, minimized window

These are either user-facing UI surfaces or non-top-level extension contexts.
They do not satisfy the hidden non-tab ordinary-product requirement.

Verdict:

```text
USER_VISIBLE_OR_NON_TOP_LEVEL_SURFACE
```

## Why no live non-tab write probe is included

The supported-surface contract fails before a product write is justified.

A live iframe/offscreen product-write experiment would test a different
contract: whether an embedded ChatGPT page can be made to behave sufficiently
like a top-level page. PR8.2.5 deliberately does not reinterpret that as
preserved ordinary product semantics.

The only live probe in this PR is read-only and reports the current proven
browser-native substrate from `BrowserNativeTurnProvider.status()`.

It never sends a turn and never creates a browser surface.

## Reopen conditions

This verdict should be reopened if Chrome later documents a supported primitive
that can host or create a non-tab top-level external web page with ordinary site
storage/session semantics, or if ChatGPT exposes a supported product execution
surface that removes the need for the page runtime while preserving the same
consumer-product contract.

## Governance

PR8.2.5 adds no:

- protected/private ChatGPT write reconstruction;
- cookie or credential extraction/replay;
- challenge, Sentinel, Turnstile, or proof emulation;
- browser fingerprint emulation;
- automatic write retry;
- hidden browser-process launcher;
- offscreen/iframe product-write implementation.

The existing PR8.2.4a.3 reusable inactive-tab transport remains unchanged.

## Primary sources

Reviewed 2026-08-15:

- Chrome Offscreen API:
  `https://developer.chrome.com/docs/extensions/reference/api/offscreen`
- Chrome MV3 service-worker migration:
  `https://developer.chrome.com/docs/extensions/develop/migrate/to-service-workers`
- Chrome Debugger API:
  `https://developer.chrome.com/docs/extensions/reference/api/debugger`
- Chrome extension storage and cookies:
  `https://developer.chrome.com/docs/extensions/develop/concepts/storage-and-cookies`
