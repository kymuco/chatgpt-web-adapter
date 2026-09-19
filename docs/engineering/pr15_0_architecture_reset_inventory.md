# PR15.0 — Architecture Reset Inventory and Consolidation Boundary

Status: draft architecture gate  
Base: `bcab380705e7007597d30f7260aec20095a9a975`  
Tracking: #107

## Why this milestone exists

PR14.9 exposed a structural problem rather than only a local failure mode.

A locally correct change could land in the base page turn, another in a recovery
wrapper, another in an early-terminal wrapper, while the actual production
`canonicalCompleted` continuation path still bypassed request-bound identity
authority.

That is possible because historical research and repair composition has become part
of the runtime architecture.

The PR15 line changes the optimization target:

```text
before:
  preserve each discovered repair layer

now:
  preserve proven behavior and invariants
  while deleting historical runtime structure
```

The repository stays the same. There is no parallel v2 repository and no speculative
universal-runtime rewrite.

## Baseline on post-PR14.9 main

Measured repository surface:

| Surface | Files | Bytes | lineage-named files |
| --- | ---: | ---: | ---: |
| `src/chatgpt_web_adapter` | 178 | 2,026,006 | ~80 |
| `browser_native_extension` | 120 | 1,239,592 | ~86 |
| `tests` | 302 | 1,979,633 | ~184 |

"Lineage-named" means names carrying research history such as `pr*`, `schema*`,
`repair`, `forensics`, or `live_gate`.

Code search also finds dozens of shipping extension modules that redefine
`executeNativeTurn` or `executeOfficialPageTurn`, often retaining the previous
function under a `PriorExecute...` alias.

That makes import order part of behavior.

## Architectural rule

```text
one concept
→ one implementation
→ one owner
→ one explicit call path
```

A migration is incomplete while both old and new owners remain active.

A compatibility facade may remain public, but it must not own a second implementation.

## Production categories

Every shipping module must converge to one of four categories:

### 1. Runtime

Required for a supported production capability.

Runtime code must use stable names based on responsibility, not the PR that created it.

### 2. Compatibility

A thin forwarding surface retained for public import/API compatibility.

Compatibility code may adapt names and arguments. It must not duplicate behavior or
become a second runtime path.

### 3. Diagnostic / validation

Doctor, bounded live gates, deployment verification, migration checks and release
validation.

These may inspect production behavior but must not participate in ordinary product
execution.

### 4. Research / historical evidence

Characterization probes, abandoned schema experiments, historical repair generations,
forensics and decision records.

Research code must not be imported by production.

Where retained in-tree, prefer an explicit research/archive location rather than the
shipping runtime package.

## Explicit ChatGPT turn target

The consolidated ChatGPT path must read top-to-bottom:

```text
TurnRequest
    ↓
resolve conversation
    ↓
acquire browser authority
    ↓
prepare product surface
    ↓
submit
    ↓
bind exact request identity
    ↓
observe product response
    ↓
canonical reconcile / prove finality
    ↓
release browser authority
    ↓
TurnResult
```

Optional behavior must be represented by explicit composition/calls, not by replacing
global functions after import.

### Forbidden end-state pattern

```javascript
const prior = executeNativeTurn;
executeNativeTurn = async function (...) {
    ...
    return prior(...);
};
```

The same rule applies to `executeOfficialPageTurn` and equivalent Python facades that
retain multiple active implementations.

## Migration protocol

Each consolidation slice follows:

```text
identify one active concept
→ identify all current owners/wrappers
→ choose the canonical owner
→ move behavior into explicit composition
→ run deterministic equivalence tests
→ run bounded live proof when the invariant requires product evidence
→ delete the displaced owner(s)
```

Do not leave a working old path "temporarily" in production after the new path is
accepted.

## Safety invariants that survive the rewrite

The reset is structural, not semantic.

At minimum retain:

```text
model intent != execution authority
identity != permission
product observation != approval
streaming != canonical finality
request identity != canonical persistence
canonical persistence != replay authority
ambiguous delegated write != automatic retry
transport fact != consumer semantic decision
```

PR14.9 specifically freezes:

```text
canonicalCompleted recovery continuation
→ request-bound identity authority active
→ exact user message identity may be proven
→ one bounded canonical reconciliation
→ no replay authority minted from persistence
```

## Multi-provider direction

Do not add provider #2 to the current layered ChatGPT implementation.

First consolidate ChatGPT. Then extract only the contracts that survive the real
ChatGPT implementation.

Target separation:

```text
neutral runtime semantics
!= provider semantics
!= transport mechanics
```

Conceptual target:

```text
runtime/
  core/
    contracts
    capabilities
    conversation
    lifecycle
    errors

  providers/
    chatgpt/
      provider
      canonical
      auth
      transports/

    deepseek/
      provider
      canonical
      auth
      transports/
```

This structure is illustrative, not a commitment to exact package names.

### Provider proof order

```text
1. consolidated ChatGPT provider
2. minimal DeepSeek Web provider
3. evaluate abstraction
4. only then consider Gemini
```

DeepSeek is intentionally the second proof because its web-session/API behavior is
materially different from ChatGPT browser-owned continuation behavior.

Provider-specific capabilities remain explicit. The neutral runtime must not pretend
that every provider supports the same product surface.

## Repository / package decision

Do not create:

```text
cwa-v2
cwa-next
universal-web-adapter
web-ai-runtime
```

at this stage.

Keep:

- the same repository;
- the same history;
- the current `chatgpt-web-adapter` distribution;
- compatibility for existing consumers while each slice migrates.

A separate neutral runtime repository/package is justified only after at least two
materially different providers use the same proven core without provider-specific
leakage.

## Directional acceptance criteria

The architecture reset should drive these values toward zero:

```text
production filenames carrying PR/schema lineage
runtime monkeypatch-by-import-order wrappers
research/forensics imported by production
multiple active implementations for one capability
provider wire payload knowledge in neutral core
provider-specific conditionals outside provider registration/composition
```

Completed migration slices should reduce active production complexity. Net file/LOC
growth is acceptable for a temporary slice only when the same slice deletes displaced
runtime ownership before acceptance.

## PR15 sequence

### PR15.0 — inventory and consolidation boundary

Deliver:

- current production composition map;
- module category inventory;
- first deletion/consolidation candidates;
- roadmap/status update;
- no new product capability.

### PR15.1 — explicit ChatGPT runtime

Deliver:

- explicit ordinary-turn call graph;
- removal of wrapper-by-import-order ownership for migrated slices;
- behavior-equivalent deterministic tests;
- bounded live proofs for preserved authority/finality boundaries;
- deletion of displaced repair generations.

### PR15.2 — provider architecture proof

Deliver:

- provider-neutral contracts extracted from consolidated behavior;
- ChatGPT as provider #1;
- minimal DeepSeek Web text/continuation implementation as provider #2;
- no broad images/tools/account-pool scope;
- evidence that the neutral core does not depend on ChatGPT or DeepSeek wire shapes.

## First inventory targets

Highest-value consolidation targets discovered from the current tree:

1. browser extension `executeNativeTurn` wrapper chain;
2. `executeOfficialPageTurn` wrapper chain;
3. rich-input `schema7 ... schema29` production lineage;
4. product/runtime facade + frozen-core duplication;
5. PR8.8 instant/browser-authority forensics still located inside the shipping package;
6. generated-artifact characterization generations that remain packaged despite a
   frozen capability conclusion;
7. live gates and characterization runners living beside runtime implementation.

The first code migration should choose one of these chains and delete owners, not add
another facade.
