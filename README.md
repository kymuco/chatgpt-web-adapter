# chatgpt-web-adapter

[![CI](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml)

Product-runtime adapter for using an existing ordinary ChatGPT web session from Python, HDE-style local runtimes, and terminal tools.

> [!WARNING]
> Not the official OpenAI API.
> Uses an existing ChatGPT web session and ordinary ChatGPT product semantics.
> Browser and web-product behavior may change.

`chatgpt-web-adapter` now has one forward-looking production surface:

```text
ChatGPTProductRuntime
  -> browserless canonical read/status/session plane
  -> explicit ProductWriteTransport
  -> browser-owned page write for protected text turns
  -> canonical browserless assistant readback
```

The first proven production write transport is `browser-owned`. It uses one reusable ChatGPT tab owned by the Chrome extension for the protected product write, while canonical reads and session lifecycle remain browserless where possible.

The historical `ChatGPTWebClient` API is still available for compatibility and for capabilities that have not yet graduated into the product runtime. Sentinel/prepared/direct-write and direct browser-native APIs are retained as research or diagnostic surfaces; they are no longer the recommended starting point for new production integrations.

See [ROADMAP.md](ROADMAP.md) for the post-PR8 architecture plan and [docs/public_surface_pr8_6.md](docs/public_surface_pr8_6.md) for the support-tier and compatibility policy.

## What This Is

`chatgpt-web-adapter` is a local adapter around an authenticated ChatGPT product session. It separates:

- **canonical observation** — conversation attach/read/status and session lifecycle;
- **product mutation** — an explicit product write transport;
- **runtime orchestration** — `ChatGPTProductRuntime`;
- **capability declarations** — `AVAILABLE`, `UNSUPPORTED`, `UNKNOWN`, `UNIMPLEMENTED`;
- **execution provenance** — transport, planes, completion evidence, identity, and transport-specific observations.

It is designed so callers such as HDE do not need to know Chrome tab IDs, extension worker names, Native Messaging details, or Sentinel internals.

## What This Is Not

`chatgpt-web-adapter` is not:

- the official OpenAI API;
- a replacement for the OpenAI Python SDK;
- a documented long-term OpenAI platform contract;
- a browser-challenge bypass, Turnstile solver, proof-token synthesizer, or credential replay system;
- a full chat application, TUI, or local history product.

If you need an officially supported API contract, use the official OpenAI platform rather than this package.

## Public Surface Tiers

PR8.6 makes support level explicit.

### Primary production

Canonical tier: `PRIMARY_PRODUCTION`.

Use these for new product-runtime integrations:

- `assemble_product_runtime()`;
- `ChatGPTProductRuntime`;
- `ProductWriteTransport`;
- `CanonicalConversationClient`;
- capability and provenance models;
- `chatgpt-web-adapter runtime status`;
- `chatgpt-web-adapter runtime send`.

### Shared support

Canonical tier: `SHARED_SUPPORT`.

Auth/session helpers, core response/conversation types, and common errors are shared by the production runtime and compatibility surface.

### Compatibility

Canonical tier: `COMPATIBILITY`.

`ChatGPTWebClient` / `WebChatClient` remain import-compatible and supported for existing callers. They also retain features that the production browser-owned text transport has not yet implemented, including existing streaming/media/web-backend workflows.

PR8.6 does **not** emit deprecation warnings and does not remove these APIs. New ordinary text-turn integrations should prefer `ChatGPTProductRuntime`.

### Experimental

Canonical tier: `EXPERIMENTAL`.

Approval, raw-payload, and prepared-web-backend helpers remain experimental because they depend more directly on changing undocumented web behavior.

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

## Capabilities

The product runtime distinguishes four states:

- `AVAILABLE` — implemented and evidence-backed on this transport;
- `UNSUPPORTED` — known not to be provided by the contract;
- `UNKNOWN` — not sufficiently characterized;
- `UNIMPLEMENTED` — product-present or plausible, but not implemented by this runtime surface.

The current browser-owned production transport has evidence-backed ordinary text new-chat/continuation and canonical readback. Other product features are deliberately not implied from what the ChatGPT UI may support.

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

Browser-specific observations such as runtime-tab creation/reuse remain transport metadata rather than mandatory generic product fields.

## Browser UX Note

The extension does not intentionally request foreground activation for its reusable runtime tab. A warm reusable-tab path has been observed to stay inactive. On a cold path where no runtime tab exists, Chrome may still foreground a newly created tab even though the runtime did not request activation. Treat foreground disturbance as an observed browser behavior, not as a guaranteed invariant.

## Compatibility: `ChatGPTWebClient`

Existing applications do not need an immediate rewrite:

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
messages = client.get_messages("<conversation-id>")
```

The historical client remains the compatibility surface for older workflows. Existing Sentinel-enabled protected-write examples are kept for regression and migration reference, but `auto_sentinel=True` is no longer the recommended architecture for new ordinary text-turn integrations.

No PR8.6 compatibility decision silently redirects `ChatGPTWebClient.send()` into `ChatGPTProductRuntime`, and the production runtime never falls back into `ChatGPTWebClient.send()`.

## Experimental and Research Workflows

Experimental web-backend helpers include:

- `approve_pending_action()`;
- `wait_and_approve_pending_actions()`;
- `send_and_auto_approve()`;
- `PayloadBuilder`;
- `validate_payload`;
- `send_payload` through the compatibility client;
- prepared/raw backend diagnostics.

See [docs/raw_payload.md](docs/raw_payload.md).

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

- [ROADMAP.md](ROADMAP.md) — post-PR8 architecture direction and PR9.0 alternatives
- [docs/public_surface_pr8_6.md](docs/public_surface_pr8_6.md) — support tiers and compatibility decisions
- [docs/architecture.md](docs/architecture.md) — current runtime/canonical/transport layering
- [docs/product_runtime_pr8_3.md](docs/product_runtime_pr8_3.md) — production runtime assembly baseline
- [docs/product_transport_protocol_pr8_4.md](docs/product_transport_protocol_pr8_4.md) — transport/canonical interface separation
- [docs/product_capabilities_provenance_pr8_5.md](docs/product_capabilities_provenance_pr8_5.md) — capabilities and provenance
- [docs/browser_native_runtime.md](docs/browser_native_runtime.md) — low-level implementation/setup history
- [docs/authentication.md](docs/authentication.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/raw_payload.md](docs/raw_payload.md)
- [docs/rename_compatibility.md](docs/rename_compatibility.md)

`USAGE.md` remains a detailed compatibility-client guide for the historical `ChatGPTWebClient` feature set. New ordinary text-turn integrations should start with this README and `examples/product_runtime.py` instead.

## Known Failure Modes

- reusable session auth expires or is revoked;
- ChatGPT product/page structure changes;
- the extension or Native Messaging host is not connected;
- the reusable runtime tab is closed and must be reconciled/recreated;
- canonical response/message schemas change;
- experimental legacy backend contracts drift;
- an ambiguous delegated write requires reconciliation rather than automatic retry.

See [docs/troubleshooting.md](docs/troubleshooting.md).

## Compatibility Policy

- `ChatGPTProductRuntime` is the primary forward-looking production compatibility target.
- `ChatGPTWebClient` is retained without deprecation in PR8.6 for existing callers and feature coverage not yet present in the product runtime.
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