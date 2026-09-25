# PR15.32 — Consolidate attachment-evidence ownership

## Purpose

Continue #107 by removing the remaining source-order replacement chain around
`_pr92ClosureAttachmentEvidenceExpression`.

The rich-input evidence implementation evolved through these shipping generations:

```text
base closure evidence
→ schema8
→ schema9
→ schema10
→ schema11
→ schema22
→ schema23
→ schema25
→ schema26
→ schema27
```

Each generation replaced the same shared runtime name. Schema27 is the final
effective production expression; schema28 and schema29 do not replace it.

## New ownership

The original closure implementation is now private:

```text
_pr92BaseAttachmentEvidenceExpression(...)
```

Historical schema generations remain explicit named helpers:

```text
_pr92Schema8AttachmentEvidenceExpression(...)
_pr92Schema9AttachmentEvidenceExpression(...)
_pr92Schema10AttachmentEvidenceExpression(...)
_pr92Schema11AttachmentEvidenceExpression(...)
_pr92Schema22AttachmentEvidenceExpression(...)
_pr92Schema23AttachmentEvidenceExpression(...)
_pr92Schema25AttachmentEvidenceExpression(...)
_pr92Schema26AttachmentEvidenceExpression(...)
_pr92Schema27AttachmentEvidenceExpression(...)
```

The sole public production owner is:

```text
service_worker_attachment_evidence.js
```

and it graduates the final effective generation directly:

```text
_pr92ClosureAttachmentEvidenceExpression(...)
→ _pr92Schema27AttachmentEvidenceExpression(...)
```

## Why direct graduation is correct

This chain is not nested composition. Each schema generation replaced the same
expression wholesale, while all evidence consumers resolved the shared name at
call time.

All rich-input schemas are loaded before turns can execute, so production
historically observed the last replacement: schema27. The new owner makes that
fact explicit instead of depending on import order.

## Preserved authority semantics

PR15.32 does not change evidence semantics. Schema27 still owns:

- official-composer evidence only;
- exact requested attachment-set matching;
- cross-channel exactness;
- independent filename-group handling;
- fail-closed unknown role-group handling;
- structured removal-control basename parsing;
- indexed-removal ambiguity handling;
- bidirectional ambiguity fail-closed behavior;
- literal semantics for unindexed removal controls.

Existing pre-stage cleanliness, post-stage stable evidence, pre-submit
revalidation, and schema7 atomic validate+click paths still resolve the same
public expression at call time.

No write, submit, retry, navigation, attachment-byte transport, or finality
authority is added.

## Assembly

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_attachment_evidence.js
→ service_worker_attachment_staging.js
→ service_worker_rich_input_lifecycle.js
```

All historical evidence helpers exist before the public owner is installed.

## Static target

```text
_pr92ClosureAttachmentEvidenceExpression public definitions = 1
_pr92ClosureAttachmentEvidenceExpression runtime assignments = 0
PriorAttachmentEvidenceExpression aliases                  = 0
```

## Regression strategy

PR15.32 verifies:

- one public attachment-evidence owner;
- zero schema-generation reassignments;
- the base closure implementation is private;
- schema27 is the directly graduated final generation;
- schema28/schema29 do not replace the capability;
- write-domain assembly installs the owner after all schemas and before staging;
- owner delegation is exactly once with no argument drift;
- existing evidence reads resolve the public owner dynamically.

Tracking: #107
