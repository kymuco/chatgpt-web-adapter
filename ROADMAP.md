# chatgpt-web-adapter Roadmap

_Last updated: 2026-08-15_

This roadmap defines the canonical architectural direction for `chatgpt-web-adapter` after the PR8 browser-owned transport, production-runtime, capability/provenance, and public-surface work.

The detailed daily-use architecture review is recorded in:

- [`docs/post_pr8_daily_use_product_bridge_direction.md`](docs/post_pr8_daily_use_product_bridge_direction.md)

That document is the source of detail for Temporary Chat, browser-authority lifetime, revision-safe streaming, model selection, resource/debugger work, and HDE research automation boundaries. This roadmap keeps the repository-level sequence and invariants concise enough to remain navigable.

The strategic goal is no longer merely to prove that ordinary ChatGPT product turns can be sent from Python.

The goal is to evolve the proven transport into a **fast, capability-aware, low-overhead local ChatGPT product bridge** whose browser implementation remains replaceable and whose public contract is suitable for HDE and other local tools.

---

## 1. Current Proven Baseline

The PR8 series established a working ordinary-ChatGPT product transport with the following shape:

```text
HDE / terminal / Python caller
        |
        v
ChatGPTProductRuntime
        |
        +-- READ / STATUS / SESSION
        |      -> browserless canonical HTTP
        |
        `-- WRITE
               -> ProductWriteTransport
               -> BrowserOwnedProductTransport
               -> Native Messaging
               -> Chrome extension
               -> ordinary ChatGPT page-owned product write
               -> browserless canonical readback/finality
```

### Proven properties

The current green PR8.6 baseline has evidence for:

- ordinary ChatGPT product semantics rather than a separate API product;
- explicit browser-owned write delegation;
- browserless canonical conversation reads, status, and session lifecycle;
- new-chat creation;
- existing-conversation continuation;
- canonical response readback;
- exact conversation/message identity recovery for ordinary durable chats;
- on-demand runtime-tab creation when absent;
- stale stored-tab reconciliation;
- same-tab reuse across turns;
- successful warm inactive-tab reuse;
- a cold/no-tab path where foreground activation was observed even though the runtime did not request it;
- no automatic retry after an ambiguous delegated write;
- no legacy/direct-write fallback from the production runtime;
- explicit closed-set `browser-owned` transport selection through `ChatGPTProductRuntime`;
- a stable canonical/write interface split;
- capability states that distinguish `AVAILABLE`, `UNSUPPORTED`, `UNKNOWN`, and `UNIMPLEMENTED`;
- structured product execution provenance;
- nullable `finish_reason` without synthetic `stop` fabrication;
- public-surface classification separating production, shared support, compatibility, experimental, and research/diagnostic APIs;
- a green repository-wide regression suite after PR8.6 (`826 passed`, `0 failed` in the validating Windows checkout).

### Important foreground-activation correction

The correct invariant is:

```text
runtime_tab_foreground_activation_requested = false
```

not:

```text
foreground activation can never happen
```

A warm path has been observed to stay inactive, while a cold/no-tab creation path has also been observed to foreground the newly created tab.

Future lifecycle/resource work must measure both:

```text
cold-start foreground-disturbance risk
warm-reuse foreground-disturbance risk
```

rather than encoding “never foregrounds” as a false guarantee.

### PR8.2.5 non-tab boundary

The supported Chrome surfaces reviewed in PR8.2.5 did **not** reveal a qualifying supported hidden/non-tab runtime that simultaneously preserves ordinary top-level ChatGPT product semantics.

The current minimum proven write substrate therefore remains an ordinary ChatGPT page runtime owned by Chrome/extension machinery.

This is a reopenable evidence boundary, not a metaphysical impossibility claim. Reopen it if a newly documented Chrome or OpenAI-supported surface materially changes the architecture.

---

## 2. Current Product-Runtime Contract

The intended public mental model after PR8.4–PR8.6 is:

```text
                 ChatGPTProductRuntime
                    /           \
                   /             \
                  v               v
     CanonicalConversation    ProductWriteTransport
           Client                    Protocol
             |                          |
             |                          `-- BrowserOwnedProductTransport
             |                                  |
             |                                  `-- current page-owned writer
             |
             `-- messages / status / session / attach / readback
```

HDE should use the product-runtime contract rather than browser implementation details.

Current HDE-facing primitives include:

```python
runtime.health(...)
runtime.capabilities()
runtime.send(...)
runtime.send_text_observed(...)
runtime.get_status(...)
runtime.get_messages(...)
runtime.attach_conversation(...)
runtime.governance()
```

HDE should **not** need to know:

- Chrome tab IDs;
- extension worker names;
- Native Messaging host details;
- `chrome.debugger` target IDs;
- Sentinel internals;
- concrete browser-owned writer classes;
- whether a future implementation becomes Python-centered, daemon-centered, or extension-centered.

---

## 3. Architectural Invariants

Future PRs must preserve these invariants unless later evidence explicitly supersedes one.

1. **Ordinary product semantics are first-class.** Do not silently substitute another product/API surface while calling it equivalent.
2. **Canonical observation and product mutation are separate planes.** Read/status/session logic must not be coupled to one particular write mechanism.
3. **Transport selection is explicit.** No silent `browser-owned -> legacy direct write` fallback.
4. **Ambiguous writes are never automatically retried.** Reconciliation precedes any retry decision.
5. **Authoritative completion evidence is preserved.** Page submission alone is not enough to claim a completed product turn.
6. **Incremental text observation is not canonical finality.** Partial text may be shown early without claiming completion.
7. **Browser Authority Lease is not Turn Lifecycle Lease.** The logical turn may remain active after browser authority becomes unnecessary, if live evidence proves early release safe.
8. **Browser authority stays browser-local where possible.** Browser state and page interaction should not be reconstructed externally without need.
9. **HDE must not depend on browser implementation details.** It depends on the product-runtime contract.
10. **Observed provenance is preserved instead of synthesized.** Missing metadata remains missing when other evidence proves completion.
11. **Capability states remain distinct.** `UNSUPPORTED`, `UNKNOWN`, and `UNIMPLEMENTED` must not collapse into false/true.
12. **Parameterized capabilities may add structured details without discarding the four-state model.**
13. **Explicit product-mode selection is fail-closed unless the caller explicitly opts into best-effort fallback.**
14. **Conversation/product mode must not leak silently across independent turns.** Sticky UI state requires explicit characterization and isolation.
15. **Legacy research remains recoverable.** Sentinel/direct-write work is isolated before deletion.
16. **No challenge-bypass expansion.** No Turnstile solving, proof-token generation, browser-protection emulation, protective-credential extraction/replay, or reconstructed protected private writes.
17. **The current production transport is replaceable.** Future supported/native/desktop transports should be swappable without rewriting HDE.
18. **Architecture work is evidence-labelled.** Distinguish `PROVEN`, `TARGET`, `HYPOTHESIS`, `DECISION`, and `DECISION_PENDING` when the distinction matters.

---

## 4. Completed Foundation — PR8.3 through PR8.6

### PR8.3 — Production Browser-Owned ChatGPT Transport Integration

Status: **COMPLETE / LIVE-VALIDATED**

Established:

- `ChatGPTProductRuntime`;
- production `browser-owned` transport selection;
- CLI `runtime status` / `runtime send`;
- browserless canonical/session plane plus page-owned write plane;
- no legacy direct-write fallback;
- canonical readback requirement;
- no automatic ambiguous-write retry.

### PR8.4 — Product Transport Protocol and Canonical/Write Plane Separation

Status: **COMPLETE / REGRESSION-CLEAN**

Established:

- `ProductWriteTransport`;
- `CanonicalConversationClient`;
- implementation-independent `ChatGPTProductRuntime` dispatch;
- `BrowserOwnedProductTransport` as the first concrete production transport;
- explicit transport identity validation;
- HDE-facing decoupling from the concrete browser writer.

### PR8.5 — Product Capability Model and Provenance-Aware Response Governance

Status: **COMPLETE / LIVE-VALIDATED**

Established:

- four-state capability model;
- machine-readable browser-owned feature declaration;
- product execution/completion/identity provenance;
- canonical completion independent of nullable `finish_reason`;
- no synthetic `stop`;
- live capability/provenance compatibility gate.

### PR8.6 — Legacy/Sentinel Isolation and Public Surface Reclassification

Status: **COMPLETE / FULL SUITE GREEN**

Established:

```text
PRIMARY_PRODUCTION
SHARED_SUPPORT
COMPATIBILITY
EXPERIMENTAL
RESEARCH_DIAGNOSTIC
```

with:

- `ChatGPTProductRuntime` as the forward-looking production surface;
- `ChatGPTWebClient` retained as compatibility rather than silently redirected/deprecated;
- Sentinel/direct browser-native surfaces classified as research/diagnostic;
- README/examples/architecture repositioned around the product runtime;
- no transport/runtime behavior rewrite.

---

## 5. Daily-Use Phase — Why PR8.7 through PR8.11 Exist

The next phase is not about proving that the transport works at all.

It is about making the proven product-runtime boundary suitable for actual HDE daily use.

The target experience is:

```text
request
   |
   v
create/reuse minimal browser authority
   |
   v
page-owned write
   |
   +--> useful text appears quickly
   |
   +--> browser authority released as soon as evidence permits
   |
   v
authoritative finality/reconciliation
```

For internal HDE calls:

```text
Temporary product mode
+ FAST semantic model intent
+ revision-safe streaming
+ TURN_SCOPED browser authority
```

should eventually provide a low-latency, non-cluttering inference primitive while HDE retains ownership of its reviewed context/memory policy.

The detailed reviewed design is in [`docs/post_pr8_daily_use_product_bridge_direction.md`](docs/post_pr8_daily_use_product_bridge_direction.md).

---

## 6. PR8.7 — Temporary Chat Product Semantics, Ephemeral Identity / Persistence Characterization and Fail-Closed Conversation-Mode Governance

### Goal

Make Temporary Chat a proven product-runtime capability suitable for ephemeral HDE calls without assuming durable-conversation identity/readback semantics.

### Required characterization

At minimum:

```text
Temporary mode selection proven before write
successful text turn
no normal/durable fallback on selection failure
history/persistence behavior
conversation/turn identity behavior
get_messages/get_status/attach behavior or explicit absence
terminal/finality source
cold/no-tab path
warm/reused-tab path
TEMP -> NORMAL isolation
NORMAL -> TEMP isolation
runtime-tab recreation behavior
continuation semantics if any
```

### Primary API direction

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

A convenience `send_temporary()` may later delegate to the same mode contract.

### Core invariant

```text
TEMPORARY requested
    -> Temporary product mode proven before write
or
    -> fail before write
```

No accidental durable conversation creation.

### Capability rule

`temporary_chat` moves from `UNKNOWN` to `AVAILABLE` only after the transition/identity/persistence matrix is live-characterized.

### Architecture Invalidation Check

If Temporary Chat cannot be represented safely through the current product-runtime/canonical boundaries without major special-case coupling, advance PR9.0 rather than forcing durable-chat semantics onto an ephemeral product mode.

---

## 7. PR8.8 — Browser Authority Lease, Turn Lifecycle Separation, Idle-TTL / Turn-Scoped Disposal and Cold/Warm Lifecycle Governance

### Central distinction

```text
Browser Authority Lease != Turn Lifecycle Lease
```

### Turn Lifecycle Lease

Covers the logical turn through authoritative finality/reconciliation.

### Browser Authority Lease

Covers only the time during which the browser page/context remains genuinely required.

If evidence proves the page is required until finality, both leases end together.

If evidence proves generation/canonical observation can continue after page-owned write handoff, browser authority may be released earlier while the logical turn remains active.

### Lifecycle policies

```text
PERSISTENT
IDLE_TTL
TURN_SCOPED
```

Initial PR8.8 compatibility defaults:

```text
PERSISTENT = default
IDLE_TTL = opt-in
TURN_SCOPED = opt-in
```

Do not change the default until lifecycle/resource evidence justifies it.

### TTL precedence

```text
per-turn explicit override
        ↓
runtime assembly default
        ↓
transport implementation default
```

### TTL rule

TTL begins after **Browser Authority Lease release**, never merely after submit.

`ttl=0` is permitted for any explicit `TURN_SCOPED` path whose authority-release point is proven safe; it is not Temporary-only.

### Disposal decision

```text
CLOSE   = production v1
DISCARD = benchmark/characterization candidate
```

### Minimum PR8.8 resource evidence

```text
cold-start latency
warm-reuse latency
idle CPU
idle memory
close -> next-turn latency
foreground disturbance
Browser Authority Lease duration
```

### Core invariant

```text
no tab disposal while browser authority is still required
```

### Architecture Invalidation Check

If browser authority cannot meaningfully separate from the full logical turn lifecycle, record that as a hard PR9.0 boundary rather than hiding it behind timer policy.

---

## 8. PR8.9 — Incremental Text Observation, Revision-Safe Streaming, First-Delta Latency and Canonical-Finality Reconciliation

### Goal

Surface useful response text as soon as safely observable rather than blocking on the current final-message polling loop.

### Central distinction

```text
Incremental Text Observation != Canonical Finality
```

### Primary abstraction

Do not promise model-token boundaries unless the source actually exposes them.

Prefer revision-safe text observations such as:

```text
AssistantTextSnapshot
AssistantTextDelta
AssistantTextRevision
CanonicalTextFinalized
```

`on_token` may remain as compatibility/helper behavior where an append-only channel is proven.

### Streaming source order

```text
1. incremental canonical observation
2. safe browser response observation
3. rendered-page observation
```

Start with a focused live question:

> Does the canonical read surface expose useful partial assistant content during generation?

If clearly no, move to the next source rather than forcing the canonical path.

### Reconciliation states

A useful final stream/canonical relationship may include:

```text
EXACT_MATCH
CANONICAL_EXTENDS_STREAM
STREAM_REVISED_BY_CANONICAL
STREAM_INCOMPLETE
UNAVAILABLE
```

### Metrics

At minimum:

```text
TTFW
TTFT
stream_duration
finality_lag
return_lag
browser_authority_release_lag
```

### Core invariant

```text
partial text may be shown early
completion is not claimed until authoritative terminal semantics are proven
no automatic resend after partial-stream failure
```

### Architecture Invalidation Check

If useful low-latency streaming fundamentally requires a browser-ownership model incompatible with the current runtime seams, advance PR9.0 before building further features on an invalid boundary.

---

## 9. PR8.10 — Product Model / Reasoning Selection, Semantic Model Profiles, State-Scope Isolation and Selection Provenance

### Goal

Let HDE deliberately choose low-latency versus deep-reasoning product behavior.

### HDE-facing semantic intent

```text
FAST
BALANCED
DEEP
MAX
```

Semantic profiles belong at the `ChatGPTProductRuntime` layer.

The transport exposes/applies product-specific selectors and returns observed selection evidence.

### Exact selector

An advanced exact product-model/mode selector may exist, but semantic intent should remain the stable HDE-facing abstraction.

### Explicit selection is strict by default

```text
no explicit intent
    -> inherited/default behavior may be allowed

explicit model_profile/model_exact
    -> select/prove before write
       or fail before write
```

Best-effort fallback requires explicit caller opt-in and provenance must record the fallback.

### Required scope characterization

Determine whether selection mutates:

```text
turn
conversation
runtime tab
future new chats
account/product default
other manually open ChatGPT tabs
```

Transition tests must detect sticky-state leakage.

### Structured capability details

Keep the PR8.5 four-state model, but allow parameterized capabilities to expose structured details when needed.

### Core invariant

```text
requested model intent is never silently represented as honored when evidence says otherwise
```

### Architecture Invalidation Check

If reliable model/reasoning control requires fundamentally different page authority, carry that evidence to PR9.0 rather than hiding the limitation.

---

## 10. PR8.11 — Browser Authority Cost Reduction, Debugger Attachment Minimization and Deep Resource Baseline

### Goal

Reduce browser overhead and visible browser authority without weakening product semantics.

### Debugger policy

Do **not** attempt to conceal or bypass Chrome security UX while still using debugger authority.

Correct sequence:

```text
measure current debugger attachment lifetime
        ↓
shorten attachment window where safe
        ↓
live reliability validation
        ↓
independently investigate debugger-free/lower-authority path
```

Possible lower-authority experiments include content scripts / `chrome.scripting`, but they must independently prove product-semantic equivalence.

### Deep resource baseline

Build on PR8.8 minimum lifecycle measurements and add:

```text
cold boot CPU time
network bytes/request count
JS heap if available
DOM node count if useful
GPU/compositor activity if measurable
per-turn CPU/network cost
navigation/reload cost
debugger attach lifetime
resource-class contribution
```

Resource blocking/removal should be performed one class at a time and must not approximate or break product semantics.

### Architecture Invalidation Check

If a clearly superior lower-authority mechanism requires a larger ownership rewrite, defer that rewrite and carry evidence into PR9.0.

---

## 11. Architecture Invalidation Check

Normal sequencing is:

```text
PR8.7 -> PR8.8 -> PR8.9 -> PR8.10 -> PR8.11 -> PR9.0
```

But every PR8.7–PR8.11 must explicitly ask:

```text
Did this PR reveal that the current product-runtime boundary cannot safely express the feature?
Did it reveal unavoidable browser coupling that invalidates the current ownership model?
Would a next-generation bridge materially change the implementation we are about to build next?
```

If yes:

```text
FUNDAMENTAL_BOUNDARY_DISCOVERED
        |
        v
advance PR9.0
```

Do not mechanically finish the entire PR8.7–PR8.11 sequence on top of an architecture that evidence has already invalidated.

---

## 12. HDE Integration During the Daily-Use Phase

Do not wait for PR9.0 to begin HDE integration.

HDE can use the current PR8.6 product runtime for ordinary text turns now, with capability checks around optional features.

Conceptual HDE call classes may become:

### User-visible durable conversation

```text
mode: durable
model: FAST/BALANCED by default when model control becomes AVAILABLE
streaming: yes when AVAILABLE
browser policy: moderate idle TTL after lifecycle evidence
```

### Internal short inference

```text
mode: temporary when AVAILABLE
model: FAST when AVAILABLE
streaming: optional/preferred
browser policy: TURN_SCOPED, ttl=0 when authority release is proven safe
```

### Deep research step

```text
mode: durable research conversation
model: DEEP/MAX when AVAILABLE
streaming: yes
browser policy: long enough to preserve warm active research session
```

### Planner/evaluator call

```text
mode: temporary
model: FAST
browser policy: TURN_SCOPED
```

HDE must continue to use `runtime.capabilities()` rather than importing browser-native internals to gain these features.

---

## 13. Research Automation Boundary

`chatgpt-web-adapter` should expose product/runtime primitives:

```text
send
revision-safe text observation
status/messages/attach
Temporary Chat
model/reasoning selection
Browser Authority Lease / TTL
completion/finality events
provenance
reconciliation
```

HDE should own cognition/workflow policy:

```text
research goals
next-step generation
planner/evaluator policy
memory/context projection
budget
stop criteria
human-review checkpoints
tool/external-action policy
```

A strong future pattern is:

```text
MAIN DURABLE RESEARCH CHAT
          |
          v
HDE Research Controller
          |
          +--> TEMPORARY FAST evaluator/planner
          |
          v
validated next instruction
          |
          v
MAIN DURABLE RESEARCH CHAT
```

Minimum automation lineage/guards should include:

```text
job_id
step_id
parent_step_id
persistent journal
request fingerprint
max turns/runtime/failures
no-progress budget
duplicate detection
DONE / ABSTAIN / NEEDS_REVIEW states
no resend after ambiguous write
human gate for external effects
```

The planner/evaluator is not automatically “independent evidence” merely because it is a second model turn.

---

## 14. PR9.0 — Next-Generation Product Bridge Architecture Feasibility

PR9.0 remains an architecture-decision PR, not a rewrite PR.

Normal timing is after PR8.11, but the Architecture Invalidation Check may advance it.

### Candidate A — Current Python-Centered Runtime

```text
Python / HDE
  -> canonical HTTP
  -> Native Messaging
  -> extension
  -> ordinary ChatGPT runtime tab
```

### Candidate B — Optimized Lightweight Inactive-Tab Runtime

Evolve the current architecture with:

- bounded Browser Authority Lease;
- TTL/turn-scoped lifetime;
- revision-safe streaming;
- minimized debugger lifetime;
- reduced page-resource cost where proven safe.

### Candidate C — Extension-First Product Bridge

Treat the extension as the primary owner of browser authority and product-page state, while preserving an efficient canonical/session plane outside the browser when advantageous.

### Candidate D — Native Daemon + Extension

Potential shape:

```text
               local product bridge
                 /             \
                /               \
      canonical/session        extension
            plane             browser plane
                \               /
                 \             /
             ordinary ChatGPT product
```

The Python package could become a thin client to a language-independent local bridge.

### Candidate E — Extension Offscreen / Embedded Experiments

Only consider these if live evidence proves they preserve the required product semantics. Do not equate hidden/embedded contexts with an ordinary top-level product runtime without evidence.

### Candidate F — Direct CDP / External Browser Control

Compare as an architecture candidate, not as presumed simplification. External CDP may reduce extension components while worsening browser lifecycle/security ownership.

### Candidate G — Newly Supported Product Surface

If Chrome or OpenAI introduces a documented supported product/local execution surface that changes the PR8.2.5 boundary, reopen the lower-bound analysis.

---

## 15. PR9.0 Comparison Criteria

Every candidate should be compared against the same dimensions:

- ordinary-product semantic fidelity;
- browser ownership clarity;
- Turn Lifecycle / Browser Authority separation;
- canonical-read independence;
- public API stability;
- HDE integration complexity;
- first-text latency;
- canonical finality lag;
- browser-authority release lag;
- cold-start latency;
- idle CPU/RAM;
- network/page-init cost;
- foreground-disturbance risk;
- Temporary Chat fidelity;
- streaming/revision fidelity;
- model/reasoning control fidelity;
- failure/process isolation;
- language independence;
- installation complexity;
- upgrade/version-skew complexity;
- security boundary;
- local IPC exposure;
- session continuity;
- duplicate-write / unknown-outcome risk;
- observability/reconciliation quality;
- maintainability;
- testability;
- cross-platform portability;
- migration cost from the proven PR8 baseline.

PR9.0 should end with an explicit written verdict, for example:

```text
DECISION: EVOLVE_CURRENT_ARCHITECTURE
```

or:

```text
DECISION: PROTOTYPE_NATIVE_DAEMON_BRIDGE
```

with measurable reasons.

---

## 16. Possible Post-PR9 Direction

Two broad outcomes remain open.

### Path 1 — Evolve the Current Architecture

If the current model remains the best tradeoff:

```text
ChatGPTProductRuntime
  -> stable transport protocol
  -> optimized BrowserOwnedProductTransport
  -> bounded browser authority
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

The current Python library can become a compatibility/client layer rather than being discarded.

---

## 17. Multi-Provider Generalization Is Deliberately Deferred

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

## 18. Stress / Daily-Use Validation — Deferred, Not Cancelled

Stress testing should resume after the architecture intended for daily use is stable enough that endurance evidence will validate the design we intend to keep.

Future stress gates should include:

- repeated production-runtime continuation turns;
- new-chat + continuation mixes;
- Temporary/durable mode transitions once Temporary becomes AVAILABLE;
- model-profile transitions once model control becomes AVAILABLE;
- runtime reconstruction between groups of turns;
- process restart/reassembly;
- no duplicate runtime tabs beyond policy;
- no duplicate product turns;
- measured foreground-disturbance rate rather than a false “never foregrounds” assumption;
- authoritative completion/readback on every successful turn;
- browserless session renewal during longer runs;
- explicit reconciliation for ambiguous outcomes;
- no automatic fallback to legacy write paths;
- capability/provenance consistency across the run;
- Browser Authority Lease / TTL correctness;
- revision-safe stream/canonical reconciliation when streaming becomes AVAILABLE.

Stress should validate the **post-daily-use architecture**, not freeze the earlier implementation merely by making endurance work the next center of gravity.

---

## 19. Security and Product-Boundary Governance

All future architecture work remains subject to these boundaries:

- no Turnstile solving or bypass;
- no proof-token synthesis;
- no browser-fingerprint emulation;
- no extraction/replay of protective browser credentials;
- no reconstruction of protected private writes whose operation depends on bypassing product safeguards;
- no silent credential copying between security contexts;
- no attempt to conceal browser security UI while continuing to use the authority that triggers it;
- no claim that embedded/offscreen contexts are equivalent to ordinary top-level ChatGPT without evidence;
- no automatic resend when a delegated write may already have happened.

Preferred direction:

```text
supported/session-safe canonical operations
+ page-owned browser product write
+ explicit capability/provenance evidence
+ bounded browser authority
+ fail-closed ambiguity handling
```

---

## 20. Decision Checkpoints

### PR8.4 — COMPLETE

Confirmed:

- HDE can depend on the runtime without importing the concrete writer;
- transport and canonical boundaries are explicit;
- a future transport can fit behind the protocol.

### PR8.5 — COMPLETE

Confirmed:

- capability states distinguish available/unsupported/unknown/unimplemented;
- completion provenance does not invent nullable metadata;
- HDE receives structured execution provenance.

### PR8.6 — COMPLETE

Confirmed:

- the primary production surface is obvious;
- compatibility/research surfaces remain recoverable;
- README/examples/exports/architecture tell a consistent product-runtime-first story;
- full regression suite is green.

### After PR8.7

Ask:

- Are Temporary identity/persistence/finality semantics understood?
- Can explicit Temporary requests fail closed before write?
- Is TEMP↔NORMAL state isolation proven?
- Did the work invalidate the current canonical/product boundary?

### After PR8.8

Ask:

- Are Turn Lifecycle and Browser Authority lifetimes separately observable?
- Can browser authority be safely released before canonical finality?
- What cold/warm/resource tradeoff does TTL actually produce?
- Did lifecycle evidence invalidate the current architecture?

### After PR8.9

Ask:

- Can useful text be surfaced materially earlier than finality?
- Is the stream revision-safe and reconciled with authoritative final state?
- What source owns low-latency observation?
- Does streaming require a different browser ownership architecture?

### After PR8.10

Ask:

- Can HDE request FAST/DEEP intent without sticky state leakage?
- Is selection scope understood?
- Is explicit selection fail-closed and provenance-backed?

### After PR8.11

Ask:

- What is the measured browser cost?
- Can debugger attachment be materially shortened or removed?
- Is a lower-authority browser path actually superior?

### After PR9.0

Ask:

- Should the current Python-centered runtime remain primary?
- Is extension-first ownership materially cleaner?
- Is a local native daemon worth its lifecycle complexity?
- Does any newly supported surface invalidate the current page-runtime lower bound?
- Is a v2 product bridge justified by measurable gains?

---

## 21. Planned Order

| Phase | Work | Primary purpose |
| --- | --- | --- |
| Complete | PR8.2.x | Establish browser-owned write/read/session boundaries and non-tab feasibility boundary |
| Complete | PR8.3 | Production `ChatGPTProductRuntime`, closed transport selection, CLI, live new/continuation turns |
| Complete | PR8.4 | Product transport protocol + canonical/write plane separation |
| Complete | PR8.5 | Capability states + feature declaration + execution provenance |
| Complete | PR8.6 | Legacy/Sentinel isolation + public-surface/docs compatibility boundary |
| Next | PR8.7 | Temporary Chat semantics + ephemeral identity/persistence characterization |
| Then | PR8.8 | Browser Authority Lease + Turn Lifecycle separation + TTL/disposal |
| Then | PR8.9 | Revision-safe streaming + first-text latency + canonical reconciliation |
| Then | PR8.10 | Semantic model/reasoning selection + state-scope isolation |
| Then | PR8.11 | Browser authority/resource cost + debugger minimization |
| Decision | PR9.0 | Compare current/optimized/extension-first/daemon/offscreen/CDP/supported alternatives |
| Later | Stress | Validate the chosen daily-use architecture under repeated use |
| Deferred | Multi-provider runtime | Generalize only after a real second provider supplies evidence |

Every PR8.7–PR8.11 includes an `ARCHITECTURE_INVALIDATION_CHECK`; PR9.0 may move earlier if a fundamental boundary is discovered.

---

## 22. North Star

The long-term objective is not merely:

> “send a ChatGPT message from Python.”

The objective is a small, explicit, local product-runtime boundary that lets higher-level systems such as HDE use ordinary ChatGPT product capabilities without coupling themselves to browser implementation details.

The ideal result is:

```text
HDE / CLI / SDK / local tools
          |
          v
stable product-runtime contract
          |
          +-- canonical observation
          +-- revision-safe incremental text observation
          +-- explicit capabilities + structured feature details
          +-- provenance-aware completion
          +-- Temporary / durable conversation intent
          +-- semantic model/reasoning intent
          +-- Browser Authority Lease / TTL
          +-- replaceable product write transport
          |
          v
ordinary ChatGPT product semantics
```

The current browser-owned runtime is the first proven authority mechanism behind that contract, not the definition of the contract itself.

Three reviewed distinctions should remain visible throughout the next phase:

```text
Browser Authority Lease != Turn Lifecycle Lease

Incremental Text Observation != Canonical Finality

chatgpt-web-adapter owns product-runtime primitives
HDE owns cognition, research policy, and workflow meaning
```

Those boundaries are the foundation for PR8.7–PR9.0.