# Architecture

_Last updated: 2026-09-02_

`chatgpt-web-adapter` (CWA) is a layered product-runtime bridge around an existing ordinary ChatGPT web session. The current architecture is no longer a monolithic web-backend client and should not be understood primarily through historical Sentinel or direct-request internals.

The application-facing model is:

```text
application / HDE / CMA / terminal
                |
                v
        ChatGPTProductRuntime
      /            |            \
     /             |             \
canonical       product       structured
read/session     mutation      observations
    |               |              |
    |        ProductWriteTransport  |
    |               |              |
    |      browser-owned PRODUCTION|
    |      browserless EXPERIMENTAL|
    +---------------+--------------+
                    |
                    v
              ChatGPT product
```

The stable abstraction is the runtime and its contracts. Browser tabs, Native Messaging, extension worker composition, CDP targets, request correlation, Sentinel details, and research probes are implementation details below that boundary.

## 1. Product Runtime

Primary files:

- `src/chatgpt_web_adapter/product_runtime.py`
- `src/chatgpt_web_adapter/product_runtime_assembly.py`
- `src/chatgpt_web_adapter/product_transport.py`
- `src/chatgpt_web_adapter/product_capabilities.py`
- `src/chatgpt_web_adapter/product_provenance.py`
- `src/chatgpt_web_adapter/product_contract.py`
- `src/chatgpt_web_adapter/public_surface.py`

Responsibilities:

- expose the forward-looking application object `ChatGPTProductRuntime`;
- assemble an explicit product transport;
- keep canonical reads/finality separate from product mutation;
- expose provider-aware capability state;
- expose support-tier and runtime-contract metadata;
- preserve execution provenance;
- expose structured product observations without granting authority;
- fail closed rather than silently falling back to a legacy writer.

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

Downstream callers should not need Chrome tab ids, extension worker names, Native Messaging details, debugger targets, minified React component names, or Sentinel internals.

## 2. Canonical Observation and Session Plane

The canonical plane is represented by the public `CanonicalConversationClient` contract used by `ChatGPTProductRuntime` for canonical conversation/session observation.

Primary areas:

- conversation attach/read/status;
- auth/session loading and refresh;
- explicit current-Chrome authorization through the browser-native authority lane;
- canonical conversation/message identity;
- final assistant readback.

The canonical plane answers what durable conversation state exists and whether the exact submitted turn reached a canonical completed assistant message.

Core rule:

```text
incremental stream
!= structured observation
!= canonical finality
```

A successful protected turn ultimately requires canonical product evidence, not merely a DOM change, provisional SSE text, tool completion, or structured activity event.

Where supported, canonical reads and session renewal remain browserless even though production protected writes are browser-owned.

`browser_login_current_tab()` is an explicit credential-capture boundary, not
an ordinary product-runtime observation. The extension creates one active
additional `chatgpt.com` tab in the already-running Chrome, obtains the session
through page/CDP APIs, filters it to bounded ChatGPT credentials, and returns it
over the authenticated loopback bridge. Python validates the payload again and
atomically replaces the selected auth file. No component reads Chrome's profile
cookie database, imports browser cookies, or restarts Chrome.

## 3. Product Mutation Plane

All product mutation flows through an explicit `ProductWriteTransport` selected by the runtime.

There is no automatic browser-owned ↔ browserless ↔ compatibility fallback.

### Browser-owned transport — `PRODUCTION`

Primary areas:

- `browser_owned_product_transport.py`;
- `browser_owned_write_runtime.py`;
- browser-native client/provider;
- packaged MV3 extension;
- Native Messaging host.

The official ChatGPT page owns protected product-write semantics. CWA delegates a bounded write through the page and then returns to canonical observation for finality.

Important invariants:

- exactly one delegated write attempt for one runtime invocation unless the caller explicitly starts another invocation;
- no automatic retry after an ambiguous write;
- no hidden legacy direct-write fallback;
- page-owned protection/challenge behavior is not reconstructed by the SDK;
- canonical assistant readback remains final authority.

A reusable runtime tab is an implementation resource, not public continuation authority. The extension does not intentionally request foreground activation, though Chrome may foreground a newly created cold-path tab.

### Browserless request transport — `EXPERIMENTAL`

`browserless-request` implements a direct-request transport behind the same runtime boundary but remains explicitly experimental because it depends more directly on changing undocumented web protocol behavior.

Its contract is fail-closed around current Sentinel/challenge requirements. CWA does not solve Turnstile, synthesize proof tokens, replay protected credentials, or fall back to browser-owned writes merely because direct admission fails.

Transport support tier and individual capability state remain separate contracts.

## 4. Rich Input Plane

PR9.2 graduates rich input on the live-proven default browser-owned provider path.

Supported evidence-backed paths include:

- image new chat;
- general file new chat;
- multimodal continuation.

The same protected-write and finality rules apply to rich input.

Native Messaging carries validated local paths rather than attachment bytes. The official ChatGPT page owns upload and submit. The runtime validates the requested attachment set and correlates the protected request to the intended user message/conversation before treating the write as valid.

Capability graduation is provider-aware: an arbitrary custom provider does not inherit rich-input `AVAILABLE` state from the transport name alone.

## 5. Structured Product Observation Plane

PR9.3 and PR10.0 add a bounded observation layer alongside, not inside, mutation/finality authority.

Root production observation values can represent:

- search activity;
- generic tool/activity points;
- source identity;
- citation-to-source relationships;
- required-action evidence.

Post-0.3 typed models additionally support stronger connector and required-action lifecycle representation when stable product identifiers are explicitly present.

Core rule:

```text
product observation
!= product approval
!= connector authorization
!= product write authority
!= retry authority
!= canonical finality
!= downstream filesystem/Git/workspace authority
```

The collector consumes only bounded standardized events. Raw tool arguments/results, raw connector payloads, arbitrary DOM text, private reasoning, credentials, cookies, authorization headers, signed URLs, and retrieved private connector content remain outside this typed observation boundary.

`tools_connectors` remains conservative (`UNKNOWN`) because current authenticated evidence does not prove a general stable connector execution contract.

## 6. Generated-Artifact Boundary

PR10.1 adds a narrow artifact observation model and characterizes current product surfaces.

The milestone deliberately stops before download authority.

```text
artifact observed
!= artifact locator exposed
!= download requested
!= destination authorized
!= overwrite authorized
!= canonical finality
```

Current frozen status:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

The current product characterization did not prove both a stable product-owned artifact identity and a safe browser-owned resolution path. CWA therefore does not synthesize identity from filename, message order, DOM position, assistant prose, URL similarity, or minified React/update-queue internals.

Historical PR10.1 characterization overlays remain in-tree as reproducible research evidence but are disabled from ordinary runtime startup by default.

## 7. Capability and Provenance Ownership

Capabilities answer whether a feature is implemented and evidence-backed for the selected runtime/provider path.

Canonical states:

- `AVAILABLE`;
- `UNSUPPORTED`;
- `UNKNOWN`;
- `UNIMPLEMENTED`.

Provenance describes what one execution actually observed: transport, completion source, canonical proof, request/conversation identity, and transport-specific metadata.

CWA does not fabricate provenance to make heterogeneous transports look identical.

## 8. Public Surface Tiers

The root package exposes machine-readable support classification through `PublicSurfaceTier`, `PUBLIC_SURFACE_CLASSIFICATION`, and `public_surface_tier()`.

### `PRIMARY_PRODUCTION`

Forward-looking runtime, product transport contract, canonical client contract, capabilities/provenance/contracts, and immutable structured observation value types.

### `SHARED_SUPPORT`

Auth/session helpers, common conversation/response/error types, and `MediaItem` / `MediaSource` rich-input types used by the primary runtime.

### `COMPATIBILITY`

`ChatGPTWebClient` / `WebChatClient` and historical workflows retained for existing callers without silent redirection into the product runtime.

### `EXPERIMENTAL`

Approval helpers, raw/prepared backend surfaces, payload helpers, and `browserless-request` where contracts depend more directly on undocumented product behavior.

### `RESEARCH_DIAGNOSTIC`

Direct browser-native provider/install APIs, Sentinel internals, feasibility probes, and product-characterization tooling used to investigate or repair boundaries.

Research artifacts are intentionally retained when they provide useful evidence, but their presence does not make them application APIs.

The historical tier decision remains documented in `docs/public_surface_pr8_6.md`.

## 9. Compatibility Boundary

`ChatGPTWebClient` remains import-compatible and useful for historical workflows. It is no longer the architecture reference for new product-turn integrations.

Do not silently route:

```text
ChatGPTWebClient.send()
-> ChatGPTProductRuntime
```

and do not silently fall back:

```text
ChatGPTProductRuntime
-> ChatGPTWebClient.send()
```

Migration remains explicit.

`USAGE.md` now documents the current runtime first and keeps compatibility/research paths separately discoverable.

## 10. Downstream Authority Boundary

CWA may provide product evidence to CMA, HDE, terminal tools, or arbitrary Python applications.

It does not own the meaning or authority those applications assign to that evidence.

Examples:

```text
CWA: "ChatGPT exposed a required authorization action"
caller: decides whether approval is allowed

CWA: "ChatGPT cited source X"
caller: decides how to use that source

CWA: "generated artifact observation exists"
caller: still has no download/filesystem authority unless a separate future handoff contract provides it
```

Project state, memory, task orchestration, Git policy, workspace mutation, and autonomous continuation remain outside this repository.

## 11. What Stays Out of CWA

The package should not become:

- a full chat application/TUI;
- HDE/CMA project memory or cognition;
- a generic project agent;
- a Git/filesystem authority layer;
- a browser-challenge circumvention toolkit;
- a caller-controlled abstraction over every internal ChatGPT tool;
- a stable SDK built on minified React/DOM internals;
- a generic multi-provider model abstraction before a real second product backend exists.

## 12. Architectural decision rule

When product behavior changes or a new capability is considered:

```text
observe narrowly
-> identify the decision-relevant product contract
-> preserve authority separation
-> add deterministic regression
-> perform bounded live validation when product-facing behavior changed
-> document the resulting capability/support boundary
```

Stop characterization when the architectural decision is already supported. Do not continue reverse engineering merely because deeper internal state is reachable.

See [`../ROADMAP.md`](../ROADMAP.md) for current development direction and [`README.md`](README.md) for the documentation map.
