# PR15.35 — Consolidate protected-submit expression ownership

## Purpose

Continue #107 by removing source-order replacement from the rich-input
protected-submit page expression.

Before this slice the shipping name
`_pr92Schema7AtomicAttachmentSubmitExpression` evolved through:

```text
schema 7 atomic attachment validation + click
→ schema 20 early page-side arm marker
→ schema 21 validated-click-boundary arm
```

Schema 21 intentionally bypassed schema 20's early-marker wrapper because that
wrapper armed request authority before schema-7 validation had completed. The
final effective behavior was therefore schema-21 semantics built directly from
the immutable schema-7 expression.

## Explicit stages

PR15.35 names the historical stages directly:

```text
_pr92Schema7BaseAtomicAttachmentSubmitExpression(...)
_pr92Schema20PageSideArmProtectedSubmit(...)
_pr92Schema21ValidatedClickBoundaryArm(...)
```

Schema 20 and schema 21 no longer capture or reassign the public builder.

The sole production owner is:

```text
service_worker_protected_submit_expression.js
```

and the public call is explicitly:

```text
_pr92Schema7AtomicAttachmentSubmitExpression(...)
→ _pr92Schema21ValidatedClickBoundaryArm(...)
→ _pr92Schema7BaseAtomicAttachmentSubmitExpression(...)
```

## Preserved submit boundary

The final schema-21 contract is unchanged:

- schema-7 attachment evidence and deadline checks run first;
- the Send button is revalidated in the same page expression;
- the unique schema-20 arm marker is inserted exactly once;
- the marker is immediately before `button.click()`;
- no await or page-task boundary exists between marker and click;
- pre-validation arming remains impossible;
- the debugger acknowledgement after the potentially writing Runtime.evaluate is
  still not awaited;
- network observation remains the post-submit authority.

Schema 20's early-marker helper remains historical/characterization code but is
not production composition.

## Assembly

The write domain now loads:

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_protected_submit_expression.js
→ service_worker_attachment_evidence.js
```

All schema files have loaded before the explicit owner is installed. Runtime
consumers in schema-7 resolve the public builder dynamically at call time.

## Static target

```text
_pr92Schema7AtomicAttachmentSubmitExpression public definitions = 1
_pr92Schema7AtomicAttachmentSubmitExpression runtime assignments = 0
_pr92Schema20PriorAtomicAttachmentSubmitExpression aliases = 0
```

## Out of scope

PR15.35 does not consolidate:

- `_pr92CreateTurnContext`, which has later schema26/27/28 diagnostic owners;
- `isConversationWrite`, whose base predicate is still used explicitly by
  schema29 request-body correlation;
- raw mouse/Enter submission primitives;
- ordinary-text `sendCommand` identity observation.

Those remain separate ownership problems.

Tracking: #107
