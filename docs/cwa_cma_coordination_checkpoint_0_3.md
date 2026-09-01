# CWA ↔ CMA coordination checkpoint after CWA 0.3

_Status: synchronization checkpoint; ownership rules remain unchanged._

The older coordination roadmap records the 0.2-era migration plan. This checkpoint
updates the concrete version/milestone facts without making CWA a CMA-specific
support library.

## Current released CWA baseline

```text
CWA version  0.3.0
CWA tag      v0.3.0
CWA commit   112a47e3c586d0720e4be85e43e7e793edb9cfc6
release      2026-09-01
```

CWA 0.3 includes the mature browser-owned product runtime, experimental browserless
request transport, rich-input graduation on the proven browser-owned provider path,
and structured search/tool/source/citation observations.

## Current CMA checkpoint

CMA has progressed beyond the old M2.4.x/M3.0 planning checkpoint. The latest merged
cross-project fact used here is:

```text
CMA M4.2
Durable Experiment / Run / Evidence Registry
merged PR #22
merge commit 3bd17b67bfa3f6e38ed41f1cd16b5e71b4dbe34b
```

This does not imply that CMA must immediately consume every CWA 0.3 capability.
Dependency migration remains explicit and versioned.

## Ownership remains unchanged

```text
ChatGPT product
      |
      v
CWA product/runtime evidence
      |
      v
CMA provider/orchestration meaning
      |
      v
CMA local authority / workspace / Git policy
```

For PR10.0 specifically:

```text
CWA may report:
    app/connector activity
    required user action
    product continuation evidence

CWA does not infer:
    approve the action
    mutate the project
    authorize Git/filesystem/provider changes
```

CMA or another caller may use CWA evidence as one input to its own policy, but product
observation never becomes downstream authority by implication.
