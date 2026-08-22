# chatgpt-web-adapter Roadmap

_Last updated: 2026-08-22_

This roadmap defines the canonical post-0.2 direction for `chatgpt-web-adapter` (CWA).

CWA is a standalone SDK / CLI / local ChatGPT product bridge. It is not a support library for any single downstream project. HDE, `codexia-manual-agent` (CMA), terminal users, Python applications and future local tools are all consumers of the same public product-runtime contract.

The detailed historical PR8 daily-use design remains in [`docs/post_pr8_daily_use_product_bridge_direction.md`](docs/post_pr8_daily_use_product_bridge_direction.md). Cross-repository ownership and version coordination with CMA is maintained separately in [`docs/cwa_cma_coordination_roadmap.md`](docs/cwa_cma_coordination_roadmap.md).

---

## 1. Frozen baseline — CWA 0.2.0

CWA 0.2.0 was released on 2026-08-22 and is the frozen baseline for the next generation.

```text
release     v0.2.0
commit      f1ebfd671c45153a3279163dc624e0af7c00e3f9
main == tag at release boundary
```

The 0.2 line establishes the first release-grade product-runtime surface:

- `ChatGPTProductRuntime` as the forward-looking application boundary;
- browser-owned ordinary ChatGPT product writes;
- canonical browserless read/status/finality where supported;
- no hidden fallback to legacy direct writes;
- no automatic retry after ambiguous writes;
- revision-safe streaming and final-only observation;
- product-native model profiles `INSTANT`, `MEDIUM`, `HIGH` plus compatibility aliases `FAST`, `BALANCED`, `DEEP`;
- production Temporary Chat text turns with session-local authority;
- stable `cwa` CLI surfaces for send/status/capabilities/messages/snapshot/export/doctor;
- deterministic conversation artifact manifests;
- release-grade packaging, installed-wheel smoke and cross-platform CI.

The 0.2 release intentionally does **not** graduate the new product-runtime surface for images, general files, multimodal continuation, web search/tools/connectors or a production browserless write transport.

---

## 2. Product identity and ownership

The project should be understood as:

```text
                     ChatGPT product
                           |
                           v
                 chatgpt-web-adapter
             standalone SDK / CLI / bridge
                           |
            +--------------+--------------+
            |              |              |
            v              v              v
           CMA            HDE        other callers
```

CWA owns facts and mechanisms intrinsic to the ChatGPT product bridge:

- transport and session mechanics;
- canonical conversation observation;
- product writes;
- streaming/finality/reconciliation;
- product capabilities and provenance;
- model/product-mode selection;
- Temporary Chat semantics;
- browser authority lifecycle;
- attachments and rich product features when graduated;
- product-level diagnostics and artifacts.

CWA does **not** own downstream project cognition or authority:

- Director / Worker / Summarizer roles;
- project state or project history meaning;
- task orchestration;
- workspace mutation policy;
- Git authority;
- autonomous project continuation policy.

Those belong to CMA/HDE/other applications built on CWA.

---

## 3. Architectural invariants

The PR9 line must preserve the following unless new evidence explicitly supersedes one.

1. **CWA remains standalone.** Downstream integrations may stress-test the public contract but do not define the product roadmap.
2. **Ordinary ChatGPT product semantics remain first-class.** Do not silently substitute another product/API surface while calling it equivalent.
3. **Canonical observation and product mutation remain separate planes.**
4. **Transport selection is explicit.** No silent browser-owned ↔ browserless ↔ legacy fallback.
5. **Ambiguous writes are never automatically retried.** Reconciliation comes first.
6. **Streaming is not finality.** Incremental observations never fabricate canonical completion.
7. **Observed provenance is preserved rather than synthesized.**
8. **Capabilities remain evidence-backed.** `AVAILABLE`, `UNSUPPORTED`, `UNKNOWN`, and `UNIMPLEMENTED` remain distinct.
9. **Browser Authority Lease remains separate from Turn Lifecycle.**
10. **Browser internals stay below the public runtime boundary.** Callers should not depend on tab ids, extension worker details, Native Messaging internals, debugger target ids or concrete transport classes.
11. **The production transport remains replaceable.** New transports must fit the product-level contract rather than forcing downstream rewrites.
12. **No challenge-bypass expansion.** Do not add Turnstile solving, proof-token generation, browser-protection emulation or replay-oriented protected-write reconstruction.
13. **Browserless write work is experimental by default.** A working direct-request path does not become production merely because it passed today.
14. **Dynamic web-product drift is an explicit risk.** Browserless behavior may change independently of CWA releases and must fail clearly rather than pretend permanence.

---

## 4. Development mode after 0.2 — fast and reliable

PR8 used many small evidence and repair steps because the architecture and product contracts were still unknown. That mode should not become permanent process overhead.

Post-0.2 development should prefer **large vertical milestones**.

```text
OLD RESEARCH MODE
feature
 -> probe
 -> repair
 -> hardening
 -> replication
 -> polish
 -> another small contract PR

POST-0.2 MODE
one vertical milestone
 -> implementation
 -> deterministic regression/failure semantics
 -> bounded live validation
 -> docs/compatibility
 -> full regression
 -> DONE
```

The goal is not fewer checks. The goal is fewer administrative stops.

A separate repair/hardening PR is justified when:

- a real post-merge defect is found;
- live evidence reveals a fundamentally new boundary;
- the original milestone cannot safely contain the newly discovered work;
- product drift invalidates an existing assumption.

Do not create tiny PRs merely to repeat verification already covered by the milestone acceptance gate.

---

# PR9 — Post-0.2 Product Generation

## 5. PR9.0 — Browser-Owned v1 Completion and Standalone SDK Architecture Freeze

### Goal

Finish the browser-owned generation as the mature production baseline and freeze the standalone SDK architecture that later transports must preserve.

This is not another investigation into whether browser-owned writes work. They already do. PR9.0 should close the remaining browser-owned era as a product milestone.

### Scope

PR9.0 should include, in one vertical PR where practical:

- final review of the public `ChatGPTProductRuntime` contract;
- final transport/canonical boundary suitable for both current browser-owned and future browserless implementations;
- browser authority lifecycle and resource behavior cleanup where evidence already supports it;
- stable ordinary-text durable and Temporary behavior;
- model profile and streaming behavior under the frozen public contract;
- finality, reconciliation and ambiguous-write semantics;
- diagnostics and product provenance consistency;
- standalone Python SDK and CLI ergonomics;
- downstream compatibility expectations without adding downstream-specific orchestration;
- performance cleanup that materially improves real use;
- removal or isolation of obvious obsolete internal paths where safe;
- documentation updated from “research architecture” to “mature production browser-owned baseline”.

### Acceptance principle

```text
BrowserOwnedProductTransport
    = production implementation complete
```

“Complete” does not mean immutable. It means future work should primarily add capabilities or alternative transports rather than repeatedly reopen already-proven browser-owned foundations.

### Downstream contract

CMA is one important integration consumer. HDE and arbitrary third-party callers are equally valid consumers.

PR9.0 should preserve the rule:

```text
CWA public product contract
    stable above implementation details
```

rather than adding CMA-specific concepts to CWA.

---

## 6. PR9.1 — Experimental Browserless Request Transport

### Goal

Build the next transport generation using direct web requests where technically and ethically supportable, while keeping it explicitly experimental because ChatGPT Web is a dynamic undocumented product surface.

Target architecture:

```text
                 ChatGPTProductRuntime
                         |
          +--------------+--------------+
          |                             |
          v                             v
BrowserOwnedProductTransport   BrowserlessRequestTransport
PRODUCTION                     EXPERIMENTAL
```

### Principle

Browserless is not a requirement to eliminate the browser at any cost. It is an experimental direct-request path behind the same product-level runtime contract.

The existing production browser-owned implementation remains available as the reliable baseline.

### Vertical scope

PR9.1 should investigate and implement the complete viable browserless text path in one milestone rather than one header or endpoint per PR:

- session/auth use within existing legitimate session boundaries;
- new conversation;
- existing conversation continuation;
- prepare/write sequencing where applicable;
- response stream observation;
- canonical finality and reconciliation;
- product identity recovery;
- model/reasoning selection where representable without fabricating equivalence;
- Temporary semantics where representable;
- explicit unsupported/unknown states where not representable;
- drift/error classification;
- no automatic retry after ambiguous writes;
- no silent fallback to browser-owned writes unless the caller explicitly requests a policy that permits it.

### Experimental status

Even a successful PR9.1 remains:

```text
BrowserlessRequestTransport = EXPERIMENTAL
```

Reason:

```text
browser-owned:
    the official frontend adapts to many product changes itself

browserless:
    CWA directly depends on current web protocol behavior
```

Therefore direct-request compatibility can break when the site changes independently of a CWA release.

### Boundary rule

If a protected product write cannot be represented legitimately without reconstructing challenge protections or replay-oriented credential machinery, record the limitation. Do not turn browserless research into challenge-bypass work.

---

## 7. PR9.2 — Full Product Input Expansion: Images, Files and Multimodal

### Goal

Move CWA beyond the 0.2 text-first product contract and make the standalone SDK useful for the ordinary rich-input workflows users expect from ChatGPT.

### Scope

Prefer one integrated milestone covering:

- image upload;
- multiple images;
- image + text turns;
- general file attachment;
- PDF/document/code attachment paths;
- multimodal continuation;
- attachment identity and metadata in product responses/artifacts;
- upload/submit partial-failure semantics;
- streaming after rich input;
- model-profile interaction;
- durable versus Temporary behavior;
- capability declarations per transport.

Historical compatibility/media paths may provide evidence and implementation material, but they do not count as product-runtime graduation by themselves.

### Transport rule

Browser-owned production support and browserless experimental support are evaluated independently.

Example:

```text
images:
  browser-owned = AVAILABLE
  browserless    = UNKNOWN / EXPERIMENTAL / AVAILABLE-experimental
```

Do not flatten transport-specific evidence into one false global claim.

---

## 8. PR9.3 — Search, Tools and Rich Product Turn Surface

### Goal

Expose more of the ChatGPT product turn as structured CWA observations without turning CWA into a project agent or authority system.

### Candidate product observations

- web-search activity;
- search/source/citation observations;
- tool invocation and tool completion activity where safely observable;
- required-action states;
- connector/product activity where appropriate;
- richer assistant activity/event normalization;
- final answer plus source/provenance relationships.

### Ownership boundary

CWA may report:

```text
"ChatGPT performed/asked for product action X"
```

CWA must not infer:

```text
"therefore mutate this workspace or Git repository"
```

External/local authority remains the responsibility of the caller such as CMA or HDE.

Normalized product observations are evidence, not downstream authority.

---

## 9. PR9.4 — CWA 0.3 Stabilization and Release

### Goal

Cut the next release after the PR9 product generation reaches a coherent user-facing boundary.

Target positioning:

```text
CWA 0.2
    production-grade text product bridge

CWA 0.3 target
    mature standalone product SDK
    + completed browser-owned baseline
    + experimental browserless request transport
    + rich input / multimodal product support
    + richer search/tool/product observations where completed
```

Not every experimental surface must be promoted to stable status to ship 0.3. Experimental features must be clearly labeled and must not weaken the stable browser-owned contract.

Release acceptance should continue to require:

- full deterministic regression suite;
- bounded live product gate for changed product-facing behavior;
- Linux/Windows package validation;
- exact installed-wheel smoke;
- release metadata/tag/version agreement;
- explicit capability/support-tier documentation.

---

## 10. CMA and other downstream consumers

CMA remains strategically important because it is a demanding real consumer of CWA, but it does not own the CWA roadmap.

The relationship is:

```text
CWA releases stable product contracts
        |
        v
CMA explicitly pins/migrates to a version
```

CMA M3.0 may pin CWA 0.2.0 and migrate to `ChatGPTProductRuntime` without waiting for PR9.

Future CMA adoption of 0.3/PR9 capabilities should be an explicit downstream migration rather than an implicit moving dependency.

The same rule applies to HDE and other callers.

Cross-repository ownership details belong in [`docs/cwa_cma_coordination_roadmap.md`](docs/cwa_cma_coordination_roadmap.md), not in feature-number ownership of this roadmap.

---

## 11. Long-term direction after PR9

PR9 is not the end-state of CWA. It establishes two parallel transport realities:

```text
PRODUCTION
browser-owned product authority

EXPERIMENTAL
browserless direct-request product transport
```

Future generations may improve either side, add supported native/product surfaces if they appear, or eventually promote a browserless mode only if long-term evidence justifies a stronger support claim.

The stable abstraction should remain:

```text
application
    |
    v
ChatGPTProductRuntime
    |
    v
explicit product transport
```

so transport evolution does not force users to rebuild their applications.

---

## 12. Canonical post-0.2 sequence

```text
v0.2.0 — frozen production text baseline
   |
   v
PR9.0 — finish browser-owned generation + freeze mature standalone SDK architecture
   |
   v
PR9.1 — experimental browserless direct-request transport
   |
   v
PR9.2 — images / files / multimodal product-runtime graduation
   |
   v
PR9.3 — search / tools / rich product observations
   |
   v
PR9.4 — CWA 0.3 stabilization and release
```

The sequence may be adjusted if live product evidence reveals a fundamental dependency, but avoid returning to tiny verification-only PR chains without a concrete reason.
