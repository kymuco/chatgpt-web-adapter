# PR15.38 — Consolidate raw submit primitive ownership

## Purpose

Continue #107 by removing source-order replacement from the two raw browser
submit primitives:

```text
clickSendButton(...)
submitWithEnter(...)
```

Historically both names evolved through the same chain:

```text
base CDP primitive
→ PR9.2 deadline-aware wrapper
→ PR9.2 closure guard
```

That behavior is retained, but the stages are now explicit helpers rather than
captured prior bindings.

## Explicit stages

Mouse submit:

```text
_cwaBaseClickSendButton(...)
_pr92ClickSendButtonWithinDeadline(...)
_pr92ClosureRejectRawMouseSubmit(...)
```

Enter submit:

```text
_cwaBaseSubmitWithEnter(...)
_pr92SubmitWithEnterWithinDeadline(...)
_pr92ClosureRejectRawEnterSubmit(...)
```

The sole public production owner is:

```text
service_worker_raw_submit_primitives.js
```

with explicit composition:

```text
clickSendButton(...)
→ _pr92ClosureRejectRawMouseSubmit(...)
→ _pr92ClickSendButtonWithinDeadline(...)
→ _cwaBaseClickSendButton(...)
```

and:

```text
submitWithEnter(...)
→ _pr92ClosureRejectRawEnterSubmit(...)
→ _pr92SubmitWithEnterWithinDeadline(...)
→ _cwaBaseSubmitWithEnter(...)
```

## Preserved rich-input boundary

The closure helpers still fail closed immediately when
`_pr92ActiveRichInputContext !== null`.

Therefore a production rich-input turn never reaches a raw mouse or Enter CDP
submit primitive through the public names.

The deadline-aware rich branches remain available as historical helpers for the
reviewed PR9.2 layer, but they are not reachable through the public raw
primitives while an active rich-input context exists.

## Preserved text-only behavior

With no active rich-input context:

```text
closure helper
→ deadline helper
→ base primitive
```

The deadline helper sees no rich context and delegates directly to the original
base behavior.

The base `_cwaBaseSubmitOfficialPageTurn` still resolves the public
`clickSendButton` and `submitWithEnter` names dynamically at call time, so
the explicit owner remains in the same production path.

## Static target

```text
clickSendButton public definitions = 1
clickSendButton runtime assignments = 0
submitWithEnter public definitions = 1
submitWithEnter runtime assignments = 0
_pr92DeadlineRepairPriorClickSendButton aliases = 0
_pr92DeadlineRepairPriorSubmitWithEnter aliases = 0
_pr92ClosurePriorClickSendButton aliases = 0
_pr92ClosurePriorSubmitWithEnter aliases = 0
```

## Assembly

The write domain now loads:

```text
service_worker_rich_input_pr9_2.js
→ service_worker_rich_input_deadline_repair_pr9_2.js
→ service_worker_rich_input_closure_repair_pr9_2.js
→ service_worker_raw_submit_primitives.js
→ service_worker_rich_input_schema7_repair_pr9_2.js
```

All helpers are defined before the public owner is installed.

## Authority

PR15.38 changes ownership only.

It does not add:

- rich-input raw-submit authority;
- retry authority;
- a second submit path after an ambiguous write boundary;
- request classification;
- navigation;
- canonical finality.

## Out of scope

Still open after this slice:

- `sendCommand` ownership (base → hotfix → ordinary-text identity);
- the smaller `connectNativeBridge` product-state wrapper.

Tracking: #107
