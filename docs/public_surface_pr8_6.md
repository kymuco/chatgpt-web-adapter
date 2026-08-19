# PR8.6 — Legacy Direct-Write / Sentinel Isolation, Public Surface Reclassification and Compatibility Boundary

PR8.6 makes the current product-runtime architecture obvious without deleting the research and compatibility layers that made it possible.

## Outcome

The forward-looking application path is now:

```text
assemble_product_runtime()
  -> ChatGPTProductRuntime
      -> CanonicalConversationClient
      -> ProductWriteTransport
          -> BrowserOwnedProductTransport
              -> proven browser-owned page write
      -> capability declaration
      -> provenance-aware completion
```

Historical `ChatGPTWebClient`, Sentinel, prepared/raw web-backend, and direct browser-native APIs remain available, but they no longer share one undifferentiated support label.

## Support tiers

PR8.6 defines five explicit tiers:

```text
PRIMARY_PRODUCTION
SHARED_SUPPORT
COMPATIBILITY
EXPERIMENTAL
RESEARCH_DIAGNOSTIC
```

The root package exposes:

```python
from chatgpt_web_adapter import (
    PUBLIC_SURFACE_CLASSIFICATION,
    PUBLIC_SURFACE_TIERS,
    PublicSurfaceTier,
    public_surface_tier,
)
```

This classification is documentation/governance metadata. It does not modify runtime dispatch.

## Tier 1 — PRIMARY_PRODUCTION

Use for new ordinary ChatGPT product-runtime integrations:

- `assemble_product_runtime`
- `ChatGPTProductRuntime`
- `CanonicalConversationClient`
- `ProductWriteTransport`
- `ProductRuntimeExecution`
- `ProductRuntimeHealth`
- transport registry constants
- capability models
- provenance/completion models

Compatibility target:

- forward-looking application contract;
- no automatic legacy fallback;
- unknown transport fails closed;
- browser implementation details remain behind the transport boundary.

## Tier 2 — SHARED_SUPPORT

Shared support includes:

- core conversation/response types;
- auth/session helpers;
- common errors;
- conversation references;
- public-surface classification metadata.

These are used by both the product runtime and compatibility layers and should not be described as legacy merely because some originated before PR8.

## Tier 3 — COMPATIBILITY

Compatibility-retained symbols include:

- `ChatGPTWebClient`
- `WebChatClient`
- legacy metrics/diagnostic response helpers
- media input types
- `DEFAULT_MODEL`

### Decision for `ChatGPTWebClient`

PR8.6 does **not** deprecate `ChatGPTWebClient`.

Reasons:

1. existing applications already depend on it;
2. it contains feature coverage that the current text-only product transport has not yet graduated (for example media and some backend-specific controls);
3. a warning at import/runtime time would create noise before a complete migration target exists;
4. the PR9.0 architecture decision may change how the final v2 product bridge is packaged.

However, new ordinary text-turn application code should prefer `ChatGPTProductRuntime`.

Compatibility guarantee for the current major line:

```text
existing imports remain valid
existing ChatGPTWebClient behavior is not silently redirected
no implicit ProductRuntime -> legacy send fallback
no implicit legacy send -> ProductRuntime migration
```

Any future removal or runtime deprecation requires a separate migration-aware decision.

## Tier 4 — EXPERIMENTAL

Experimental symbols include:

- approval/policy helpers;
- required-action helpers;
- `PayloadBuilder` / `validate_payload`;
- prepared-turn helpers.

They remain exposed because they are useful, but their contracts depend more directly on changing web-backend behavior.

Experimental does not mean deprecated. It means they are not part of the primary product-runtime compatibility promise.

## Tier 5 — RESEARCH_DIAGNOSTIC

Research/diagnostic symbols include:

- Sentinel provider/transaction types;
- Sentinel prepare/finalize probes;
- direct `BrowserNativeTurnProvider` and bridge status/result types;
- Native Messaging install/extension helpers.

These symbols remain importable for:

- regression diagnosis;
- transport implementation work;
- PR history reproduction;
- PR9.0 architecture comparison.

Application code should not treat these low-level symbols as the product-runtime API.

### Sentinel decision

No Sentinel code is deleted in PR8.6.

The current production `ChatGPTProductRuntime` assembles with `auto_sentinel=False` and never falls back to the Sentinel/direct-write path. Sentinel remains a research/compatibility artifact until a later evidence-based removal decision.

### Direct browser-native decision

Direct `BrowserNativeTurnProvider` use is likewise retained. The production runtime uses browser-native mechanics behind `BrowserOwnedProductTransport`, but direct low-level provider use is classified research/diagnostic because it exposes implementation ownership that HDE/application callers should not depend on.

## Example classification

### Primary production

```text
examples/product_runtime.py
```

It demonstrates:

- runtime assembly;
- health;
- capabilities;
- ordinary text send;
- execution provenance.

### Compatibility

Examples such as:

```text
examples/basic_send.py
examples/continue_saved.py
examples/attach_existing.py
examples/read_messages.py
examples/status_polling.py
```

remain useful for existing `ChatGPTWebClient` users and historical feature coverage.

### Experimental

```text
examples/approve_tools.py
examples/raw_payload.py
examples/github_auto_approve.py
```

### Research / diagnostic

```text
examples/browser_native_send.py
examples/diagnose_latency.py
examples/watch_conversation.py
```

PR-specific feasibility examples are not promoted merely because they live under `examples/`.

## README / usage positioning

The README is now product-runtime-first.

`USAGE.md` remains the detailed compatibility guide for the historical `ChatGPTWebClient` feature set. It is not deleted or rewritten wholesale in PR8.6 because that would mix behavior migration with documentation classification. New ordinary text-turn integrations should start with:

1. `README.md`;
2. `examples/product_runtime.py`;
3. `docs/product_runtime_pr8_3.md`;
4. `docs/product_transport_protocol_pr8_4.md`;
5. `docs/product_capabilities_provenance_pr8_5.md`.

## Browser UX observation

The browser-owned runtime requests no foreground activation.

Live PR8.5 compatibility validation also demonstrated a cold path where no reusable runtime tab existed and Chrome foregrounded the newly created tab anyway. Therefore:

```text
foreground activation requested = false
```

and

```text
foreground activation observed = true/false
```

remain distinct facts. The latter belongs in transport observation/provenance and becomes a PR9.0 comparison criterion rather than a PR8.6 compatibility failure.

## Migration guidance

For new ordinary text-turn application code:

```python
from chatgpt_web_adapter import assemble_product_runtime

runtime = assemble_product_runtime(auth_file="auth_data.json")
response = runtime.send("hello")
```

For existing code:

```python
from chatgpt_web_adapter import ChatGPTWebClient
```

continues to work. Migrate when the product runtime exposes the capabilities your application needs; do not rewrite merely to satisfy a cosmetic deprecation.

For implementation/debug tooling, direct browser-native and Sentinel imports remain available but should not cross into HDE-facing contracts.

## Acceptance gates

```text
S0  ChatGPTProductRuntime is documented as the primary production surface
S1  public support tiers are machine-readable and non-overlapping
S2  all root public exports are classified
S3  ChatGPTWebClient imports remain compatible
S4  no deprecation warning is introduced in PR8.6
S5  production runtime still has no legacy direct-write fallback
S6  Sentinel code remains available but is classified research/diagnostic
S7  direct browser-native low-level APIs are research/diagnostic
S8  primary example uses product runtime + capabilities + provenance
S9  README is product-runtime-first and links ROADMAP.md
S10 architecture docs reflect runtime/canonical/transport separation
S11 legacy/experimental examples remain available for diagnosis/migration
S12 no extension, browser-owned writer, protected-write, or auth semantics are changed
```

## Non-goals

PR8.6 does not:

- delete Sentinel/direct-write modules;
- remove `ChatGPTWebClient`;
- add a warning on every compatibility-client use;
- migrate media, streaming, approvals, tools, or raw payloads into the product runtime;
- change the browser-owned write algorithm;
- change extension/runtime-tab behavior;
- solve the cold-tab foreground observation;
- introduce a generic ChatGPT/Claude/Gemini abstraction;
- decide the PR9.0 daemon/extension/Python ownership question.

Isolation and clear ownership come first. Removal or v2 redesign comes only after an evidence-backed architecture decision.
