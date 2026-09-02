# chatgpt-web-adapter

[![CI](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/kymuco/chatgpt-web-adapter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/chatgpt-web-adapter.svg)](https://pypi.org/project/chatgpt-web-adapter/)
[![Python](https://img.shields.io/pypi/pyversions/chatgpt-web-adapter.svg)](https://pypi.org/project/chatgpt-web-adapter/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Product-runtime adapter for using an existing ordinary ChatGPT web session from Python, HDE-style local runtimes, and terminal tools.**

[Documentation](docs/README.md) · [Architecture](docs/architecture.md) · [Status](STATUS.md) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

> [!WARNING]
> Not the official OpenAI API.  
> Uses an existing ChatGPT web session and ordinary ChatGPT product semantics.  
> Browser and web-product behavior may change.

> **Product observation is not authority. Streaming is not finality. Ambiguous writes are not automatically retried.**

`chatgpt-web-adapter` (CWA) wraps an authenticated ChatGPT web-product session behind a typed Python runtime and CLI. The forward-looking application boundary is `ChatGPTProductRuntime`; the production write transport is `browser-owned`. The historical `ChatGPTWebClient` remains available as a compatibility surface, while low-level Sentinel/direct browser-native APIs remain research or diagnostic surfaces.

## Current status

- **Latest public release:** `v0.3.0` — 2026-09-01.
- **Current `main`:** post-0.3 development through merged PR10.1.
- **Production write transport:** `browser-owned`.
- **Experimental transport:** `browserless-request`.
- **Current product boundary:** text, images, general files, multimodal continuation, canonical conversation reads, streaming/finality, model profiles, Temporary Chat, web-search observation, and typed product observations are implemented on their evidence-backed paths.
- **Conservative boundaries:** `tools_connectors` remains `UNKNOWN`; generated-artifact download handoff remains unsupported without a stable product-owned artifact identity and safe resolution path.
- **Generated-artifact handoff status:** `ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY`.

See [STATUS.md](STATUS.md) for the compact current-state snapshot and [ROADMAP.md](ROADMAP.md) for what comes next.

## Why CWA

CWA is for callers that want ordinary ChatGPT product semantics without embedding browser internals throughout their application.

```text
application / HDE / CMA / terminal
               |
               v
       ChatGPTProductRuntime
          /       |       \
         /        |        \
 canonical     product    structured
 read/status    write     observations
     |            |           |
     |      browser-owned      |
     |        PRODUCTION       |
     +------------+------------+
                  |
                  v
            ChatGPT product
```

The runtime deliberately separates:

- **canonical observation** — attach/read/status and final assistant readback;
- **product mutation** — an explicit product write transport;
- **structured observations** — bounded search/tool/source/citation/required-action evidence;
- **capability state** — `AVAILABLE`, `UNSUPPORTED`, `UNKNOWN`, `UNIMPLEMENTED`;
- **support tier** — production, shared support, compatibility, experimental, research/diagnostic;
- **downstream authority** — always owned by the caller, never inferred from product evidence.

## Capability snapshot

| Surface | Current state | Notes |
| --- | --- | --- |
| Ordinary text new chat / continuation | Production | Browser-owned protected write + canonical readback |
| Canonical messages / status / attach | Production | Browserless where supported |
| Revision-safe streaming / final-only | Production | Incremental output never becomes canonical finality |
| Model profiles | Production | `INSTANT` / `MEDIUM` / `HIGH` CLI aliases; semantic Python profiles remain supported |
| Temporary Chat | Production | Session-local authority; no durable fallback |
| Images and general files | Production on the proven default provider path | Exact attachment-set and request correlation guards |
| Multimodal continuation | Production on the proven default provider path | Same canonical finality boundary |
| Web-search observation | Production on the proven default provider path | Typed search/source/citation evidence |
| Generic product-tool observation | Observed | Reports what the product emitted; does not create caller tool authority |
| Required-action point evidence | Observed | Can represent visible authorization requirements without approving them |
| Connector execution lifecycle | Conservative / `tools_connectors=UNKNOWN` | Requires explicit stable product identity/correlation |
| Generated-artifact observation | Bounded internal boundary | Observation does not grant download authority |
| Generated-artifact download | Unsupported today | Reopens only with stable product-owned identity + safe browser-owned resolution |
| `browserless-request` writes | Experimental | May fail closed at current challenge/Sentinel boundaries |

Capability state is provider-aware. A custom provider does not inherit an `AVAILABLE` capability merely because it uses the same transport name.

## Quick start

### Install

```bash
python -m pip install "chatgpt-web-adapter[browser]"
```

Requirements:

- Python 3.10-3.14;
- system `curl` in `PATH` for the canonical web-session client;
- an authenticated ChatGPT web session;
- Chrome/Chromium plus the packaged extension and Native Messaging host for production protected writes.

### Authenticate once

```bash
chatgpt-web-adapter auth login --auth-file auth_data.json
chatgpt-web-adapter auth status --auth-file auth_data.json
```

`auth_data.json` contains reusable account/session material. Do not commit or share it. See [docs/authentication.md](docs/authentication.md) and [SECURITY.md](SECURITY.md).

### Install the browser-owned bridge

```powershell
chatgpt-web-adapter browser-native install
chatgpt-web-adapter browser-native extension-dir
```

Load the printed extension directory through `chrome://extensions` → Developer mode → Load unpacked, then verify:

```powershell
chatgpt-web-adapter browser-native status
cwa doctor --json
```

A healthy bridge reports the extension connected and the runtime ready.

### Send from the CLI

```powershell
cwa send "Give me a short project summary." --profile HIGH
```

Useful stable commands:

```powershell
cwa doctor --json
cwa status --json
cwa capabilities --json
cwa messages <conversation-id> --json
cwa snapshot <conversation-id> --name project --output-dir ./artifacts --json
cwa export <conversation-id> --format jsonl --name project --output-dir ./artifacts --json
```

The long-form runtime commands remain supported:

```powershell
chatgpt-web-adapter runtime status
chatgpt-web-adapter runtime send "Hello from the product runtime"
```

Temporary Chat:

```powershell
cwa send "Answer briefly." --temporary --profile INSTANT
```

The stable CLI is intentionally narrower than the complete Python runtime surface.

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
print(execution.observations)
```

Canonical lifecycle access remains on the same runtime:

```python
status = runtime.get_status(conversation_id)
messages = runtime.get_messages(conversation_id)
attached = runtime.attach_conversation(conversation_id)
```

For ordinary callers, `runtime.send(...)` is the compact entrypoint when the complete observation/provenance result is not needed directly.

### Rich input

On the live-proven production/default browser-owned provider path, `send_text_observed()` accepts images and general files through `media=`:

```python
execution = runtime.send_text_observed(
    "Describe this image and summarize the attached notes.",
    media=["./diagram.png", "./notes.txt"],
)
```

The official ChatGPT page owns upload and protected submit. CWA validates the requested attachment set and preserves the same canonical finality/no-retry boundary as ordinary text turns.

## Capabilities

Runtime capability declarations are evidence-backed and provider-aware. Use `runtime.capabilities()` rather than inferring support from a transport name, a visible ChatGPT UI control, or the presence of an internal implementation module.

The compact status table above is the repository-level snapshot; [STATUS.md](STATUS.md) records the current post-0.3 boundaries in more detail.

## Structured product observations

`send_text_observed()` can return immutable typed observations for search activity, generic tool/activity points, source identity, citation relationships and required-action evidence.

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

The governing rule is:

```text
product observation
!= product approval
!= connector authorization
!= write/retry authority
!= canonical finality
!= filesystem/Git/workspace authority
```

PR10.0 adds stronger connector/required-action lifecycle models when an explicit stable product identifier exists, but current authenticated product evidence remains conservative and does not graduate the combined `tools_connectors` capability.

PR10.1 also establishes a bounded generated-artifact observation boundary. Actual download/materialization is intentionally not implemented until a stable product-owned artifact identity and safe browser-owned resolution path are proven. See [docs/generated_artifact_handoff_pr10_1.md](docs/generated_artifact_handoff_pr10_1.md).

## Public Surface Tiers

Support level is explicit and machine-readable.

### Primary production

Canonical tier: `PRIMARY_PRODUCTION`.

Use these for new integrations:

- `assemble_product_runtime()`;
- `ChatGPTProductRuntime`;
- `ProductWriteTransport`;
- `CanonicalConversationClient`;
- capability, contract and provenance models;
- immutable root-exported structured observation value types;
- `chatgpt-web-adapter runtime status`;
- `chatgpt-web-adapter runtime send`.

### Shared support

Canonical tier: `SHARED_SUPPORT`.

Auth/session helpers, common response/conversation types, errors, and the `MediaItem` / `MediaSource` rich-input types.

### Compatibility

Canonical tier: `COMPATIBILITY`.

`ChatGPTWebClient` / `WebChatClient` remain supported for existing callers and historical workflows. They are not silently redirected into `ChatGPTProductRuntime`.

Existing Sentinel-era behavior remains discoverable for migration and regression work; for example `auto_sentinel=True` remains a compatibility concept rather than the recommended architecture for new integrations.

### Experimental

Canonical tier: `EXPERIMENTAL`.

Approval helpers, raw/prepared web-backend helpers, `PayloadBuilder`, `validate_payload`, `send_payload`, and the `browserless-request` transport depend more directly on undocumented product behavior and may evolve faster.

See [docs/raw_payload.md](docs/raw_payload.md).

### Research / diagnostic

Canonical tier: `RESEARCH_DIAGNOSTIC`.

Direct `BrowserNativeTurnProvider`, Sentinel transaction/provider internals, low-level bridge diagnostics, and PR-specific probes exist for transport research and regression diagnosis. They are not the application API.

The machine-readable classification is available through:

```python
from chatgpt_web_adapter import PUBLIC_SURFACE_CLASSIFICATION, public_surface_tier

print(public_surface_tier("ChatGPTProductRuntime"))
print(public_surface_tier("ChatGPTWebClient"))
```

The detailed historical tier decision is preserved in [docs/public_surface_pr8_6.md](docs/public_surface_pr8_6.md).

## Safety and failure model

CWA intentionally fails closed around uncertain product state.

- No automatic retry after an ambiguous write.
- No silent browser-owned ↔ browserless ↔ legacy fallback.
- Streaming does not prove canonical completion.
- Generic tool/router activity does not prove connector identity.
- Required-action observation does not approve an action.
- Generated-artifact observation does not authorize download or filesystem writes.
- CWA does not implement Turnstile solving, proof-token synthesis, credential replay, or challenge-bypass machinery.

For operational failures, see [docs/troubleshooting.md](docs/troubleshooting.md). For security-sensitive behavior, see [SECURITY.md](SECURITY.md).

## Examples

Primary production example:

- [examples/product_runtime.py](examples/product_runtime.py) — primary `ChatGPTProductRuntime` example.

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

PR-specific feasibility probes may also live in `examples/`; their presence does not promote them into the public production SDK.

## Documentation

Use [docs/README.md](docs/README.md) as the documentation map.

Current entry points:

- [STATUS.md](STATUS.md) — current release/main/capability snapshot;
- [ROADMAP.md](ROADMAP.md) — current development direction;
- [USAGE.md](USAGE.md) — current runtime-first user guide with a separate compatibility section;
- [docs/architecture.md](docs/architecture.md) — current runtime architecture;
- [docs/browser_owned_v1_contract.md](docs/browser_owned_v1_contract.md) — production browser-owned contract;
- [docs/product_rich_input_pr9_2.md](docs/product_rich_input_pr9_2.md) — rich-input evidence and boundary;
- [docs/product_runtime_observation_integration_pr9_3.md](docs/product_runtime_observation_integration_pr9_3.md) — observation integration;
- [docs/generated_artifact_handoff_pr10_1.md](docs/generated_artifact_handoff_pr10_1.md) — current artifact handoff boundary;
- [docs/authentication.md](docs/authentication.md);
- [docs/troubleshooting.md](docs/troubleshooting.md);
- [docs/release_checklist.md](docs/release_checklist.md);
- [docs/rename_compatibility.md](docs/rename_compatibility.md).

Historical PR-specific documents remain in `docs/` as evidence and architectural lineage. They are not all current getting-started documentation.

## Development

```bash
python -m pip install -e ".[test,browser]"
python -m pytest -q
```

Product-facing changes require deterministic regression coverage and bounded live validation appropriate to the changed surface. Documentation-only changes do not justify a live product write.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Release integrity

CWA validates source tests on Ubuntu and Windows across Python 3.10-3.14, builds wheel + sdist, checks distribution metadata/contracts, and smoke-tests the exact installed wheel outside the source checkout.

Tagged publication additionally requires:

```text
GitHub tag version == pyproject package version == dated CHANGELOG release heading
```

The latest public release is [v0.3.0](https://github.com/kymuco/chatgpt-web-adapter/releases/tag/v0.3.0).

## Package naming

- repository: `chatgpt-web-adapter`
- distribution: `chatgpt-web-adapter`
- import: `chatgpt_web_adapter`

See [docs/rename_compatibility.md](docs/rename_compatibility.md).

## License

MIT. See [LICENSE](LICENSE).
