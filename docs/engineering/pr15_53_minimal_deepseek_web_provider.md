# PR15.53 — Minimal DeepSeek Web provider proof

## Purpose

Use a materially different web product to test the PR15.52 provider boundary without
generalizing the ChatGPT runtime.

This slice is intentionally narrow:

```text
DeepSeek Web
→ text new chat
→ text continuation
→ explicit provider identity / semantics
→ no automatic retry
→ no fallback
→ explicit page-owned completion evidence
```

Everything else stays out of scope.

## Provider identity

```text
provider_id       = deepseek
product_semantics = ordinary-deepseek
transport         = deepseek-web
support tier      = EXPERIMENTAL
```

The runtime must pass the frozen `product_provider_boundary(...)` from PR15.52.

## Browser architecture

DeepSeek does not enter the existing ChatGPT native-turn lifecycle.

The only shared browser boundary is the already-proven Native Messaging bridge:

```text
Python DeepSeekWebTurnProvider
→ existing Native Messaging host
→ type=turn, providerId=deepseek
→ provider turn registry
→ executeDeepSeekWebTurn(...)
→ hidden chat.deepseek.com tab
→ Chrome/CDP page interaction
```

For ordinary ChatGPT traffic:

```text
providerId absent / chatgpt
→ existing diagnostic/observer dispatch
→ existing ChatGPT CWA_NATIVE_TURN_LAYERS
→ unchanged
```

The provider registry is private to the extension turn boundary. It exists only to
prevent provider branching from leaking into ChatGPT domain layers; it is not a public
generic runtime/provider registry.

## No private DeepSeek HTTP contract

PR15.53 deliberately does not depend on undocumented DeepSeek endpoints or payloads.

The extension:

- opens `https://chat.deepseek.com/`;
- finds the visible textarea;
- types via CDP input;
- submits through a visible primary send control, with Enter as a bounded fallback;
- observes the user-visible assistant DOM;
- waits for the final assistant text to remain stable for at least 9 seconds with no
  visible stop control.

Current public browser evidence identifies the DeepSeek textarea and assistant markdown
surface, but these selectors are treated as experimental product evidence, not as an
official API contract.

## Conversation identity

The provider does not encode DeepSeek route structure.

For a new chat:

```text
completed page turn
→ generate local opaque conversation id
→ observe exact final DeepSeek URL
→ persist local id -> exact URL
```

For continuation:

```text
local conversation id
→ resolve exact stored URL
→ open that URL
→ submit next text turn
```

Unknown continuation ids fail before any write.

The implementation intentionally contains no `/a/chat/s/` route assumption.

## Finality and retry

A successful turn returns only after:

```text
assistant text observed
+ visible assistant text changed from baseline
+ no visible stop control
+ same final assistant text stable >= 9000 ms
```

This is page-owned transport finality, not server-canonical readback.

Therefore provenance records:

```text
completion source             = TRANSPORT_RETURN
canonical_completion_proven   = false
completion proof              = stable_assistant_dom
incremental observation final = false
```

If the send action has occurred but a new stable assistant response cannot be proven,
the extension fails with:

```text
DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED
```

The Python provider marks that failure as:

```text
reconciliation_required = true
automatic_retry_allowed = false
```

No retry or fallback path exists.

## Capability surface

Only these are AVAILABLE:

```text
text_turns
new_chat
continuation
```

Streaming, canonical readback, files, images, web search, Temporary, model/reasoning
selection, tools/connectors, approvals, branching and multimodal continuation remain
UNIMPLEMENTED in this proof.

## Live gate

The bounded live gate is:

```powershell
python tools/deepseek_web_live_gate_pr15_53.py --timeout 180
```

It performs exactly two product writes:

1. fresh DeepSeek chat with a unique echo marker;
2. continuation using the returned local conversation id with a second unique marker.

Acceptance requires:

- both markers appear in the final response;
- continuation preserves the same local conversation id;
- both executions report `stable_assistant_dom`;
- neither claims canonical server finality;
- the runtime passes `product_provider_boundary(...)`.

The user must already be logged into `chat.deepseek.com` in the Chrome profile used by
the extension. The extension must be reloaded after the new DeepSeek host permission is
added.

## Non-goals

No:

- DeepSeek API-key transport;
- private DeepSeek HTTP reverse engineering;
- images or files;
- search/tools/connectors;
- model or reasoning controls;
- account pooling;
- public generic provider registry;
- generic `ProductRuntime`;
- changes to ChatGPT Browser Authority or finality.

Tracking: #107
