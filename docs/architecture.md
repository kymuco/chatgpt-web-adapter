# Architecture

_Last updated: 2026-09-26_

CWA is a local product-runtime bridge for authenticated consumer AI web products.

The architecture is provider-aware but not provider-flattening: shared contracts express
what survived real product evidence, while provider-specific mechanics remain below the
public boundary.

## 1. Runtime first, provider boundary second

Execution happens through a concrete runtime:

```text
application / HDE / Codexia / terminal
                  |
                  v
        provider-specific runtime
          /          |          \
         /           |           \
   ChatGPT      DeepSeek Web    Gemini Web
 production     experimental    experimental
```

An existing runtime can then be inspected/validated as:

```text
ProductProviderBoundary schema 2
```

`ProductProviderBoundary` is metadata and invariant validation. It is not a request
router and does not execute turns.

## 2. Frozen provider-neutral contract

PR15.56 froze the provider-neutral boundary after ChatGPT, DeepSeek and Gemini proofs.

Schema 2 records:

```text
provider_id
product_semantics
transport

canonical_readback_required
canonical_interface

write_transport_interface
capability_model
provenance_model

automatic_write_retry
fallback_transport
ambiguous_write_requires_reconciliation
incremental_observation_is_canonical_finality
```

Current shared safety invariants include:

```text
automatic_write_retry = false
fallback_transport = none
ambiguous_write_requires_reconciliation = true
incremental_observation_is_canonical_finality = false
```

These are architectural guarantees, not assumptions inferred from a provider name.

## 3. Provider differences remain explicit

### ChatGPT

```text
provider_id = chatgpt
product_semantics = ordinary-chatgpt
canonical_readback_required = true
canonical_interface = CanonicalConversationClient
```

The mature application runtime is:

```text
ChatGPTProductRuntime
```

ChatGPT has a separate canonical read/session plane and production browser-owned write
transport.

### DeepSeek Web

```text
provider_id = deepseek
product_semantics = ordinary-deepseek
canonical_readback_required = false
canonical_interface = none
support = EXPERIMENTAL
```

Current scope is text new chat and continuation.

### Gemini Web

```text
provider_id = gemini
product_semantics = ordinary-gemini
canonical_readback_required = false
canonical_interface = none
support = EXPERIMENTAL
```

Current scope is text new chat and continuation.

See [providers.md](providers.md).

## 4. ChatGPT production runtime

The mature/default path remains:

```text
application
    |
    v
ChatGPTProductRuntime
   /             \
  /               \
canonical        mutation
read/session     ProductWriteTransport
  |                 |
  |          browser-owned PRODUCTION
  |          browserless-request EXPERIMENTAL
  |
  +------ completion / identity reconciliation
```

Primary modules include:

- `product_runtime.py`;
- `product_runtime_core.py`;
- `product_transport.py`;
- `product_capabilities.py`;
- `product_provenance.py`;
- `product_provider.py`;
- `product_contract.py`;
- `public_surface.py`.

The intended application contract remains narrow:

```python
runtime.health(...)
runtime.capabilities()
runtime.send(...)
runtime.send_text_observed(...)
runtime.get_status(...)
runtime.get_messages(...)
runtime.attach_conversation(...)
```

## 5. Canonical observation is conditional, not universal

ChatGPT currently has a canonical conversation/session interface.

It can answer:

- which durable conversation exists;
- current durable status;
- durable message history;
- whether the submitted turn reached a canonical completed assistant message.

Core rule:

```text
incremental stream
!= structured observation
!= DOM stability
!= canonical finality
```

DeepSeek/Gemini currently do not claim this canonical interface. Their runtime boundary
sets `canonical_readback_required=false`.

The architecture therefore does not pretend every provider has the same read plane.

## 6. Product mutation

All writes happen through an explicit provider-specific transport.

There is no silent:

```text
browser-owned
↔ browserless
↔ compatibility client
↔ another provider
```

fallback.

### ChatGPT browser-owned

The official page owns protected write semantics.

CWA delegates a bounded write through the signed-in product page and then returns to
the appropriate observation/finality plane.

### DeepSeek / Gemini page-owned writes

The provider worker performs one bounded page-owned submit and observes the resulting
page state.

Current completion evidence is:

```text
PAGE_DOM_STABLE_COMPLETION
canonical_completion_proven = false
```

This is valid transport evidence but not canonical readback.

See [browser_owned.md](browser_owned.md).

## 7. Write ambiguity and retry authority

The strongest cross-provider safety rule is:

```text
write known not to have happened
→ ordinary failure where appropriate

write may have happened
→ reconciliation required
→ automatic retry forbidden
```

For DeepSeek/Gemini, the ambiguous boundary begins when the click-capable submit
`Runtime.evaluate` may have executed.

A debugger/bridge failure after that point never authorizes a second write.

## 8. Conversation identity

Identity semantics are provider-specific.

ChatGPT uses its proven product conversation/session identity.

DeepSeek/Gemini currently use:

```text
local opaque conversation id
→ exact observed provider page route
```

CWA does not guess or freeze undocumented provider-internal route-id schemas when the
product does not expose a stronger public identity contract.

## 9. Capabilities

Capabilities are evidence-backed for a concrete runtime/provider.

States:

- `AVAILABLE`;
- `UNSUPPORTED`;
- `UNKNOWN`;
- `UNIMPLEMENTED`.

Support tier is separate from capability state.

This permits an experimental provider to have a live-proven `AVAILABLE` text-turn
capability without claiming production support for the provider as a whole.

## 10. Provenance

`ProductExecutionProvenance` describes what one execution actually observed.

It can record:

- provider/product semantics;
- transport;
- completion source;
- canonical-completion claim;
- conversation/request identity;
- provider-specific finality detail.

Neutral provenance requires explicit product semantics. It does not silently synthesize
ChatGPT semantics for another provider.

## 11. Rich input

Rich input is currently a mature ChatGPT capability on the proven browser-owned path.

Supported evidence-backed paths include:

- image new chat;
- general file new chat;
- multimodal continuation.

Native Messaging carries validated local paths rather than raw attachment bytes. The
official page owns upload and submit.

DeepSeek/Gemini do not inherit rich-input availability merely because their web UIs may
visibly expose upload controls.

## 12. Structured product observation

The mature ChatGPT runtime can expose bounded typed observations for:

- search activity;
- generic tool/activity points;
- source identity;
- citation relationships;
- required-action evidence.

Observation is intentionally separated from authority:

```text
product observation
!= product approval
!= connector authorization
!= product write authority
!= retry authority
!= canonical finality
!= filesystem/Git/workspace authority
```

Raw private tool arguments/results, credentials, arbitrary DOM state and capability
locators remain outside the public observation boundary.

## 13. Generated artifacts

The generated-artifact boundary remains conservative.

Current frozen result:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

Observation does not imply download authority. CWA does not synthesize stable artifact
identity from filename, prose, DOM order, message order, URL similarity or minified
frontend internals.

## 14. Browserless transport

`browserless-request` remains an experimental ChatGPT transport.

It exists behind the same high-level runtime boundary but depends more directly on
undocumented web request behavior and product protection state.

CWA does not solve Turnstile, synthesize proof tokens or weaken ambiguity/finality
rules merely to make browserless writes succeed.

Avoiding Chrome is not, by itself, a promotion criterion.

## 15. Public surface tiers

The root package exposes machine-readable tiers.

### `PRIMARY_PRODUCTION`

Includes:

- `ChatGPTProductRuntime`;
- `assemble_product_runtime()`;
- `ProductProviderBoundary`;
- `product_provider_boundary()`;
- product transport/capability/provenance/contracts;
- canonical client interfaces;
- immutable structured observation values.

### `SHARED_SUPPORT`

Auth/session helpers, common types, errors and media values.

### `COMPATIBILITY`

`ChatGPTWebClient` / `WebChatClient` and historical workflows.

### `EXPERIMENTAL`

Raw/backend helpers and unstable transport/product surfaces.

DeepSeek/Gemini concrete runtimes remain module-only rather than root production
exports.

### `RESEARCH_DIAGNOSTIC`

Direct browser-native/Sentinel/characterization tooling.

## 16. Extension composition

The browser extension keeps provider dispatch private.

The internal provider handler registry is composition machinery, not:

- a public plugin registry;
- a caller-controlled routing table;
- a generic provider factory.

Shared abstraction should reopen only when a real provider or consumer falsifies the
current contract.

## 17. Downstream authority

CWA can provide product evidence to HDE, Codexia, terminal tools or arbitrary Python
applications.

It does not own:

- project memory;
- autonomous continuation policy;
- task planning;
- Git/workspace authority;
- filesystem mutation policy;
- external approval policy.

Those remain downstream concerns.

## 18. Architectural decision rule

For product drift or a new capability:

```text
observe narrowly
→ identify decision-relevant contract
→ preserve authority separation
→ add deterministic regression
→ perform bounded live validation when needed
→ document resulting support/capability boundary
```

Do not continue reverse engineering after the architectural decision is already
supported.

## 19. Reopen conditions for provider architecture

Do not add another abstraction layer merely because another provider exists.

Reopen the frozen provider architecture only if:

1. a real provider cannot fit schema 2 without misrepresenting semantics;
2. a real consumer needs stable provider construction/selection;
3. a new canonical interface shape cannot be represented;
4. production promotion of an experimental provider requires a stronger contract;
5. a concrete safety failure disproves the current reconciliation model.

See [engineering/pr15_56_provider_architecture_closure.md](engineering/pr15_56_provider_architecture_closure.md).
