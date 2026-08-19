# Architecture

`chatgpt-web-adapter` is no longer best described as one monolithic web-backend client. PR8.3–PR8.6 establish a layered product-runtime architecture while preserving the older `ChatGPTWebClient` surface for compatibility and research.

The forward-looking model is:

```text
HDE / Python / terminal caller
            |
            v
   ChatGPTProductRuntime
      /             \
     /               \
canonical plane   write transport
     |                 |
     |          BrowserOwnedProductTransport
     |                 |
     |          BrowserOwnedProductWriteRuntime
     |                 |
     |          Native Messaging + extension
     |                 |
     +------ ordinary ChatGPT product ------+
```

The first proven write transport is `browser-owned`; it is an implementation behind the runtime contract, not the definition of that contract.

## Layer 1: Product Runtime

Primary files:

- `src/chatgpt_web_adapter/product_runtime.py`
- `src/chatgpt_web_adapter/product_transport.py`
- `src/chatgpt_web_adapter/product_capabilities.py`
- `src/chatgpt_web_adapter/product_provenance.py`
- `src/chatgpt_web_adapter/public_surface.py`

Responsibilities:

- expose the stable application-facing runtime object;
- keep canonical observation separate from product mutation;
- select an explicit closed-set product transport;
- fail closed instead of falling back to a legacy writer;
- expose capability state without collapsing unknown/unimplemented/unsupported;
- expose provenance for completion, identity, transport, and evidence planes;
- keep browser-specific observations optional and transport-owned.

The HDE-facing contract should stay narrow:

```python
runtime.health(...)
runtime.capabilities()
runtime.send(...)
runtime.send_text_observed(...)
runtime.get_status(...)
runtime.get_messages(...)
runtime.attach_conversation(...)
```

HDE should not need to know Chrome tab IDs, Native Messaging host details, extension worker names, CDP targets, Sentinel internals, or future daemon implementation details.

## Layer 2: Canonical Observation and Session Plane

Primary files:

- `src/chatgpt_web_adapter/client.py`
- `src/chatgpt_web_adapter/messages.py`
- `src/chatgpt_web_adapter/status.py`
- `src/chatgpt_web_adapter/attach.py`
- `src/chatgpt_web_adapter/auth.py`
- `src/chatgpt_web_adapter/auth_refresh.py`
- `src/chatgpt_web_adapter/auth_status.py`
- `src/chatgpt_web_adapter/auth_store.py`
- `src/chatgpt_web_adapter/browser_cookies.py`

Responsibilities:

- load and refresh reusable ChatGPT web-session credentials;
- attach to existing conversations;
- read canonical messages;
- derive canonical conversation status;
- recover canonical conversation/message identity;
- provide the independent readback used to prove completion after browser-owned writes.

PR8.4 names the structural contract `CanonicalConversationClient`. The current implementation is supplied by `ChatGPTWebClient`, but product-runtime callers should depend on the canonical interface rather than on legacy write methods.

Browserless canonical reads/session renewal are a strong property and should remain outside the browser unless a future architecture comparison proves a better alternative.

## Layer 3: Browser-Owned Product Write Transport

Primary files:

- `src/chatgpt_web_adapter/browser_owned_product_transport.py`
- `src/chatgpt_web_adapter/browser_owned_write_runtime.py`
- `src/chatgpt_web_adapter/browser_native_provider.py`
- `src/chatgpt_web_adapter/browser_native_client.py`
- packaged MV3 extension / Native Messaging host assets

Responsibilities:

- expose the proven browser-owned writer through `ProductWriteTransport`;
- check runtime readiness before delegation;
- recheck canonical continuation state at the commit point;
- delegate exactly once to the official ChatGPT page-owned write path;
- avoid automatic retry after an ambiguous delegated write;
- require canonical assistant readback before returning success;
- observe runtime-tab creation/reuse and foreground behavior without making those browser facts part of the generic transport contract.

The browser page owns protected product-write semantics. The bridge does not reconstruct private protected POSTs, export protection credentials, solve challenges, or emulate browser protection state.

The extension requests no foreground activation for the reusable runtime tab. A cold path may still be foregrounded by Chrome when the tab is newly created; this is an observed browser behavior and is therefore provenance/diagnostic evidence rather than a guaranteed no-focus invariant.

## Layer 4: Compatibility Web Client

Primary files include:

- `src/chatgpt_web_adapter/client.py`
- `src/chatgpt_web_adapter/conversation_send.py`
- `src/chatgpt_web_adapter/diagnostic_metrics.py`
- media/upload/model/backend-shaping helpers

`ChatGPTWebClient` and `WebChatClient` remain available because existing callers depend on them and because the product runtime has not yet absorbed every historical feature (for example media and some streaming/backend-specific controls).

PR8.6 changes their classification, not their behavior:

```text
before: described as the primary stable send surface
after:  compatibility surface retained without deprecation
```

Do not silently route `ChatGPTWebClient.send()` through `ChatGPTProductRuntime`. Do not silently route `ChatGPTProductRuntime` back into `ChatGPTWebClient.send()` as a fallback. The two surfaces must remain explicit while migration proceeds.

## Layer 5: Experimental Web-Backend Helpers

Primary areas:

- approval/policy helpers;
- `PayloadBuilder` and payload validation;
- prepared/raw payload helpers;
- connector-specific continuation experiments.

These features remain useful but rely more directly on undocumented backend behavior. They are `EXPERIMENTAL`, not part of the primary product-runtime promise.

Experimental features should not dictate the generic `ProductWriteTransport` contract until they have separate product-runtime characterization.

## Layer 6: Research / Diagnostic Transport Internals

Primary areas:

- Sentinel transaction/provider modules;
- direct `BrowserNativeTurnProvider` use;
- Native Messaging installation/bridge diagnostics;
- PR-specific feasibility probes and boundary repair examples.

PR8.6 intentionally keeps these artifacts available. They are valuable for:

- regression diagnosis;
- understanding historical web contracts;
- comparing alternative transports;
- validating future PR9.0 architecture candidates.

They are not the recommended application API. Isolation comes before deletion.

## Public Surface Tiers

The root package exposes machine-readable classification through `PublicSurfaceTier`, `PUBLIC_SURFACE_CLASSIFICATION`, and `public_surface_tier()`.

Tiers are:

- `PRIMARY_PRODUCTION` — forward-looking `ChatGPTProductRuntime` contract;
- `SHARED_SUPPORT` — auth, common types, and errors used across layers;
- `COMPATIBILITY` — retained historical `ChatGPTWebClient` surface;
- `EXPERIMENTAL` — unstable backend/workflow helpers;
- `RESEARCH_DIAGNOSTIC` — low-level transport research and diagnostics.

No PR8.6 tier automatically means removal. In particular, compatibility and research symbols remain importable unless a future migration PR explicitly decides otherwise.

## Capability and Provenance Ownership

Capabilities answer whether the selected runtime/transport has evidence for a feature. They do not claim everything the ChatGPT UI can do.

Provenance answers what happened during one execution. In particular:

```text
canonical completion proven
    !=
finish_reason necessarily present
```

`finish_reason=None` remains valid observed metadata when canonical readback proves completion through another signal.

Transport-specific evidence such as runtime-tab IDs stays optional metadata so future native/daemon transports do not have to invent browser facts.

## Compatibility Boundary

PR8.6 makes these decisions:

- `ChatGPTProductRuntime`: primary production target;
- `ChatGPTWebClient`: compatibility-retained, no deprecation warning in PR8.6;
- approval/raw/prepared helpers: experimental;
- direct Sentinel and browser-native low-level symbols: research/diagnostic;
- no legacy deletion in PR8.6;
- no automatic migration or fallback between old and new write paths.

See `docs/public_surface_pr8_6.md` for the detailed decision table.

## What Should Stay Out of This Repository

The package should still avoid becoming:

- a full chat application or TUI;
- HDE session/memory/identity storage;
- connector-specific business logic;
- a browser-challenge circumvention toolkit;
- a generic multi-provider model abstraction before a real second product backend exists.

Those concerns either belong above the product runtime or require a separate evidence-backed architecture phase.
