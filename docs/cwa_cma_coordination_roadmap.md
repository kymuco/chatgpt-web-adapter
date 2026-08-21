# CWA ↔ CMA Coordination Roadmap

_Last synchronized: 2026-08-20_

This document is the cross-repository planning contract between `chatgpt-web-adapter` (CWA) and `codexia-manual-agent` (CMA). It is intentionally narrower than either repository's full roadmap. When an older roadmap paragraph uses broader language such as “HDE owns workflow meaning” or “CWA is transport only”, this document defines the current ownership boundary for CWA ↔ CMA work.

## 1. Architectural split

```text
ChatGPT product
      ↓
CWA — product bridge
      ↓
CMA provider/runtime
      ↓
CMA project/orchestration layer
      ↓
CMA local authority + workspace/Git execution
```

### CWA owns product/runtime primitives

CWA owns facts and mechanisms that are intrinsic to the ChatGPT product bridge:

- ordinary ChatGPT product transport;
- canonical conversation reads, status, attach/session identity and finality;
- browser-owned product writes and Browser Authority lifecycle;
- durable vs Temporary Chat product semantics;
- semantic model/reasoning profiles and selection provenance;
- revision-safe assistant text streaming;
- normalized user-visible activity/tool/search streaming;
- optional final-answer-only streaming;
- product capabilities and execution provenance;
- canonical reconciliation and ambiguous-write handling;
- deterministic product-level `ConversationSnapshot` artifacts;
- low-level CLI/SDK diagnostics such as status/messages/capabilities/doctor.

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

CMA must not depend on Chrome tab ids, service-worker internals, Native Messaging details or the concrete CWA browser writer.

## 2. Terminology boundary

Two names are deliberately kept distinct.

### CWA `ConversationSnapshot`

A transport/product artifact describing what was actually present in a ChatGPT conversation. It may contain deterministic user/assistant context output and an optional raw product payload backup.

### CMA `ProjectContextCheckpoint`

A semantic project artifact describing what the project should carry forward after one or more conversations. It is produced by CMA policy, not by CWA transport logic.

The intended flow is:

```text
CWA ConversationSnapshot
        ↓ source/provenance
CMA Summarizer
        ↓
HistoryDelta
        ↓
ProjectContextCheckpoint
```

CMA should therefore not introduce another orchestration object called `ConversationSnapshot`.

Likewise, orchestration results use `WorkResult`, not `ResultReceipt`. The word `receipt` remains reserved for authority/security concepts such as authorization receipts and mutation receipts/observations.

## 3. Synchronized execution order

CWA and CMA can advance in parallel because their next milestones are on different layers.

### CWA

1. **PR8.12 — normalized activity + final-only streaming**
   - full user-visible turn stream is implemented and live-covered;
   - presentation polish is complete;
   - `--stream --final-only` is implemented as an optional quieter surface.
2. **PR8.13 — Temporary Chat production graduation**
   - production `conversation_mode="temporary"` path;
   - pre-write Temporary proof;
   - same-lifecycle continuation authority where supported;
   - Temporary-specific finality/recovery semantics;
   - no durable fallback.
3. **Standalone/runtime stabilization for 0.2**
   - README quick start for `cwa send` and `cwa snapshot`;
   - `cwa status`, `cwa messages`, `cwa capabilities`;
   - explicit snapshot vs export distinction;
   - `cwa doctor`;
   - stable artifact manifest/CLI contracts and exit codes;
   - Windows/Linux CI, wheel/sdist smoke, changelog and release cleanup.

CWA should not add project summarization, history merge, Director/Worker state machines or project rollover as part of this sequence.

### CMA

1. **M2.4.1 — exact patch proposal contract** — COMPLETE.
2. **M2.4.2 — complete preimage/namespace revalidation + exact execution plan**
   - revalidate the entire multi-file preimage set before authority consumption;
   - bind an execution plan to accepted M2.3 create/replace primitives.
3. **M2.4.3 — multi-file application and failure semantics**
   - define the commit model;
   - all-or-fail where supportable, otherwise explicit bounded partial-failure semantics;
   - no silent best-effort mutation.
4. **M2.4.4 — changed-file mutation observations/receipts**
   - digest-bound per-file/set execution observations;
   - exact changed-file/failure evidence.
5. **M2.4.5 — rollback, crash and recovery semantics**
   - recover from interrupted multi-file application according to the chosen commit model.
6. **M2.4.6 — model patch request → bounded proposal → local human approval**
   - the remote model may propose a bounded patch request;
   - it still receives no direct write authority;
   - execution remains under CMA local authority.
7. **M2.5 — explicit Git mutation governance**
   - commit and push remain distinct authorized actions;
   - workspace mutation never implies Git authority.
8. **M3.0 — CWA Product Runtime provider migration**
   - move CMA off the old `ChatGPTWebClient.send()/send_to_conversation()` integration contract;
   - consume stable `ChatGPTProductRuntime` capabilities/provenance/streaming surfaces;
   - keep browser internals below the CWA boundary.
9. **M3.1 — durable `ProjectState` + event journal**
   - persistent exact chronology for project/runtime decisions, tool results, authority outcomes and conversation identities.
10. **M3.2 — Summarizer + `HistoryDelta` + `ProjectContextCheckpoint` + rollover**
    - project-semantic context compression and deterministic handoff;
    - CWA snapshots are inputs/provenance, not the project memory format.
11. **M3.3 — Director/Worker protocol**
    - `WorkOrder` issuance;
    - `WorkResult` return contract;
    - conversation allocation and role boundaries.
12. **M3.4 — project execution state machine**

```text
INIT
→ DIRECTING
→ WORK_READY
→ EXECUTING
→ VERIFYING
→ REVIEW_READY
→ DIRECTING

terminal:
COMPLETE / BLOCKED / FAILED / ESCALATED / BUDGET_EXHAUSTED
```

13. **M3.5 — deterministic resume/recovery and multi-conversation lifecycle**
    - interrupted Director/Worker work can be reconstructed from durable state;
    - no duplicate side effect is inferred from conversational state alone.
14. **M4 — Computational Lab** builds on the completed project runtime.
15. **M5 — bounded automation** adds limited autonomous continuation with explicit budgets and stop policies.

## 4. Integration contract

CMA should consume CWA through a provider boundary conceptually shaped like:

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
          ↓
CMA provider adapter
          ↓
Director / Worker / Summarizer
          ↓
ProjectState + WorkOrder + WorkResult
HistoryDelta + ProjectContextCheckpoint
          ↓
CMA local authority / workspace / Git governance
```

CWA events are observations. They do not become CMA authority.

CMA authority objects are local. They do not become CWA product-transport concerns.

## 5. Explicit non-overlap rules

- CWA does not summarize project history; CMA does.
- CWA does not decide when project context rolls over; CMA does.
- CWA does not create `WorkOrder`; CMA does.
- CWA does not interpret tool/search activity as project progress; CMA may interpret normalized observations if useful.
- CMA does not reimplement ChatGPT stream parsing; it consumes CWA events.
- CMA does not select or mutate Chrome/browser internals; it requests CWA product intent.
- CMA patch authority does not imply Git commit/push authority.
- GitHub-first project workflows do not bypass M2.4/M2.5 authority boundaries.
- Neither project treats conversational success text as proof that a filesystem/Git side effect occurred; local execution observations remain authoritative for local effects.

## 6. Release synchronization checkpoint

Before CMA M3.0 is considered complete, CWA should have a stable enough 0.2-facing contract for the surfaces CMA consumes. CMA may integrate earlier against the feature branch for development, but the M3.0 completion gate should pin an explicit CWA version/commit and record the exact capability assumptions.

After M3.0, future CWA implementation changes remain replaceable behind the product-runtime contract and should not require CMA orchestration redesign.