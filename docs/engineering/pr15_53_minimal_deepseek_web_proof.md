# PR15.53 — Minimal DeepSeek Web provider proof

## Purpose

Use a materially different second provider to test the boundary frozen in PR15.52.

This slice is deliberately narrow:

```text
DeepSeek Web
→ text new chat
→ text continuation
→ opaque local conversation identity bound to restored page route
→ page-owned completion evidence
→ no automatic retry
→ no fallback transport
```

It does not add images, files, tools/connectors, account pools, model-profile
abstraction, a public generic provider registry, or a generic ProductRuntime. The
extension-only provider-turn map is a private dispatch seam whose sole purpose is to
keep provider branching out of ChatGPT domain layers.

## Evidence-driven boundary correction

PR15.52 initially required every provider to expose:

```text
CanonicalConversationClient
```

The second-provider implementation falsifies that requirement.

The minimal DeepSeek Web proof intentionally does not depend on undocumented private
HTTP endpoints. Its strongest available finality is page-owned DOM evidence. Therefore
provider-boundary schema 2 makes canonical readback conditional:

```text
canonical_readback_required = true
  → canonical_interface = CanonicalConversationClient

canonical_readback_required = false
  → canonical_interface = none
```

ChatGPT keeps canonical readback unchanged. DeepSeek declares it unavailable instead
of fabricating a canonical plane.

## Browser composition

The existing Native Messaging authority lane remains the only local bridge.

DeepSeek turns use the existing `type="turn"` request with:

```text
providerId = deepseek
```

`service_worker_deepseek_provider.js` registers exactly one handler in the private
provider-turn registry owned by `service_worker.js`. Provider dispatch happens before
diagnostic handlers, observers, and the ChatGPT native-turn lifecycle, so DeepSeek does
not pass through:

- Browser Authority;
- Temporary lifecycle;
- ChatGPT model-profile selection;
- ChatGPT rich-input lifecycle;
- ChatGPT canonical reconciliation;
- ChatGPT response-stream hooks.

The manifest adds only the official web origin:

```text
https://chat.deepseek.com/*
```

## No private DeepSeek HTTP contract

The worker does not call `fetch`, XHR, CDP Network interception, or any DeepSeek
private endpoint.

The first proof interacts only with the official page:

```text
Runtime.evaluate
page-owned send-control click
chrome.tabs
chrome.storage.local
```

This means the second-provider proof tests web-session/browser architecture rather
than silently becoming an API-key integration.

## Conversation identity

No DeepSeek route format is hardcoded.

After a successful new-chat turn:

1. the page must navigate away from its initial route;
2. the final URL must remain under `https://chat.deepseek.com`;
3. the extension creates an opaque local conversation id;
4. `chrome.storage.local` binds that opaque id to the exact observed route.

A continuation receives only the opaque id. The extension resolves the saved route,
navigates the dedicated DeepSeek tab there, and requires the same opaque id after the
turn.

This is session-local routing identity, not a claim about DeepSeek backend ids.

## Finality

The experimental finality rule is intentionally weaker than ChatGPT canonical
readback.

Before submission the worker records bounded visible response-like page text. It then
writes the composer and performs exactly one page-owned send-control click. The send
control is resolved only inside the composer-local DOM surface; there is no keyboard
fallback and no second submit. After that single submit, if DeepSeek route navigation
replaces the CDP target, the worker may reattach only for post-submit observation.
It never replays the write. The worker then waits until:

- new response text is visible;
- an obvious stop-generation control is absent;
- the current DeepSeek assistant surface is preferred when present
  (`.ds-markdown.ds-assistant-message-main-content`, then the older
  `.ds-markdown.ds-markdown--block`, then bounded structural fallbacks);
- the same response text remains stable for at least nine seconds.

Successful evidence is recorded as:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
automatic_write_retry = false
```

If the single submit has already occurred but the page does not provide that evidence
before deadline, the attempt fails as:

```text
DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED
```

The Python provider maps that result to `DeepSeekWebWriteOutcomeAmbiguousError` with
`reconciliation_required=true` and `automatic_retry_allowed=false`. No second
submit or fallback transport is authorized.

## Python surface

PR15.53 adds experimental module-only classes:

```text
DeepSeekBrowserTurnProvider
DeepSeekWebTransport
DeepSeekWebRuntime
```

They are intentionally not added to the existing ChatGPT transport assembler or root
public API.

Capabilities are:

```text
text_turns   = AVAILABLE
new_chat     = AVAILABLE
continuation = AVAILABLE
support tier = EXPERIMENTAL
```

Everything outside the proof is UNKNOWN or UNIMPLEMENTED.

## Live gate

Prerequisites:

- install/reload the extension built from this branch;
- keep the Native Messaging host running;
- sign in to `https://chat.deepseek.com` in that Chrome profile.

Run:

```powershell
python -m chatgpt_web_adapter.deepseek_web_live_gate
```

The gate performs one new chat and one continuation with independent random response
markers. Acceptance requires:

```text
provider boundary passes
first marker observed
opaque conversation id established
second marker observed
continuation keeps same opaque conversation id
automatic write retry = false
fallback transport = none
canonical completion proven = false
```

CI proves deterministic composition and safety invariants. The provider is not
graduated beyond EXPERIMENTAL until this live gate passes on the real product.

Tracking: #107
