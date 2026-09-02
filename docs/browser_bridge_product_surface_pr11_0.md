# PR11.0 — Browser Bridge Product Surface

PR11.0 turns the existing unpacked Chrome extension from a mostly invisible development bridge into a small, legible CWA product surface without changing ChatGPT write, finality, capability or downstream-authority contracts.

## Product goal

The extension should feel like a normal companion surface for `chatgpt-web-adapter`, not like a debugger, DevTools panel or infrastructure monitor.

The visible product layer therefore prioritizes the questions a user actually has:

```text
Is CWA ready?
Is my local runtime connected?
What can I do from here?
```

Implementation details remain available only as diagnostics.

## Visual identity

The CWA mark is independent from OpenAI/ChatGPT branding.

PR11.0 visual v2 replaces the earlier bracket/debugger-like symbol with a softer linked-shape mark: two rounded parts connected as one adapter. The mark intentionally avoids terminal brackets, shields, locks or imitation of the OpenAI logo.

The same identity is used by:

- Chrome extension icons (`16`, `32`, `48`, `128`);
- popup product header;
- repository hero asset.

## User-facing popup

The default popup shows:

- product name and a short purpose statement;
- one primary state: `Ready`, `Working`, `Needs attention`, or `Status unavailable`;
- `Local runtime` as the main connection summary;
- ChatGPT wording that says it opens when needed rather than claiming authentication state CWA has not proven;
- `Open ChatGPT` as the primary explicit action;
- `Copy diagnostics` as a secondary explicit action;
- a collapsed `Details` section for engineering fields.

The main screen deliberately does **not** lead with `Native host`, `Runtime tab`, `Browser-owned`, protocol numbers, or no-write disclaimers. Those terms are useful diagnostics, not first-impression product copy.

## What the popup may observe

The popup asks the service worker for one local sanitized status object:

```text
extensionVersion
protocolVersion
nativeHostConnected
runtimeTabPresent
runtimeTabRouteKind
busy
transport = browser-owned
```

`runtimeTabRouteKind` is intentionally coarse:

```text
not_created
stale
chatgpt
conversation
```

The popup does not receive actual tab ids, conversation ids, URLs, page content or credentials.

## What the popup must not do

```text
popup visibility
!= ChatGPT product write
!= runtime-tab provisioning
!= connector approval
!= retry/fallback authority
!= canonical finality
```

The popup therefore does not:

- type or submit a ChatGPT message;
- call `executeNativeTurn()`;
- create the runtime-owned ChatGPT tab merely because the popup opened;
- inspect ChatGPT DOM/CDP state;
- expose conversation ids, tab ids, turn ids or URLs;
- expose cookies, authorization/session tokens, signed locators or connector payloads;
- repair or retry an ambiguous product write.

`Open ChatGPT` is a separate explicit user click that opens the normal `https://chatgpt.com/` page. It is not runtime-tab provisioning.

## Status semantics

### Ready

```text
nativeHostConnected = true
busy = false
```

Visible copy:

```text
Ready
Your local runtime can use this browser session.
```

### Working

```text
nativeHostConnected = true
busy = true
```

Visible copy indicates that the local runtime is using the browser session. Opening the popup does not start the request.

### Needs attention

```text
nativeHostConnected = false
```

The primary surface says CWA cannot reach the local runtime. The technical term `Native host` remains in the collapsed diagnostics section instead of being the headline.

### Status unavailable

Used only when the popup cannot obtain the bounded local status object.

## Runtime-tab wording

A missing runtime tab is not automatically an error. The production runtime creates/reuses it on demand when a caller initiates a governed browser-owned turn.

The collapsed details surface may distinguish:

- `Created on demand` — no current runtime tab;
- `Ready` — a ChatGPT root runtime tab exists;
- `Conversation open` — the runtime tab is on a conversation route;
- `Needs refresh` — stored runtime-tab state no longer resolves safely.

The popup does not remove stale storage or create a replacement merely because it was opened.

## Sanitized diagnostics

`Copy diagnostics` copies only the bounded local status fields above plus fixed product/surface labels.

It intentionally omits:

- runtime tab id;
- conversation/turn ids;
- URLs;
- credentials/tokens/cookies;
- raw Native Messaging payloads;
- ChatGPT page content;
- connector or artifact capability-bearing values.

## Toolbar state

The toolbar title is product-facing:

- `ChatGPT Web Adapter — Ready`;
- `ChatGPT Web Adapter — Working`;
- `ChatGPT Web Adapter — Needs attention`.

The normal ready state uses the CWA icon without badge clutter. Busy/unavailable may use the existing bounded amber/red badge indicators.

## Extension description

The Chrome card explains purpose instead of implementation:

> Connects the CWA local runtime to your existing ChatGPT browser session.

The high-trust implementation details remain documented in architecture/security docs rather than being presented as marketing copy.

## Distribution boundary

PR11.0 still uses the existing unpacked-extension workflow:

```text
chrome://extensions
-> Developer mode
-> Load unpacked
```

Chrome may therefore continue to identify it as a developer/unpacked extension and may add its own developer-mode badge. PR11.0 improves CWA's icon and popup but does not pretend that local development installation is Chrome Web Store distribution.

Chrome Web Store publication remains intentionally deferred. Before considering it, review at least:

- store policy for the high-trust `debugger` permission;
- privacy/disclosure requirements;
- extension update/version lifecycle;
- support expectations for external users;
- whether store distribution is actually needed by downstream adoption.

## Packaging

The browser extension package-data contract includes:

```text
*.json
*.js
*.html
*.css
*.png
```

Release validation compares the complete source extension asset set against the wheel rather than validating JavaScript/JSON only.

## Acceptance gate

PR11.0 is complete when:

1. manifest uses the product name, user-facing description and new CWA icons without adding permissions;
2. popup is usable in light and dark mode;
3. main popup copy is user-facing and engineering detail is secondary/collapsed;
4. popup status remains local and sanitized;
5. popup performs no ChatGPT product write or automatic runtime-tab provisioning;
6. toolbar state follows Native Messaging connection / in-flight state without becoming an authority surface;
7. all four PNG icon sizes are present and valid;
8. wheel/sdist include the complete product surface;
9. README/docs use the same visual identity;
10. deterministic tests and full CI are green;
11. one manual unpacked-extension visual check confirms that the v2 icon/popup no longer reads like a debug utility.

No authenticated ChatGPT product turn is required for this milestone because the changed behavior is extension chrome and local bridge-status presentation, not ChatGPT product mutation.
