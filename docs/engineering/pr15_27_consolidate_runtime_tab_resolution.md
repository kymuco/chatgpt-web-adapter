# PR15.27 — Consolidate runtime-tab resolution ownership

## Purpose

Continue #107 by removing the remaining source-order ownership chain around
`ensureRuntimeTab`.

Before this slice, four shipping modules captured and reassigned the same hook:

```text
service_worker_phase_timing_pr8_8.js
service_worker_temporary_product.js
service_worker_retained_conversation_tabs.js
service_worker_rich_input_schema16_repair_pr9_2.js
```

The recursive runtime assembly made the effective historical composition:

```text
schema16 rich deadline
→ retained-conversation routing
→ Temporary routing
→ phase timing
→ base runtime-tab acquisition
```

That order is behaviorally significant. Retained saved-conversation routing may
terminate before the lower Temporary/phase/base path; Temporary routing may
terminate before phase/base; schema16 must remain the outer deadline boundary.

## New ownership

The base implementation in `service_worker.js` is now the private helper:

```text
_cwaBaseEnsureRuntimeTab
```

The four historical owners now expose pure helpers:

```text
_pr92Schema16ResolveRuntimeTabWithinRichDeadline(conversationId, next)
_pr148ResolveRuntimeTab(conversationId, next)
_pr813ResolveRuntimeTab(conversationId, next)
_pr88ResolveRuntimeTabWithPhaseTiming(conversationId, next)
```

The single public production owner is:

```text
service_worker_runtime_tab_resolution.js
```

and explicitly composes:

```text
schema16(retained(temporary(phase(base))))
```

The owner is assembled immediately after `service_worker_runtime_write.js`.
At that point the observability path has already provided phase/Temporary helpers,
and the write domain has already provided retained/schema16 helpers.

## Preserved boundaries

- PR14.8 saved-conversation retained-tab routing is unchanged.
- Fresh normal chat still delegates to the historical base path after detaching a
  conversation-bound legacy pointer.
- Temporary Chat still bypasses retained saved-conversation routing once its live
  turn context exists.
- Temporary continuation identity checks and live-tab authority are unchanged.
- PR9.2 schema16 still bounds the complete rich runtime-tab acquisition with the
  outer rich-input deadline.
- PR8.8 phase timing still observes only paths that historically reached its
  inner layer.
- No new tab creation, navigation, retry, write, or canonical-finality authority
  is introduced.

## Static target

```text
ensureRuntimeTab public definitions = 1
ensureRuntimeTab runtime assignments = 0
PriorEnsureRuntimeTab aliases        = 0
```

## Regression strategy

The PR15.27 regression checks both static ownership and executable composition.
A Node harness supplies pure stub layers and proves the nested handoff order:

```text
enter schema16
→ enter retained
→ enter temporary
→ enter phase
→ base
→ exit phase
→ exit temporary
→ exit retained
→ exit schema16
```

## Acceptance

- exactly one public `ensureRuntimeTab` owner;
- zero runtime assignments of `ensureRuntimeTab`;
- zero historical `PriorEnsureRuntimeTab` aliases;
- exact historical outer-to-inner order preserved;
- retained, Temporary, phase timing, and schema16 tests updated to helper ownership;
- engineering quality and JavaScript syntax green;
- full Linux/Windows Python 3.10–3.14 matrix green;
- release build and installed-wheel smoke green.
