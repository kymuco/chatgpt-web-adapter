# Building on top of CWA

CWA is the reusable product-runtime boundary for local applications that need ordinary
consumer AI web-product semantics.

Higher-level products should consume CWA without moving application cognition, policy
or workflow authority into this repository.

## Start from the runtime contract

For the mature/default ChatGPT path:

```python
from chatgpt_web_adapter import assemble_product_runtime

runtime = assemble_product_runtime(
    transport="browser-owned",
    auth_file="auth_data.json",
)
```

For new integrations, prefer the runtime/capability/provenance surface over the
historical `ChatGPTWebClient`.

Useful application primitives include:

- `runtime.health()`;
- `runtime.capabilities()`;
- `runtime.send()`;
- `runtime.send_text_observed()`;
- `runtime.get_status()`;
- `runtime.get_messages()`;
- `runtime.attach_conversation()`;
- `product_provider_boundary(runtime)` for provider-neutral metadata validation.

## Provider-aware integration

Do not write application logic that assumes every provider has ChatGPT's complete
surface.

Instead:

```text
runtime
→ inspect capabilities
→ inspect provider boundary when needed
→ use only evidence-backed surfaces
```

Current `main` has:

```text
ChatGPT       production/default
DeepSeek Web  experimental
Gemini Web    experimental
```

DeepSeek/Gemini currently expose live-proven text new-chat and continuation through
module-only runtimes. They do not inherit canonical readback, rich input, streaming or
model-profile capabilities from ChatGPT.

See [providers.md](providers.md).

## What CWA should own

CWA owns reusable, application-agnostic product mechanics such as:

- authenticated product/session integration;
- explicit write transports;
- conversation identity mechanics;
- provider capability declarations;
- execution provenance;
- product-level completion/finality evidence;
- structured product observations;
- browser bridge mechanics;
- ambiguity/reconciliation boundaries;
- sanitized diagnostics.

## What the application should own

A downstream application should keep authority for:

- prompt/workflow policy;
- memory and project state;
- task planning;
- local filesystem/Git mutations;
- approval policy for external actions;
- retry decisions after reconciliation;
- provider-selection policy;
- user-facing presentation;
- app-specific persistence/logging.

CWA reporting that a product exposed an action or source does not authorize the
application to act on it.

## Provider selection belongs downstream for now

CWA intentionally does not expose a public generic provider factory or registry.

That means a higher-level application that experiments with multiple providers should
own the selection policy and instantiate the appropriate runtime explicitly.

This is deliberate while DeepSeek/Gemini remain experimental.

Do not push a generic provider router into CWA merely because an application wants
fallback behavior.

In particular:

```text
provider A failed ambiguously
!= permission to resend through provider B
```

## Browser-owned integration

A higher-level application should treat the browser bridge as runtime infrastructure,
not as UI or workflow authority.

The application should not depend on:

- Chrome tab ids;
- CDP target ids;
- extension worker names;
- provider DOM selectors;
- exact page routes;
- Native Messaging framing.

Those remain below CWA's runtime boundary.

See [browser_owned.md](browser_owned.md).

## Experimental provider example

An application may explicitly opt into an experimental runtime:

```python
from chatgpt_web_adapter.gemini_web import GeminiWebRuntime

runtime = GeminiWebRuntime()

if not runtime.health().ready:
    raise RuntimeError("Gemini Web runtime unavailable")

if runtime.capabilities().state("text_turns").value != "AVAILABLE":
    raise RuntimeError("text turns unavailable")

response = runtime.send_text("Summarize this in one sentence.")
```

This is an explicit experimental dependency. Do not silently substitute it for the
production ChatGPT runtime.

## Historical compatibility surface

`ChatGPTWebClient` / `WebChatClient` remain available for existing callers and
regression work.

They are no longer the recommended architecture foundation for a new product.

Do not silently route:

```text
ChatGPTWebClient.send()
→ ChatGPTProductRuntime
```

or the reverse.

Migration should remain explicit.

## Promotion rule

Move logic downward into CWA only when it is:

1. reusable across applications;
2. owned by the product/runtime boundary rather than app policy;
3. evidence-backed;
4. compatible with authority/finality invariants;
5. regression-testable without relying on one consumer's workflow.

If a feature exists only because one app needs a specific workflow, keep it in that
app first.

## Failure handling

Applications should distinguish:

```text
known pre-write failure
→ caller may decide whether a new invocation is appropriate

ambiguous write
→ reconcile
→ never automatically replay
```

A provider-specific ambiguous error is not an ordinary transient retry signal.

## Recommended layering

```text
application / HDE / Codexia / TUI
        |
        |  cognition, policy, workflow, UX
        v
small application service layer
        |
        |  explicit runtime invocation
        v
CWA provider runtime
        |
        |  product/session/write/finality mechanics
        v
consumer AI web product
```

This keeps CWA reusable without turning it into an agent framework.
