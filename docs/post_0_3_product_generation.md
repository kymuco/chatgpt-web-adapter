# CWA post-0.3 product generation

_Status: PR10.0 working contract_

CWA 0.3.0 is the released baseline for the next product generation.

```text
release  v0.3.0
main     112a47e3c586d0720e4be85e43e7e793edb9cfc6
```

The PR10 line should extend the released product-runtime contract without reopening
already-proven browser-owned write/finality foundations or silently promoting
experimental browserless behavior.

## Product terminology

The ChatGPT product increasingly presents external integrations as Apps and Plugins,
while CWA 0.3 retains the compatibility capability name `TOOLS_CONNECTORS`.
PR10 documentation therefore uses **app/connector** for the user-visible product
surface without renaming the released capability identifier inside this milestone.

## PR10.0 — app/connector and required-action lifecycle

### Goal

Expose a structured, privacy-bounded lifecycle when ChatGPT uses a connected app or
connector and when the product requires user action before continuation.

The core invariant is:

```text
product observation
    != product approval
    != connector authorization
    != local/external action authority
    != canonical finality
    != write retry authority
```

CWA reports what the ChatGPT product visibly did or requested. It does not decide
whether an external action should be allowed, and it does not acquire workspace,
filesystem, Git, account, or provider authority from an observation.

### Required lifecycle evidence

Prefer explicit stable product identifiers over inferred pairing:

```text
connector/app activity id
    + optional connector/app identity
    + optional operation
    + lifecycle phase

required action id
    + action type
    + optional connector/app correlation
    + lifecycle phase
```

Supported lifecycle phases are:

- `STARTED`
- `UPDATED`
- `COMPLETED`
- `FAILED`

The existing PR9.3 point event remains valid as `OBSERVED` when stronger lifecycle
correlation is unavailable.

### Correlation rule

CWA must not pair request/result/action events merely because they are adjacent,
share a label, have similar tool names, or appear in one turn. Lifecycle correlation
requires an explicit stable identifier supplied by the observed product surface.
Conflicting reuse of one stable identifier fails closed.

### Privacy rule

Structured app/connector observations must never contain raw tool arguments/results,
OAuth tokens, cookies, authorization headers, refresh/access tokens, signed URLs,
provider credentials, private reasoning, raw SSE, or arbitrary connector payloads.
Only bounded identifiers, safe product labels, operation names, lifecycle phase,
sequence, and timing metadata are eligible for typed observation.

### Capability rule

`TOOLS_CONNECTORS` stays `UNKNOWN` until authenticated live product evidence proves
that the browser-owned observation channel can repeatedly expose a stable and safe
app/connector lifecycle. Deterministic tests are necessary but not sufficient for
capability graduation.

### Acceptance

PR10.0 is complete only when:

1. deterministic collector/runtime tests pass across the supported Python matrix;
2. legacy PR9.3 observation semantics remain compatible;
3. collector defects remain non-authoritative and cannot invalidate/retry a write;
4. privacy regressions are fail-closed;
5. browser-owned app/connector event shape is characterized without exporting raw
   credentials or payloads;
6. one bounded authenticated live gate confirms the implemented event contract, or
   the capability remains explicitly `UNKNOWN` with the unsupported evidence recorded;
7. canonical readback/finality remains independent of connector/action observations;
8. exact installed-wheel smoke remains green before merge.

## Later PR10 milestones

Do not freeze later milestone contents before PR10.0 live evidence. Candidate areas
include generated/downloadable product artifacts, compatibility-drift hardening, and
real downstream adoption feedback. Each should remain a vertical product milestone,
not a sequence of verification-only micro-PRs.
