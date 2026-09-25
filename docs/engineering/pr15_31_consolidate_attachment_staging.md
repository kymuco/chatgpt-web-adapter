# PR15.31 — Consolidate attachment-staging ownership

## Purpose

Continue #107 by removing the remaining source-order replacement chain around
`_pr92StageOfficialPageAttachments`.

Unlike the nested wrappers consolidated in PR15.27–PR15.30, attachment staging
evolved as a sequence of schema generations. Each generation replaced the same
runtime name, and the last loaded implementation won.

Historical production loading:

```text
base staging
→ closure repair
→ schema 8
→ schema 10
→ schema 12
→ schema 13
```

The effective production implementation before PR15.31 was already schema 13.

## New ownership

The original implementation is now named explicitly:

```text
_pr92BaseStageOfficialPageAttachments
```

Historical staging generations remain available as named helpers:

```text
_pr92StageWithPageOwnedEvidence
_pr92Schema8StageFromCleanComposer
_pr92Schema10StageFromOfficialCleanComposer
_pr92Schema12StageWithBoundedPostStageEvidence
_pr92Schema13FullyBoundedStage
```

The sole public owner is:

```text
service_worker_attachment_staging.js
```

and it graduates the final effective production generation directly:

```text
_pr92StageOfficialPageAttachments(...)
→ _pr92Schema13FullyBoundedStage(...)
```

## Why this is not a nested composition

The historical generations intentionally bypassed earlier replacements as the
design matured.

The explicit helper dependencies preserve those exact historical choices:

```text
closure generation
→ base staging

schema 8
→ clean-composer proof
→ closure generation

schema 10
→ stronger official-composer proof
→ closure generation

schema 12
→ schema-10 clean-composer proof
→ base staging
→ deadline-bounded post-stage evidence

schema 13
→ schema-10 clean-composer proof
→ fully bounded schema-13 file selection
→ schema-12 deadline-bounded post-stage evidence
```

The public production capability therefore points only at schema 13. Earlier
generations are explicit historical/helper implementations, not import-time
owners.

## Preserved authority semantics

Schema 13 remains the exact effective production behavior.

It still requires:

- official-composer cleanliness before file selection;
- deadline-bounded debugger attach and Runtime/DOM setup;
- deadline-bounded composer readiness;
- deadline-bounded file-input lookup and reveal fallback;
- durable dirty-attachment fence persistence before file selection;
- deadline-bounded `DOM.setFileInputFiles`;
- bounded post-selection object/debugger cleanup;
- fail-closed handling of late file selection behind the durable fence;
- schema-12 stable page-owned post-stage evidence before accepting the staged
  attachment count.

No attachment bytes move through Native Messaging. The official page still owns
upload behavior. This PR adds no conversation write, protected submit, retry,
navigation, or canonical-finality authority.

## Diagnostics

Schema26/schema27 staging diagnostics continue to invoke the public production
`_pr92StageOfficialPageAttachments` capability.

Because the new owner delegates directly to schema13, diagnostics and ordinary
rich-input turns continue to exercise the same final production staging
implementation instead of accidentally binding to an earlier generation.

## Assembly

The owner is loaded in `service_worker_runtime_write.js` immediately after the
rich-input schema loader and before the rich-input lifecycle:

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_attachment_staging.js
→ service_worker_rich_input_lifecycle.js
```

At this point all schema-generation helpers, including schema13, are defined
before any turn can invoke the public staging capability.

## Static target

```text
_pr92StageOfficialPageAttachments public definitions = 1
_pr92StageOfficialPageAttachments runtime assignments = 0
PriorStageOfficialPageAttachments aliases             = 0
```

## Regression strategy

PR15.31 adds an ownership regression that verifies:

- one public staging owner;
- no former generation reassigns the public staging hook;
- no staging prior-function aliases remain;
- the write domain loads the owner after all schema generations;
- the public owner delegates to schema13 exactly once without argument drift;
- historical generation helper dependencies remain explicit;
- schema13 retains the exact clean → bounded file selection → post-stage
  evidence ordering.

Existing schema8/schema10/schema12/schema13 and staging-diagnostic tests continue
to own their detailed behavioral contracts.

## Acceptance

- one public attachment-staging owner;
- zero runtime reassignments of the staging hook;
- zero staging prior aliases;
- schema13 remains the exact effective production implementation;
- durable-fence, deadline, cleanup, and page-owned evidence semantics unchanged;
- staging diagnostics still use the production capability;
- engineering quality and JavaScript syntax green;
- full Linux/Windows Python 3.10–3.14 matrix green;
- release build and installed-wheel smoke green.
