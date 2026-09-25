# PR15.45 — Consolidate attachment-readiness ownership

## Purpose

Continue #107 by classifying the six remaining rich-input schema hooks and
consolidating the first coherent observational cluster:

```text
_pr92ClosureReadPageOwnedAttachmentEvidence
_pr92Schema10RequireOfficialCleanComposerBeforeStaging
_pr92Schema12ObservePostStageAttachmentEvidence
```

These hooks all govern page-owned attachment/composer observation around staging.
They do not own protected submit, retry, navigation, or canonical finality.

## Audit classification

The six names remaining after PR15.44 are not one authority chain.

```text
attachment/composer readiness:
  _pr92ClosureReadPageOwnedAttachmentEvidence
  _pr92Schema10RequireOfficialCleanComposerBeforeStaging
  _pr92Schema12ObservePostStageAttachmentEvidence

submit readiness:
  waitForSendButtonPoint

durable cleanup fence:
  _pr92ReadDirtyAttachmentFence

optional post-write diagnostics / identity reserve:
  _pr92Schema17OptionalPostWrite
```

The Temporary snapshot hook remains a separate domain:

```text
_pr87TemporaryControlSnapshotExpression
```

PR15.45 closes only the first cluster.

## Historical effective generations

Attachment evidence read:

```text
closure base read
→ schema11 outer-deadline wrapper
```

Pre-stage official composer proof:

```text
schema10 initial clean proof
→ schema15 completed debugger handoff
→ schema24 composer-mount wait + clean proof
```

Post-stage attachment proof:

```text
schema12 bounded observer setup
→ schema15 completed debugger handoff
```

Schema15 and schema24 replaced their public names directly; they did not wrap the
previous public binding. The explicit owner therefore selects the final effective
generation rather than manufacturing delegation that never existed historically.

## Explicit helpers

PR15.45 leaves historical implementations named and immutable:

```text
_pr92ClosureBaseReadPageOwnedAttachmentEvidence
_pr92Schema11ReadPageOwnedAttachmentEvidence

_pr92Schema10BaseRequireOfficialCleanComposerBeforeStaging
_pr92Schema15RequireOfficialCleanComposerBeforeStaging
_pr92Schema24RequireOfficialCleanComposerBeforeStaging

_pr92Schema12BaseObservePostStageAttachmentEvidence
_pr92Schema15ObservePostStageAttachmentEvidence
```

## Sole public owner

`service_worker_attachment_readiness.js` owns:

```text
_pr92ClosureReadPageOwnedAttachmentEvidence(...)
→ _pr92Schema11ReadPageOwnedAttachmentEvidence(...)
→ _pr92ClosureBaseReadPageOwnedAttachmentEvidence(...)

_pr92Schema10RequireOfficialCleanComposerBeforeStaging(...)
→ _pr92Schema24RequireOfficialCleanComposerBeforeStaging(...)

_pr92Schema12ObservePostStageAttachmentEvidence(...)
→ _pr92Schema15ObservePostStageAttachmentEvidence(...)
```

Existing staging and diagnostic consumers continue resolving the public names at
call time.

## Preserved semantics

PR15.45 changes ownership only.

The final production behavior remains:

- attachment evidence reads are bounded by the one outer rich-turn deadline;
- the schema11 exact structured-basename evidence rules remain intact;
- pre-stage cleanliness waits for the official composer to mount before treating
  the empty attachment set as authoritative;
- two stable clean polls are still required;
- a mounted dirty composer still fails closed;
- successful observer debugger ownership is fully relinquished inside the same
  outer deadline before the next phase may attach;
- failure/timeout detach remains best-effort and cannot rewrite the failed result;
- post-stage page-owned attachment evidence still requires stable exact evidence.

No product write or retry is added.

## Assembly

The explicit owner is installed after the historical schema loader and the
attachment-evidence expression owner, but before cleanup/staging owners:

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ ...
→ service_worker_attachment_evidence.js
→ service_worker_attachment_readiness.js
→ service_worker_attachment_cleanup.js
→ service_worker_attachment_staging.js
```

## Static target

```text
_pr92ClosureReadPageOwnedAttachmentEvidence public definitions = 1
runtime assignments = 0
_pr92Schema11PriorReadPageOwnedAttachmentEvidence aliases = 0

_pr92Schema10RequireOfficialCleanComposerBeforeStaging public definitions = 1
runtime assignments = 0

_pr92Schema12ObservePostStageAttachmentEvidence public definitions = 1
runtime assignments = 0
```

## Remaining confirmed ownership inventory

After PR15.45:

```text
rich-input:
  waitForSendButtonPoint
  _pr92ReadDirtyAttachmentFence
  _pr92Schema17OptionalPostWrite

Temporary state:
  _pr87TemporaryControlSnapshotExpression
```

Recommended bounded order:

1. submit-readiness ownership;
2. dirty-fence read ownership;
3. optional post-write ownership;
4. Temporary snapshot ownership;
5. final static no-reassignment closure gate.

Tracking: #107


## Follow-up ownership note

PR15.46 later consolidates the remaining public submit-readiness seam
`waitForSendButtonPoint` into one explicit owner while preserving the separate
PR11.7 ordinary-text UI-compatibility helper.
