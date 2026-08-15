# chatgpt-web-adapter Roadmap

_Last updated: 2026-08-15_

This roadmap defines the architectural direction after the PR8.2.x browser-owned transport research and PR8.3 production integration work. It is intentionally broader than a release checklist: it records the current evidence, the invariants that must survive future refactors, the next architectural PR sequence, the alternative runtime architectures that should be evaluated, and the decision points for a possible next-generation bridge.

The immediate goal is **not** to maximize turn count or rush daily-use stress testing. The immediate goal is to make sure the library does not accidentally fossilize around a working prototype before its ownership boundaries and public contracts are clean.

---

## 1. Current Proven Baseline

The PR8 series established a working ordinary-ChatGPT product transport with the following shape:

```text
HDE / terminal / Python caller
        |
        +-- READ / STATUS / SESSION
        |      -> browserless canonical HTTP
        |
        `-- WRITE
               -> Native Messaging
               -> Chrome extension
               -> one reusable inactive ordinary ChatGPT tab
               -> official page-owned product turn
               -> browserless canonical finality/readback
```

### Proven properties

The current branch has live evidence for:

- ordinary ChatGPT product semantics rather than a separate API product;
- explicit browser-owned write delegation;
- browserless canonical conversation reads, status, and session lifecycle;
- new-chat creation;
- existing-conversation continuation;
- canonical response readback;
- exact conversation/message identity recovery;
- one reusable inactive ChatGPT runtime tab;
- on-demand runtime-tab creation when absent;
- stale stored-tab reconciliation;
- same-tab reuse across turns;
- no observed foreground activation during validated turns;
- no automatic retry after an ambiguous delegated write;
- no legacy/direct-write fallback from the production runtime;
- explicit `browser-owned` transport selection through `ChatGPTProductRuntime`;
- a CLI production entrypoint through `chatgpt-web-adapter runtime ...`;
- a green repository-wide regression suite after PR8.3 test-boundary repair.

### PR8.2.5 boundary

The supported Chrome surfaces reviewed in PR8.2.5 did **not** reveal a qualifying supported hidden/non-tab runtime that simultaneously preserves ordinary top-level ChatGPT product semantics.

The current minimum proven substrate therefore remains:

```text
ONE REUSABLE INACTIVE ORDINARY CHATGPT TAB
```

This is a reopenable evidence boundary, not a claim that every undocumented browser trick is physically impossible. Reopen it only if a newly documented Chrome or OpenAI-supported product surface materially changes the available architecture.

### Why daily-use stress is deferred

A 20-turn or multi-day stress run would test endurance of the current shape, but the larger near-term risk is architectural: continuing to add features around historical layers could make the library harder to evolve than the transport itself.

Stress becomes high-value again **after** the transport/canonical/public interfaces are stabilized. At that point it should validate the architecture we actually intend to keep.

---

## 2. Strategic Shift After PR8.3

PR8.3 proves that the machine can run. The next phase should answer a different question:

> What should `chatgpt-web-adapter` become now that a working ordinary-product transport exists?

The current package contains several historical generations at once:

```text
ChatGPTWebClient
├─ browserless canonical reads/session logic
├─ legacy/direct web write paths
├─ prepared/Sentinel write machinery
├─ browser-native experimental APIs
└─ PR8.3 production facade
     └─ BrowserOwnedProductWriteRuntime
```

This is acceptable as research history, but it is not the desired long-term mental model.

The target is a library where product orchestration, canonical observation, and write transport are explicit independent concepts.

---

## 3. Architectural Invariants

Future PRs must preserve these invariants unless a later evidence-backed design explicitly supersedes one.

1. **Ordinary product semantics are a first-class requirement.** Do not silently substitute a different product/API surface while calling it equivalent.
2. **Canonical observation and product mutation are separate planes.** Read/status/session logic must not be coupled to one particular write mechanism.
3. **Transport selection is explicit.** No silent `browser-owned -> legacy direct write` fallback.
4. **Ambiguous writes are never automatically retried.** Reconciliation precedes any manual retry decision.
5. **Canonical readback remains authoritative.** Page submission success alone is not sufficient product completion evidence.
6. **Browser authority stays browser-local where possible.** Browser state, tab state, and page interaction should remain owned by the browser-side component rather than reconstructed externally without need.
7. **HDE must not depend on Chrome implementation details.** HDE should depend on a product-runtime contract, not tab IDs, Native Messaging, `chrome.debugger`, or extension worker structure.
8. **Observed provenance is preserved instead of synthesized.** For example, a missing `finish_reason` must not be rewritten to `stop` merely because other canonical finality evidence exists.
9. **Unsupported, unknown, and unimplemented are different states.** Capability reporting must preserve that distinction.
10. **Legacy research remains recoverable.** Sentinel/direct-write work should be quarantined before it is deleted; historical evidence and diagnostics still have value.
11. **No challenge bypass expansion.** No Turnstile solver, proof-token generator, browser-protection emulation, protective-credential extraction/replay, or reconstructed private product write path.
12. **The current production transport is replaceable.** A future supported/native/desktop transport should be swappable without rewriting HDE or the public runtime contract.

---

## 4. Target Runtime Model

The intended mental model is:

```text
                 ChatGPTProductRuntime
                    /           \
                   /             \
                  v               v
     CanonicalConversation    ProductWriteTransport
           Client                    Protocol
             |                          |
             |                          +-- BrowserOwnedProductTransport
             |                          +-- future supported/native transport
             |                          +-- future desktop transport
             |                          `-- future official product transport
             |
             `-- messages / status / session / attach / readback
```

### Product write transport protocol

The exact Python surface is still a PR8.4 design decision, but the intended contract is approximately:

```python
class ProductWriteTransport(Protocol):
    def health(self, conversation=None) -> TransportHealth: ...
    def send_text(self, text, *, conversation=None, ...) -> ChatResponse: ...
    def capabilities(self) -> TransportCapabilities: ...
    def governance(self) -> TransportGovernance: ...
```

`ChatGPTProductRuntime` should orchestrate this contract rather than depend directly on the concrete browser-owned implementation.

### Canonical plane

The canonical side should have an equally explicit role:

```text
CanonicalConversationClient
├─ attach
├─ messages
├─ status
├─ finality
├─ session/auth refresh
└─ canonical readback
```

This does **not** require an immediate rewrite of all existing `ChatGPTWebClient` internals. PR8.4 should introduce the boundary first and migrate behavior incrementally without changing the proven live path.

---

## 5. Target Package Direction

A possible end-state package layout is:

```text
chatgpt_web_adapter/
├─ product/
│  ├─ runtime.py
│  ├─ transport.py
│  ├─ capabilities.py
│  ├─ provenance.py
│  └─ errors.py
│
├─ canonical/
│  ├─ client.py
│  ├─ conversations.py
│  ├─ messages.py
│  ├─ status.py
│  └─ session.py
│
├─ transports/
│  └─ browser_owned/
│     ├─ transport.py
│     ├─ bridge.py
│     ├─ native_host.py
│     └─ extension/
│
├─ legacy/
│  ├─ sentinel/
│  ├─ prepared_write/
│  └─ direct_web/
│
└─ cli.py
```

This is a direction, not a mandate to perform a large file move in one PR. Physical layout should follow interface stabilization, not precede it.

---

## 6. PR8.4 — Product Transport Protocol, Canonical/Write Plane Interface Separation and Implementation-Independent Runtime Governance

### Outcome

Make `ChatGPTProductRuntime` depend on stable interfaces rather than concrete browser-owned implementation details.

### Planned work

- define `ProductWriteTransport` as the production write abstraction;
- introduce a canonical conversation/session interface for read/status/finality operations;
- wrap the existing `BrowserOwnedProductWriteRuntime` as the first concrete production transport rather than reimplementing it;
- allow explicit transport injection into `ChatGPTProductRuntime`;
- keep `browser-owned` as the only production transport until another is independently proven;
- preserve public `send()` / `send_text()` behavior;
- preserve explicit transport selection and fail-closed unknown transport handling;
- keep legacy `ChatGPTWebClient.send()` behavior compatible rather than silently redirecting it;
- prevent transport implementations from owning canonical lifecycle policy they do not need;
- define ownership of preflight, commit-point readiness, delegated-write ambiguity, and canonical readback.

### Non-goals

- no new browser mechanism;
- no extension rewrite;
- no new hidden/non-tab experiment;
- no Sentinel removal;
- no multi-provider abstraction;
- no performance/stress optimization.

### Exit gates

- existing PR8.3 live behavior remains possible without caller changes;
- `ChatGPTProductRuntime` can be tested against a protocol-conforming fake transport;
- HDE-facing code has no requirement to import browser-native implementation modules;
- no fallback transport is introduced;
- canonical completion remains required for successful product responses;
- ambiguous delegated writes remain non-retryable automatically;
- full regression suite remains green.

---

## 7. PR8.5 — Product Capability Model, Transport Feature Declaration and Provenance-Aware Response Governance

### Outcome

Make product/runtime capabilities explicit and machine-readable, and make response provenance rich enough that HDE does not have to infer semantics from nullable backend fields.

### Capability-state model

The capability layer must distinguish at least:

- **AVAILABLE** — implemented and evidence-backed on this transport;
- **UNSUPPORTED** — known not to be provided by the transport/product contract;
- **UNKNOWN** — not sufficiently characterized yet;
- **UNIMPLEMENTED** — believed possible or product-present, but not implemented by this runtime.

Do not collapse these into a boolean.

### Initial capability candidates

- text turns;
- new chat;
- continuation;
- canonical readback;
- conversation attach/read/status;
- streaming;
- images;
- files;
- web search;
- temporary chat;
- model selection/preservation;
- reasoning selection/preservation;
- product-owned memory/personalization semantics;
- tools/connectors;
- approvals;
- conversation branching;
- multimodal continuation.

Example direction:

```json
{
  "text_turns": "AVAILABLE",
  "new_chat": "AVAILABLE",
  "continuation": "AVAILABLE",
  "canonical_readback": "AVAILABLE",
  "images": "UNIMPLEMENTED",
  "files": "UNKNOWN",
  "web_search": "UNKNOWN",
  "temporary_chat": "UNKNOWN",
  "memory_semantics": "PRODUCT_OWNED"
}
```

Exact names should be frozen in PR8.5 tests before broad public use.

### Provenance model

Responses/executions should be able to expose structured evidence such as:

```text
transport                 browser-owned
product_semantics          ordinary-chatgpt
write_plane                browser-native-page-owned
readback_plane             browserless-canonical-http
finality_source            canonical-message-status / finish-reason / end-turn / ...
finish_reason              observed nullable value
runtime_tab                reused / created / unknown
foreground_activation      false / true / unknown
observed_model             optional observed value
conversation_id            canonical identity
message_id                 canonical identity
```

A missing `finish_reason` is valid metadata when completion was proven by another canonical finality signal. The runtime must never invent a synthetic stop reason merely for API neatness.

### HDE value

This lets HDE ask:

```text
Can this runtime perform the requested action?
What exactly completed?
Which plane supplied the evidence?
Was the browser runtime reused?
Is a feature unsupported, unknown, or merely not implemented yet?
```

without learning Chrome internals.

---

## 8. PR8.6 — Legacy Direct-Write / Sentinel Isolation, Public Surface Reclassification and Compatibility Boundary

### Outcome

Make the primary production architecture obvious without destroying the research history that enabled it.

### Planned work

- classify the PR8.3+ product runtime as the primary forward-looking production surface;
- quarantine Sentinel/prepared/direct-write machinery under an explicit legacy/research boundary where practical;
- preserve compatibility re-exports where removing them would be unnecessarily disruptive;
- separate public SDK examples from research/PR diagnostic probes;
- update README positioning to describe the production browser-owned runtime and link this roadmap;
- update architecture/usage docs so users can tell which path is current, legacy, experimental, or diagnostic;
- document compatibility guarantees for `ChatGPTWebClient` versus `ChatGPTProductRuntime`;
- decide which legacy symbols should be deprecated, retained indefinitely, or remain research-only;
- keep old research artifacts available for regression diagnosis and future contract comparison.

### Important non-goal

Do **not** delete Sentinel/direct-write code merely to make the tree look cleaner. Isolation comes before deletion. A later removal decision should be evidence-based and migration-aware.

---

## 9. HDE Integration Contract

HDE should ultimately see a narrow product-runtime interface such as:

```python
runtime.health(...)
runtime.capabilities()
runtime.send(...)
runtime.get_status(...)
runtime.get_messages(...)
runtime.attach_conversation(...)
```

HDE should **not** need to know:

- Chrome tab IDs;
- extension worker names;
- Native Messaging host details;
- `chrome.debugger` targets;
- Sentinel internals;
- whether the implementation is Python-centered, daemon-centered, or extension-centered.

This boundary is strategically important: it allows the transport implementation to change without forcing HDE session, memory, identity, or companion layers to change with it.

---

## 10. PR9.0 — Next-Generation Product Bridge Architecture Feasibility

After PR8.4–PR8.6 establish clean contracts, compare fundamentally different runtime ownership models **before** committing to a v2 implementation.

PR9.0 is a feasibility/architecture decision PR, not a rewrite PR.

### Candidate A — Current Python-Centered Runtime

```text
Python / HDE
  -> canonical HTTP
  -> Native Messaging
  -> extension
  -> reusable ChatGPT tab
```

Strengths:

- already proven;
- simplest migration path;
- excellent reuse of current code;
- browserless canonical plane is efficient.

Questions:

- is Python the right long-term lifecycle owner?
- does Python ownership make non-Python consumers unnecessarily dependent on the SDK implementation?

### Candidate B — Extension-First Product Bridge

Treat the extension as the primary owner of browser authority and product-page state.

Potential responsibilities:

```text
Extension
├─ runtime-tab state
├─ product-page readiness
├─ page-owned send lifecycle
├─ safe write observations
├─ browser reconnect/reconciliation
├─ model/page capability observations
└─ browser-local product state
```

The native side would remain responsible for canonical/session operations that are better outside the browser.

This is attractive because the privileged product environment already lives in Chrome. Browser facts should preferentially be owned by the browser component rather than reconstructed by Python.

### Candidate C — Native Daemon + Extension

Move the center of gravity from the Python package to a local product bridge process:

```text
               local product bridge
                 /             \
                /               \
      canonical/session        extension
            plane             write plane
                \               /
                 \             /
             ordinary ChatGPT product
```

Possible form:

```text
chatgpt-product-bridge.exe
```

The Python package becomes a thin client rather than the runtime owner.

Potential local transports:

- Windows named pipe, e.g. `\\.\pipe\chatgpt-product-bridge`;
- Unix-domain socket on Unix-like systems;
- localhost HTTP only if interoperability needs justify the larger exposed surface.

Possible protocol operations:

```text
health
capabilities
send
status
messages
attach
```

Benefits to evaluate:

- language-independent access for HDE and other tools;
- clearer process/failure isolation;
- one product runtime shared by multiple local clients;
- cleaner browser/native ownership boundary.

Costs to evaluate:

- installation and lifecycle complexity;
- daemon discovery and versioning;
- IPC authentication/permission model;
- additional packaging and cross-platform work.

The daemon should initially be a normal user-space local process unless evidence shows a background OS service is actually needed.

### Candidate D — Full Extension-Owned Canonical Lifecycle

Investigate whether reads/status/session should also move into the authenticated browser context.

This is **not** currently preferred because browserless canonical reads are a strong property:

- low overhead;
- no UI dependence;
- independent canonical observation;
- simpler read/status tooling.

Move canonical lifecycle into the extension only if it solves a concrete problem that outweighs those benefits.

### Candidate E — Direct CDP Without Extension

Potential shape:

```text
external runtime
   -> CDP
   -> existing Chrome
```

This may reduce extension/Native Messaging components, but it risks weakening the ownership model by making an external process directly responsible for browser automation and browser lifecycle.

Treat this as a comparison candidate, not a presumed simplification.

### Candidate F — Newly Supported Product Surface

If Chrome or OpenAI introduces a documented supported surface that changes the PR8.2.5 boundary, reopen the non-tab/native feasibility question.

Examples could include a future supported product bridge, local client contract, desktop IPC, or browser execution surface that genuinely preserves the required product semantics.

Do not assume such a surface exists until independently verified.

---

## 11. PR9.0 Comparison Criteria

Every candidate should be compared against the same dimensions:

- ordinary-product semantic fidelity;
- browser ownership clarity;
- canonical-read independence;
- public API stability;
- HDE integration complexity;
- latency and per-turn overhead;
- process/failure isolation;
- language independence;
- installation complexity;
- upgrade/version-skew complexity;
- security boundary;
- local IPC exposure;
- session continuity;
- runtime-tab/browser continuity;
- foreground-stealing risk;
- duplicate-write / unknown-outcome risk;
- observability and provenance quality;
- maintainability;
- testability;
- cross-platform portability;
- migration cost from the proven PR8.3 baseline.

PR9.0 should end with a written verdict, not merely a prototype collection.

---

## 12. Possible Post-PR9 Direction

Two broad outcomes are intentionally kept open.

### Path 1 — Evolve the Current Architecture

If the current Python-centered model remains the best tradeoff:

```text
ChatGPTProductRuntime
  -> stable transport protocol
  -> BrowserOwnedProductTransport
  -> extension
```

Continue improving it without a disruptive v2 rewrite.

### Path 2 — Build a Next-Generation Product Bridge

If daemon-centered or extension-first ownership is clearly superior:

```text
HDE / Python SDK / CLI / other local tools
               |
               v
      local ChatGPT product bridge
          /              \
 canonical plane       browser plane
          \              /
           ordinary ChatGPT
```

In that case, the current library can become a compatibility client for the new bridge rather than being discarded.

---

## 13. Multi-Provider Generalization Is Deliberately Deferred

A future abstraction could eventually look like:

```text
ProductRuntime
├─ ChatGPTProductRuntime
├─ ClaudeProductRuntime
├─ GeminiProductRuntime
└─ LocalModelRuntime
```

Do **not** build this abstraction yet.

One backend is not enough evidence to know which concepts are truly portable. Premature multi-provider design risks creating a lowest-common-denominator API based on ChatGPT-specific assumptions disguised as generic concepts.

Revisit only after there is a concrete second product/runtime implementation and enough evidence to distinguish universal contracts from provider-specific behavior.

---

## 14. Stress / Daily-Use Validation — Deferred, Not Cancelled

Stress testing should resume after the architecture intended for daily use is stable.

Future stress gates should include:

- repeated production-runtime continuation turns;
- new-chat + continuation mixes;
- runtime reconstruction between groups of turns;
- process restart/reassembly;
- stable runtime-tab identity when appropriate;
- no duplicate runtime tabs;
- no duplicate product turns;
- no observed foreground activation;
- canonical completion/readback on every successful turn;
- browserless session renewal during longer runs;
- explicit reconciliation for ambiguous outcomes;
- no automatic fallback to legacy write paths;
- capability/provenance consistency across the run.

Stress should validate the **post-abstraction architecture**, not freeze the pre-abstraction implementation by making endurance work the next development center of gravity.

---

## 15. Security and Product-Boundary Governance

All future architecture work remains subject to these boundaries:

- no Turnstile solving or bypass;
- no proof-token synthesis;
- no browser-fingerprint emulation;
- no extraction/replay of protective browser credentials;
- no reconstruction of protected private writes whose operation depends on bypassing product safeguards;
- no silent credential copying between security contexts;
- no claim that embedded/offscreen contexts are equivalent to ordinary top-level ChatGPT without evidence;
- no automatic resend when a delegated write may already have happened.

Preferred direction:

```text
supported/session-safe canonical operations
+ official page-owned browser write
+ explicit provenance
+ fail-closed ambiguity handling
```

---

## 16. Decision Checkpoints

### After PR8.4

Ask:

- Can HDE use the runtime without knowing the concrete write transport?
- Can a new transport be added without changing the HDE-facing contract?
- Are canonical and write ownership boundaries explicit in code and tests?

### After PR8.5

Ask:

- Can callers distinguish available, unsupported, unknown, and unimplemented features?
- Can a response explain how completion was proven without inventing metadata?
- Does HDE receive enough provenance to make safe lifecycle decisions?

### After PR8.6

Ask:

- Is the primary production surface obvious to a new contributor?
- Are legacy/research paths clearly isolated without losing useful evidence?
- Do README, examples, exports, and architecture docs tell the same story?

### After PR9.0

Ask:

- Should the current Python-centered runtime remain the primary architecture?
- Is extension-first ownership materially cleaner?
- Is a local native daemon worth its lifecycle complexity?
- Does any newly supported surface invalidate the current one-tab lower bound?
- Is a v2 product bridge justified by measurable architectural gains?

---

## 17. Planned Order

| Phase | Work | Primary purpose |
| --- | --- | --- |
| Complete | PR8.2.x | Establish browser-owned write/read/session boundaries and one-tab lower bound |
| Complete | PR8.3 | Expose a production `ChatGPTProductRuntime`, explicit provider selection, CLI and lifecycle assembly |
| Next | PR8.4 | Product transport protocol + canonical/write plane separation |
| Next | PR8.5 | Capability states + transport feature declaration + provenance model |
| Next | PR8.6 | Legacy/Sentinel isolation + public surface/docs compatibility boundary |
| Then | PR9.0 | Compare current, extension-first, native-daemon, extension-canonical, direct-CDP and newly supported architectures |
| Decision | Post-PR9 | Evolve current runtime or begin a justified next-generation product bridge |
| Later | Stress | Validate the chosen architecture under repeated/daily-use conditions |
| Deferred | Multi-provider runtime | Generalize only after a real second provider supplies evidence |

---

## 18. North Star

The long-term objective is not merely "send a ChatGPT message from Python".

The objective is a small, explicit, local product-runtime boundary that lets higher-level systems such as HDE use ordinary ChatGPT product capabilities without coupling themselves to browser implementation details.

The ideal result is:

```text
HDE / CLI / SDK / local tools
          |
          v
stable product-runtime contract
          |
          +-- canonical observation
          +-- explicit capabilities
          +-- provenance-aware completion
          +-- replaceable product write transport
          |
          v
ordinary ChatGPT product semantics
```

The current browser-owned runtime is the first proven transport behind that contract, not the definition of the contract itself.
