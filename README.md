# chatgpt-web-adapter

[![CI](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml)

Product-runtime adapter for using an existing ordinary ChatGPT web session from Python, HDE-style local runtimes, and terminal tools.

> [!WARNING]
> Not the official OpenAI API.
> Uses an existing ChatGPT web session and ordinary ChatGPT product semantics.
> Browser and web-product behavior may change.

`chatgpt-web-adapter` has one forward-looking production surface:

```text
ChatGPTProductRuntime
  -> browserless canonical read/status/session plane
  -> explicit ProductWriteTransport
  -> browser-owned page write for protected product turns
  -> bounded structured product observations
  -> canonical browserless assistant readback
```

The production write transport is `browser-owned`. It uses one reusable ChatGPT tab owned by the Chrome extension for protected product writes, while canonical reads and session lifecycle remain browserless where possible. CWA 0.3 extends this production path beyond the 0.2 text baseline with evidence-backed image/file input, multimodal continuation, web-search observation, and typed search/tool/source/citation observations.

The historical `ChatGPTWebClient` API remains available for compatibility. Sentinel/prepared/direct-write and direct browser-native APIs remain research or diagnostic surfaces; they are not the recommended starting point for new production integrations. The alternative `browserless-request` product transport is implemented behind the same runtime boundary but remains explicitly `EXPERIMENTAL`.

See [ROADMAP.md](ROADMAP.md) for the post-0.2 PR9 architecture plan and [docs/public_surface_pr8_6.md](docs/public_surface_pr8_6.md) for the support-tier and compatibility policy.

## CWA 0.3 CLI Quick Start

After installation and browser-owned runtime setup, the stable command surface remains:

```powershell
cwa doctor --json
cwa status --json
cwa capabilities --json
cwa send "Give me a short project summary." --profile HIGH
cwa messages <conversation-id> --json
cwa snapshot <conversation-id> --name project --output-dir ./artifacts --json
cwa export <conversation-id> --format jsonl --name project --output-dir ./artifacts --json
```

The accepted public CLI model-profile names are:

```text
INSTANT <-> FAST
MEDIUM  <-> BALANCED
HIGH    <-> DEEP
```

Product-native names are preferred in CLI documentation. Direct Python runtime profile keys remain the semantic `FAST` / `BALANCED` / `DEEP` contract.

Temporary Chat remains available through the same public CLI surface:

```powershell
cwa send "Answer briefly." --temporary --profile INSTANT
```

The CLI surface is intentionally narrower than every Python runtime capability. CWA 0.3 does not imply a new stable CLI attachment API, caller-selected product-tool orchestration, connector authorization flow, or production browserless write path merely because the ChatGPT UI exposes related features.

## Release Integrity

The 0.3 release candidate is validated as an exact wheel/sdist pair. CI verifies package metadata, console entry points, the frozen 0.3 product-runtime modules, root public-surface tiers, all packaged browser-extension `.json`/`.js` files, installed CLI help surfaces, and pre-setup `cwa doctor` behavior from a disposable environment rather than an editable checkout.

Candidate installed-wheel smoke derives the expected package version from the checkout `pyproject.toml`. A real tagged release is stricter and additionally requires:

```text
GitHub tag version == pyproject package version == dated CHANGELOG release heading
```

See [docs/release_checklist.md](docs/release_checklist.md) for the complete release gate.

## What This Is

`chatgpt-web-adapter` is a local adapter around an authenticated ChatGPT product session. It separates:

- **canonical observation** — conversation attach/read/status and session lifecycle;
- **product mutation** — an explicit product write transport;
- **runtime orchestration** — `ChatGPTProductRuntime`;
- **capability declarations** — `AVAILABLE`, `UNSUPPORTED`, `UNKNOWN`, `UNIMPLEMENTED`;
- **structured product observations** — bounded search/tool/activity/source/citation/required-action evidence;
- **execution provenance** — transport, planes, completion evidence, identity, and transport-specific observations.

It is designed so callers such as HDE do not need to know Chrome tab IDs, extension worker names, Native Messaging details, or Sentinel internals.

## What This Is Not

`chatgpt-web-adapter` is not:

- the official OpenAI API;
- a replacement for the OpenAI Python SDK;
- a documented long-term OpenAI platform contract;
- a browser-challenge bypass, Turnstile solver, proof-token synthesizer, or credential replay system;
- a general connector authorization or external-action authority layer;
- a full chat application, TUI, or local history product.

If you need an officially supported API contract, use the official OpenAI platform rather than this package.

## Public Surface Tiers

Support level is explicit and machine-readable.

### Primary production

Canonical tier: `PRIMARY_PRODUCTION`.

Use these for new product-runtime integrations:

- `assemble_product_runtime()`;
- `ChatGPTProductRuntime`;
- `ProductWriteTransport`;
- `CanonicalConversationClient`;
- capability, contract and provenance models;
- immutable structured observation value types (`ProductObservationKind`, `ProductObservationPhase`, activity/source/citation/required-action observations, and `StructuredProductObservation`);
- `chatgpt-web-adapter runtime status`;
- `chatgpt-web-adapter runtime send`.

The internal observation collector is deliberately not part of the root production API.

### Shared support

Canonical tier: `SHARED_SUPPORT`.

Auth/session helpers, core response/conversation types, common errors, and the `MediaItem` / `MediaSource` input types used by the primary runtime are shared support.

### Compatibility

Canonical tier: `COMPATIBILITY`.

`ChatGPTWebClient` / `WebChatClient` remain import-compatible and supported for existing callers and historical workflows.

The compatibility policy does **not** emit deprecation warnings and does not remove these APIs. New product-turn integrations should prefer `ChatGPTProductRuntime`.

### Experimental

Canonical tier: `EXPERIMENTAL`.

Approval, raw-payload, prepared-web-backend helpers, and the `browserless-request` transport remain experimental because they depend more directly on changing undocumented web behavior or do not yet have the production evidence boundary required for graduation.

### Research / diagnostic

Canonical tier: `RESEARCH_DIAGNOSTIC`.

Low-level Sentinel and direct browser-native provider/install symbols remain available for regression diagnosis, implementation work, and feasibility research. They are not the forward-looking application API.

The machine-readable classification is available as:

```python
from chatgpt_web_adapter import PUBLIC_SURFACE_CLASSIFICATION, public_surface_tier

print(public_surface_tier("ChatGPTProductRuntime"))
print(public_surface_tier("ChatGPTWebClient"))
```

## Requirements

- Python 3.10-3.14
- system `curl` available in `PATH` for the canonical web-session client
- an authenticated ChatGPT web session
- Chrome/Chromium plus the packaged extension and Native Messaging host for the current `browser-owned` protected-write transport

## Install

```bash
python -m pip install "chatgpt-web-adapter[browser]"
```

For local development and tests:

```bash
python -m pip install -e .[test]
pytest -q
```

## Authentication

Authorize the reusable ChatGPT web session once:

```bash
chatgpt-web-adapter auth login --auth-file auth_data.json
chatgpt-web-adapter auth status --auth-file auth_data.json
```

The first login is interactive. Subsequent access-token/session renewal is browserless while the reusable session remains valid.

`auth_data.json` contains reusable account credentials. Do not share it. See [docs/authentication.md](docs/authentication.md).

## Browser-Owned Runtime Setup

Register the Native Messaging host:

```powershell
chatgpt-web-adapter browser-native install
```

Print the packaged extension directory:

```powershell
chatgpt-web-adapter browser-native extension-dir
```

Load that directory through `chrome://extensions` -> Developer mode -> Load unpacked. The packaged extension has stable identity:

```text
kjfnkhajljnkbhikmfijcchenlfglaie
```

Verify the bridge:

```powershell
chatgpt-web-adapter browser-native status
```

A healthy bridge reports `available=true` and `extension_connected=true`.

The low-level browser-native API is research/diagnostic. Application code should normally use `ChatGPTProductRuntime`, which assembles the browser-owned transport behind the generic product transport contract.

## Production CLI Quick Start

Read-only runtime readiness and capabilities:

```powershell
chatgpt-web-adapter runtime status
```

For an existing conversation:

```powershell
chatgpt-web-adapter runtime status `
  --conversation <conversation-id>
```

Send a new ordinary text turn:

```powershell
chatgpt-web-adapter runtime send "Hello from the product runtime"
```

Continue an existing conversation:

```powershell
chatgpt-web-adapter runtime send `
  "Continue this conversation" `
  --conversation <conversation-id>
```

The production transport set is intentionally closed. Unknown transports fail closed and there is no fallback to the legacy direct-write path.

## Production Python Quick Start

```python
from chatgpt_web_adapter import assemble_product_runtime

runtime = assemble_product_runtime(
    transport="browser-owned",
    auth_file="auth_data.json",
)

health = runtime.health()
if not health.ready:
    raise RuntimeError(health.reason)

print(runtime.capabilities().to_dict())

execution = runtime.send_text_observed("Give me a short project summary.")
print(execution.response.text)
print(execution.provenance.to_dict())
```

For ordinary callers, `runtime.send(...)` is the compact entrypoint when transport observation/provenance is not needed directly.

Canonical lifecycle access remains on the same runtime:

```python
status = runtime.get_status(conversation_id)
messages = runtime.get_messages(conversation_id)
attached = runtime.attach_conversation(conversation_id)
```

### Rich input

On the live-proven production/default browser-owned provider path, the same runtime accepts images and general files and supports multimodal continuation through `media=`. Local paths, bytes-like values, path-like values, and `(source, filename)` media items are represented by the shared `MediaSource` / `MediaItem` types.

Rich-input capability graduation is provider-aware: a custom provider does not inherit `AVAILABLE` merely because its transport id is `browser-owned`. CWA only reports the PR9.2 capabilities as available when the configured provider preserves the proven send/RPC path.

### Structured product observations

`send_text_observed()` also returns immutable typed product observations through `ProductRuntimeExecution.observations`. The root production value types include:

```python
from chatgpt_web_adapter import (
    ProductActivityObservation,
    ProductCitationObservation,
    ProductObservationKind,
    ProductObservationPhase,
    ProductRequiredActionObservation,
    ProductSourceObservation,
    StructuredProductObservation,
)
```

The observation layer can represent search activity, tool/activity points, source identity, citation-to-source relationships and required-action evidence. Observation defects do not become write failures, retry authority, canonical finality, connector authorization, or downstream mutation authority.

## Capabilities

The product runtime distinguishes four states:

- `AVAILABLE` — implemented and evidence-backed on this declared runtime/provider path;
- `UNSUPPORTED` — known not to be provided by the contract;
- `UNKNOWN` — not sufficiently characterized;
- `UNIMPLEMENTED` — product-present or plausible, but not implemented by this runtime surface.

On the production/default browser-owned provider, CWA 0.3 has evidence-backed ordinary text new-chat/continuation, canonical readback, streaming/Temporary/model behavior from the 0.2 baseline, image input, general file input, multimodal continuation, and web-search observation. Generic product-tool observations have also been characterized.

Capability state remains narrower than product visibility. In particular, `tools_connectors` remains `UNKNOWN`: observing a tool event does not prove a general caller-selectable tool contract, connector coverage, connector credentials/authorization, required-action continuation, or external-action authority.

The alternative `browserless-request` transport remains `EXPERIMENTAL` even where individual capability entries are implemented. Transport support tier and capability state are separate contracts.

## Provenance and Completion

`send_text_observed()` returns structured provenance. Completion evidence is separate from optional backend metadata.

A successful turn may therefore report:

```text
completion.completed = true
completion.source = CANONICAL_READBACK
completion.canonical_completion_proven = true
finish_reason = null
finish_reason_observed = false
```

The runtime never fabricates a synthetic `stop` merely because another canonical signal proved completion.

Browser-specific observations such as runtime-tab creation/reuse remain transport metadata rather than mandatory generic product fields. Structured product observations likewise do not establish canonical completion; canonical readback remains final authority.

## Browser UX Note

The extension does not intentionally request foreground activation for its reusable runtime tab. A warm reusable-tab path has been observed to stay inactive. On a cold path where no runtime tab exists, Chrome may still foreground a newly created tab even though the runtime did not request activation. Treat foreground disturbance as an observed browser behavior, not as a guaranteed invariant.

## Compatibility: `ChatGPTWebClient`

Existing applications do not need an immediate rewrite:

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
messages = client.get_messages("<conversation-id>")
```

The historical client remains the compatibility surface for older workflows. Existing Sentinel-enabled protected-write examples are kept for regression and migration reference, but `auto_sentinel=True` is no longer the recommended architecture for new ordinary product-turn integrations.

No compatibility decision silently redirects `ChatGPTWebClient.send()` into `ChatGPTProductRuntime`, and the production runtime never falls back into `ChatGPTWebClient.send()`.

## Experimental and Research Workflows

Experimental web-backend helpers include:

- `approve_pending_action()`;
- `wait_and_approve_pending_actions()`;
- `send_and_auto_approve()`;
- `PayloadBuilder`;
- `validate_payload`;
- `send_payload` through the compatibility client;
- prepared/raw backend diagnostics;
- the `browserless-request` product transport.

See [docs/raw_payload.md](docs/raw_payload.md) and [docs/browserless_request_transport_pr9_1.md](docs/browserless_request_transport_pr9_1.md).

Research/diagnostic surfaces include direct `BrowserNativeTurnProvider`, Native Messaging installation helpers, and Sentinel transaction/provider symbols. These remain available because they are useful for regression diagnosis and future transport comparison; isolation comes before deletion.

## Examples

Primary production example:

- [examples/product_runtime.py](examples/product_runtime.py) — current `ChatGPTProductRuntime`, capabilities, send, and provenance.

Compatibility examples:

- [examples/basic_send.py](examples/basic_send.py)
- [examples/continue_saved.py](examples/continue_saved.py)
- [examples/attach_existing.py](examples/attach_existing.py)
- [examples/read_messages.py](examples/read_messages.py)
- [examples/status_polling.py](examples/status_polling.py)

Experimental examples:

- [examples/approve_tools.py](examples/approve_tools.py)
- [examples/raw_payload.py](examples/raw_payload.py)
- [examples/github_auto_approve.py](examples/github_auto_approve.py)

Research/diagnostic examples:

- [examples/browser_native_send.py](examples/browser_native_send.py)
- [examples/diagnose_latency.py](examples/diagnose_latency.py)
- [examples/watch_conversation.py](examples/watch_conversation.py)

PR-specific feasibility probes may also live in `examples/`; they are not automatically part of the public production SDK surface.

## Architecture and Operational Docs

- [ROADMAP.md](ROADMAP.md) — post-0.2 PR9 architecture direction
- [docs/public_surface_pr8_6.md](docs/public_surface_pr8_6.md) — support tiers and compatibility decisions
- [docs/architecture.md](docs/architecture.md) — current runtime/canonical/transport layering
- [docs/browser_owned_v1_contract.md](docs/browser_owned_v1_contract.md) — production browser-owned runtime contract
- [docs/browserless_request_transport_pr9_1.md](docs/browserless_request_transport_pr9_1.md) — experimental browserless-request boundary
- [docs/product_runtime_observation_integration_pr9_3.md](docs/product_runtime_observation_integration_pr9_3.md) — runtime observation integration
- [docs/product_source_citation_observation_pr9_3.md](docs/product_source_citation_observation_pr9_3.md) — source/citation observation boundary
- [docs/product_capabilities_provenance_pr8_5.md](docs/product_capabilities_provenance_pr8_5.md) — capabilities and provenance
- [docs/browser_native_runtime.md](docs/browser_native_runtime.md) — low-level implementation/setup history
- [docs/authentication.md](docs/authentication.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/raw_payload.md](docs/raw_payload.md)
- [docs/rename_compatibility.md](docs/rename_compatibility.md)
- [docs/release_checklist.md](docs/release_checklist.md)

`USAGE.md` remains a detailed compatibility-client guide for the historical `ChatGPTWebClient` feature set. New ordinary text-turn integrations should start with this README and `examples/product_runtime.py` instead.

## Known Failure Modes

- reusable session auth expires or is revoked;
- ChatGPT product/page structure changes;
- the extension or Native Messaging host is not connected;
- the reusable runtime tab is closed and must be reconciled/recreated;
- canonical response/message schemas change;
- rich-input page/request correlation changes;
- source/citation metadata shapes change;
- browserless Sentinel admission requires challenge evidence and fails closed;
- experimental legacy backend contracts drift;
- an ambiguous delegated write requires reconciliation rather than automatic retry.

See [docs/troubleshooting.md](docs/troubleshooting.md).

## Compatibility Policy

- `ChatGPTProductRuntime` is the primary forward-looking production compatibility target.
- `ChatGPTWebClient` is retained without deprecation for existing callers and historical feature coverage.
- experimental APIs may evolve faster.
- research/diagnostic APIs have no application-level stability promise even though imports remain available today.
- no legacy symbol is removed solely for tree cleanliness; removal requires a separate evidence-backed migration decision.
- undocumented `chatgpt.com` behavior can change independently of package releases.

## Package Naming

Canonical package naming is:

- repository: `chatgpt-web-adapter`
- distribution: `chatgpt-web-adapter`
- import: `chatgpt_web_adapter`

See [docs/rename_compatibility.md](docs/rename_compatibility.md).
