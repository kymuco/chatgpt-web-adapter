# PR8.4 — Product Transport Protocol and Canonical/Write Plane Separation

## Outcome

PR8.4 turns the PR8.3 browser-owned runtime from the definition of the product runtime into the first concrete transport behind a stable interface.

The intended composition is now:

```text
ChatGPTProductRuntime
├─ CanonicalConversationClient
│  ├─ attach_conversation
│  ├─ get_messages
│  └─ get_status
│
└─ ProductWriteTransport
   └─ BrowserOwnedProductTransport
      └─ BrowserOwnedProductWriteRuntime  (proven PR8.2.x implementation)
```

The browser-owned implementation remains the only registered production transport. PR8.4 does not add a second transport and does not change the live browser mechanism.

## New contracts

`product_transport.py` defines:

- `CanonicalConversationClient` — the canonical conversation observation contract used by `ChatGPTProductRuntime`;
- `CanonicalSessionClient` — an optional explicit session/auth lifecycle contract for later migration; runtime dispatch does not require it yet;
- `ProductWriteTransport` — the write-side transport protocol;
- `ProductRuntimeHealth` — generic readiness plus optional compatibility metadata;
- `ProductRuntimeExecution` — transport-labelled response plus implementation-specific observation;
- fail-closed structural validators for canonical and write contracts.

The transport protocol deliberately contains no Native Messaging, extension, CDP, runtime-tab, Sentinel, Turnstile, or proof-token concept.

Browser-specific readiness fields remain optional in `ProductRuntimeHealth` only to preserve PR8.3 CLI/SDK compatibility. A future transport is not required to synthesize them.

## Browser-owned adapter

`BrowserOwnedProductTransport` is intentionally thin. It wraps `BrowserOwnedProductWriteRuntime` and translates its health/execution values into the generic contract.

It does not reimplement:

- page submission;
- Native Messaging;
- provider registration;
- preflight semantics;
- continuation commit-point recheck;
- canonical assistant readback;
- ambiguous-write classification;
- retry governance.

Those mechanisms remain in the already live-proven PR8.2.x writer for PR8.4.

## Ownership after PR8.4

| Concern | Owner in PR8.4 | Rationale |
| --- | --- | --- |
| transport selection | `ChatGPTProductRuntime` / assembly | selection must remain explicit and fail closed |
| canonical attach/messages/status API | `CanonicalConversationClient` | independent of one write transport |
| session refresh configuration | canonical `ChatGPTWebClient` assembly | preserve current browserless session behavior without a broad rewrite |
| browser bridge/tab/page state | browser-owned implementation | browser authority stays browser-local |
| write preflight | existing `BrowserOwnedProductWriteRuntime` | already live-proven; do not rewrite in interface PR |
| continuation commit-point recheck | existing `BrowserOwnedProductWriteRuntime` | closes completed→busy race before delegation |
| delegated-write ambiguity | existing `BrowserOwnedProductWriteRuntime` | unknown outcome remains non-retryable automatically |
| canonical readback after browser write | existing browser-owned path | successful response still requires canonical completion/readback |
| no-fallback policy | `ChatGPTProductRuntime` | transport failure must not silently select legacy direct write |

This is an interface-separation milestone, not the final extraction of every lifecycle policy. The important constraint is that `ProductWriteTransport` does not prescribe browser-specific mechanics, so later transports can satisfy the contract without inheriting Chrome implementation details.

## Compatibility

Existing PR8.3 callers remain valid:

```python
runtime = assemble_product_runtime(transport="browser-owned")
runtime.send("hello")
```

Direct construction with `provider=` also remains available as a compatibility shortcut:

```python
runtime = ChatGPTProductRuntime(client, provider=provider)
```

New composition/testing code may inject a protocol-conforming transport:

```python
runtime = ChatGPTProductRuntime(
    canonical_client,
    transport="browser-owned",
    write_transport=transport,
)
```

`provider=` and `write_transport=` are mutually exclusive. An injected transport must report the same identity as the explicitly selected production transport. This prevents transport injection from becoming a hidden fallback or an unregistered second production route.

`ChatGPTWebClient.send()` is unchanged by PR8.4.

## Governance invariants

PR8.4 preserves:

- `browser-owned` as the only registered production transport;
- no silent legacy/direct-write fallback;
- no automatic retry after ambiguous delegated writes;
- canonical completion/readback as authoritative response evidence;
- browserless canonical read/status/session plane;
- page-owned browser write plane;
- no runtime-owned browser process launch;
- no requested foreground activation;
- no challenge solving, protection emulation, credential replay, or direct private product-write reconstruction.

## Explicit non-goals

PR8.4 does not:

- add capabilities state modelling — PR8.5 owns that;
- add response provenance modelling — PR8.5 owns that;
- move or delete Sentinel/direct-write code — PR8.6 owns isolation/reclassification;
- restructure the whole package into `product/`, `canonical/`, and `transports/` directories;
- add another model/product provider;
- add a hidden/non-tab browser execution experiment;
- optimize performance or perform daily-use stress testing.

## Validation gates

The PR should be considered complete when:

1. the existing PR8.3 browser-owned assembly remains source-compatible;
2. `ChatGPTProductRuntime` works with a protocol-conforming fake write transport;
3. canonical read methods are independently delegated to the canonical client;
4. protocol definitions contain no browser/Sentinel implementation dependency;
5. the browser-owned adapter wraps rather than reimplements the proven writer;
6. unknown transport identities and identity mismatch fail closed;
7. provider + explicit transport injection ambiguity is rejected;
8. no fallback transport is introduced;
9. canonical readback and ambiguous-write safety remain inherited unchanged from the proven writer;
10. the repository-wide regression suite remains green.

## Next step

After PR8.4 is validated, PR8.5 should build on these interfaces rather than on browser-owned internals:

**PR8.5 — Product Capability Model, Transport Feature Declaration and Provenance-Aware Response Governance**.
