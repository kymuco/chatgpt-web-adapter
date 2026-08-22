# CWA ↔ CMA Coordination Roadmap

_Last synchronized: 2026-08-22_

This document is the cross-repository coordination contract between `chatgpt-web-adapter` (CWA) and `codexia-manual-agent` (CMA).

It does **not** make CWA a CMA support project. CWA is a standalone SDK / CLI / local ChatGPT product bridge with its own roadmap, releases and users. CMA is one demanding downstream consumer of the public CWA contract.

The purpose of this document is narrower:

- preserve the ownership boundary;
- record version/integration checkpoints;
- prevent duplicate implementation across repositories;
- keep CMA migrations explicit when CWA evolves.

For CWA feature sequencing, [`../ROADMAP.md`](../ROADMAP.md) is authoritative.

---

## 1. Architectural split

```text
ChatGPT product
      |
      v
CWA — standalone product bridge / SDK / CLI
      |
      v
CMA provider/runtime
      |
      v
CMA project/orchestration layer
      |
      v
CMA local authority + workspace/Git execution
```

CWA is also directly consumable by HDE, terminal users, Python applications and other local tools:

```text
                    CWA
                     |
        +------------+------------+
        |            |            |
        v            v            v
       CMA          HDE      other callers
```

CMA must therefore consume CWA through the same public product contract available to other callers rather than through CMA-specific hooks.

---

## 2. Ownership boundary

### CWA owns product/runtime primitives

CWA owns facts and mechanisms intrinsic to the ChatGPT product bridge:

- ordinary ChatGPT product transport;
- canonical conversation reads, status, attach/session identity and finality;
- browser-owned product writes and Browser Authority lifecycle;
- explicit transport selection;
- durable vs Temporary Chat product semantics;
- semantic model/reasoning profiles and selection provenance;
- revision-safe assistant text streaming;
- normalized user-visible product activity;
- optional final-answer-only streaming;
- product capabilities and execution provenance;
- canonical reconciliation and ambiguous-write handling;
- product `ConversationSnapshot` / export artifacts;
- product-level CLI/SDK diagnostics such as status/messages/capabilities/doctor;
- images/files/multimodal/search/tool observations when those capabilities graduate;
- experimental browserless direct-request transport work under CWA support-tier rules.

CWA must not own project cognition, project history meaning, task orchestration, local tool authority, workspace mutation policy or Git policy.

### CMA owns project/runtime meaning

CMA owns semantics that exist because a project is being worked on rather than because ChatGPT is being transported:

- provider role/prompt protocol above CWA;
- Director/Lead, Worker/Engineer and Summarizer roles;
- `ProjectState` and project lifecycle;
- `WorkOrder` and `WorkResult` contracts;
- project context selection and projection;
- `HistoryDelta` and semantic history merge;
- `ProjectContextCheckpoint` and context rollover;
- conversation allocation/reuse policy across Director/Worker/Summarizer;
- read-only project tools and local tool broker;
- local authorization, action proposals and security receipts;
- workspace patch proposal/application/verification;
- Git mutation governance;
- deterministic project resume/recovery;
- bounded autonomous work policy.

CMA must not depend on Chrome tab ids, service-worker internals, Native Messaging details, debugger target ids, private web protocol details or the concrete CWA transport implementation.

---

## 3. Terminology boundary

Two names remain deliberately distinct.

### CWA `ConversationSnapshot`

A product/transport artifact describing what was present in a ChatGPT conversation. It may contain deterministic user/assistant context and optional product payload evidence according to the CWA artifact contract.

### CMA `ProjectContextCheckpoint`

A semantic project artifact describing what the project should carry forward after one or more conversations. It is produced by CMA policy, not CWA transport logic.

The intended flow remains:

```text
CWA ConversationSnapshot
        |
        v
CMA Summarizer
        |
        v
HistoryDelta
        |
        v
ProjectContextCheckpoint
```

CMA should not introduce another orchestration object named `ConversationSnapshot`.

Likewise, orchestration results use `WorkResult`, not `ResultReceipt`. `receipt` remains reserved for authority/security/mutation evidence where appropriate.

---

## 4. Current synchronization checkpoint

### CWA

CWA 0.2.0 is released and frozen as the current stable baseline:

```text
version     0.2.0
tag         v0.2.0
commit      f1ebfd671c45153a3279163dc624e0af7c00e3f9
release     2026-08-22
```

The release includes the stable product-runtime text contract required for CMA migration:

- `ChatGPTProductRuntime`;
- health/capability inspection;
- durable text turns;
- Temporary text turns;
- model profile intent and provenance;
- revision-safe/final-only streaming;
- canonical status/messages/attach/readback;
- finality/reconciliation semantics;
- no automatic ambiguous-write retry;
- product conversation artifacts;
- stable CLI/diagnostic surfaces.

CWA 0.2 intentionally leaves images/files/multimodal/search/tools and browserless production writes outside the stable product-runtime contract.

### CMA

At the current synchronization point, CMA has completed M2.4.4 — exact changed-file mutation observations and digest-bound set receipts.

The synchronized next sequence remains:

```text
M2.4.5
rollback / crash / recovery semantics
        |
        v
M2.4.6
model patch request
 -> bounded proposal
 -> local human approval
        |
        v
M2.5
explicit Git mutation governance
        |
        v
M3.0
CWA Product Runtime provider migration
```

CMA may continue its local-authority work independently while CWA begins PR9.

---

## 5. CMA M3.0 — explicit CWA 0.2 migration gate

CMA M3.0 should migrate off the old compatibility integration based on direct `ChatGPTWebClient.send()` / `send_to_conversation()` usage and consume the stable CWA product runtime instead.

Conceptual provider boundary:

```text
CWA ChatGPTProductRuntime
    health / capabilities
    send / send_text_observed
    canonical status/messages/attach
    model profile intent
    durable/temporary conversation intent
    answer/activity stream events
    execution provenance
    product ConversationSnapshot
          |
          v
CMA provider adapter
          |
          v
Director / Worker / Summarizer
          |
          v
ProjectState + WorkOrder + WorkResult
HistoryDelta + ProjectContextCheckpoint
          |
          v
CMA local authority / workspace / Git governance
```

### M3.0 pin

M3.0 should record an explicit dependency baseline:

```text
CWA version  = 0.2.0
CWA tag      = v0.2.0
CWA commit   = f1ebfd671c45153a3279163dc624e0af7c00e3f9
```

and record the exact capability assumptions CMA relies on.

CMA must not implicitly follow moving CWA `main`.

---

## 6. CWA PR9 proceeds independently

CWA no longer needs to wait for CMA M3.0 before continuing its own product roadmap.

The post-0.2 sequence is owned by CWA:

```text
PR9.0
finish browser-owned generation
+ freeze mature standalone SDK architecture
        |
        v
PR9.1
experimental browserless direct-request transport
        |
        v
PR9.2
images / files / multimodal product-runtime graduation
        |
        v
PR9.3
search / tools / rich product observations
        |
        v
PR9.4
CWA 0.3 stabilization/release
```

CMA does not get CWA-specific milestone numbers in its own roadmap and CWA does not get CMA orchestration milestone numbers in its roadmap.

The projects synchronize at explicit version boundaries instead.

---

## 7. Browser-owned and browserless coordination rule

CMA M3.0 should rely on the stable 0.2 browser-owned product contract.

Future CWA browserless work is explicitly experimental:

```text
BrowserOwnedProductTransport
    production baseline

BrowserlessRequestTransport
    experimental direct-request path
```

CMA must not silently switch transports merely because a browserless experiment exists.

Any future CMA use of browserless CWA should be an explicit dependency/configuration decision with capability checks and support-tier awareness.

This keeps site-protocol drift inside CWA rather than leaking private request details into CMA.

---

## 8. Capability and version migration policy

After M3.0, CMA should treat CWA as a versioned dependency.

When CWA releases a new version:

```text
new CWA release
      |
      v
CMA evaluates public capability delta
      |
      +-- no needed change -> remain pinned
      |
      `-- desired capability -> explicit migration PR
```

Examples:

- CMA can remain on 0.2 while CWA experiments with browserless PR9.1.
- CMA may later migrate to a 0.3 release to consume rich product observations or multimodal support.
- CMA should never depend on experimental internals merely because they are present in CWA source.

---

## 9. Explicit non-overlap rules

- CWA does not summarize project history; CMA does.
- CWA does not decide when project context rolls over; CMA does.
- CWA does not create `WorkOrder`; CMA does.
- CWA does not interpret product search/tool activity as project progress; CMA may interpret normalized observations.
- CMA does not reimplement ChatGPT stream parsing; it consumes CWA events.
- CMA does not select or mutate Chrome/browser internals; it requests CWA product intent.
- CMA does not implement browserless private web protocol details; CWA owns those experiments.
- CMA patch authority does not imply Git commit/push authority.
- GitHub-first project workflows do not bypass CMA local authority boundaries.
- Neither project treats conversational success text as proof that a filesystem/Git side effect occurred; local execution observations remain authoritative for local effects.
- CWA product events are observations, not CMA local authority.
- CMA local authority objects are not CWA product-transport concerns.

---

## 10. Development cadence coordination

CWA post-0.2 development now prefers large vertical milestones:

```text
implementation
+ deterministic tests
+ failure semantics
+ bounded live validation
+ docs/compatibility
= one completed PR
```

CMA may continue using its own evidence/authority cadence where local mutation safety requires it.

The two repositories do not need identical PR granularity.

Cross-project coordination should happen at:

- stable public contract changes;
- explicit version pins;
- capability additions/removals;
- breaking migration requirements;
- evidence that the current ownership boundary is wrong.

Routine CWA polish should not block CMA, and routine CMA orchestration work should not block CWA.

---

## 11. Canonical relationship after CWA 0.2

```text
CWA
standalone product bridge
owns ChatGPT product/runtime mechanics
        |
        | stable versioned contract
        v
CMA
project/orchestration runtime
owns project meaning + local authority
```

The integration is intentionally asymmetric:

- CWA does not know it is serving CMA;
- CMA knows which CWA contract/version it consumes.

That asymmetry is a feature. It keeps CWA reusable and keeps CMA insulated from browser/web-product implementation changes.
