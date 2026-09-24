# PR15.29 — Consolidate submit authority ownership

## Purpose

Continue #107 by removing the remaining source-order ownership chain around
`submitOfficialPageTurn`.

Before this slice, five shipping layers captured and reassigned the same hook:

```text
service_worker_temporary_product.js
service_worker_rich_input_deadline_repair_pr9_2.js
service_worker_rich_input_closure_repair_pr9_2.js
service_worker_rich_input_schema7_core_pr9_2.js
service_worker_text_submit_commit_hardening_pr11_3.js
```

Given the current runtime assembly, the effective historical outer-to-inner call
graph was:

```text
PR11.3 ordinary-text commit hardening
→ schema7 atomic rich-input submit
→ closure repair
→ deadline repair
→ Temporary submit authority
→ base submit
```

This boundary is especially sensitive because it is the browser-owned write /
commit point. PR15.29 changes ownership only; it does not redefine which path may
submit or what counts as an ambiguous post-commit outcome.

## New ownership

The base implementation in `service_worker.js` is now private:

```text
_cwaBaseSubmitOfficialPageTurn
```

The historical owners expose explicit helpers:

```text
_pr813SubmitOfficialPageTurn(debuggee, timeoutMs, next)
_pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry(debuggee, timeoutMs, next)
_pr92ClosurePageDeadlineGuardedSubmit(debuggee, timeoutMs, next)
_pr92Schema7AtomicAttachmentSubmit(debuggee, timeoutMs, next)
_pr113SubmitOfficialTextWithoutPostCommitRetry(debuggee, timeoutMs, next)
```

The sole public production owner is:

```text
service_worker_submit_authority.js
```

with explicit composition:

```text
text(
  schema7(
    closure(
      deadline(
        temporary(
          base
        )
      )
    )
  )
)
```

## Preserved path semantics

### Ordinary text

PR11.3 remains the outer ordinary-text authority.

When neither rich-input nor Temporary context is active it still owns the actual
submit decision, including:

- mouse release as the click protected-write boundary;
- fail-closed ambiguous mouse-release outcome;
- Enter fallback only before a click commit boundary has been attempted;
- keyDown as the keyboard protected-write boundary;
- best-effort keyUp after a committed keyDown.

The lower chain is not consulted for the ordinary-text path.

### Rich input

When rich-input context is active PR11.3 delegates. Schema7 remains the active
rich-input submit authority and preserves:

- final page-owned attachment validation;
- atomic validation + click in one page expression;
- page-side deadline protection;
- no debugger-ACK wait after a potentially committed click;
- Network request observation as post-submit proof.

Schema7 only delegates when no rich-input context is active, preserving the
historical bypass of older closure/deadline rich paths once schema7 is available.

### Closure / deadline compatibility

Closure and deadline helpers retain their exact guards and historical behavior.
They remain explicit lower compatibility layers instead of import-time hook
owners. No raw mouse/Enter path is newly authorized for rich input.

### Temporary

Temporary remains the inner specialized authority reached when ordinary/rich
layers delegate.

Its prewrite proof, startup readiness, live lifecycle/tab binding, and mode
violation handling are unchanged. The helper now receives its historical prior
submit implementation as `next`; in the explicit composition that `next` is
the private base submit, exactly matching the old import-time capture.

### Base

The original send-button-click / bounded Enter fallback implementation remains
unchanged and is now private to the explicit composition.

## Assembly

The new owner is loaded immediately after `service_worker_runtime_write.js`.

At that point:

- Temporary helpers already exist from the observability path loaded by runtime
  tab reconciliation;
- deadline / closure / schema7 / PR11.3 helpers already exist from the write
  domain.

No submit layer mutates `submitOfficialPageTurn` during import.

## Static target

```text
submitOfficialPageTurn public definitions = 1
submitOfficialPageTurn runtime assignments = 0
PriorSubmitOfficialPageTurn aliases        = 0
```

## Regression strategy

Existing rich-input, Temporary, and PR11.3 behavioral regressions remain the
semantic authority.

PR15.29 adds a dedicated architecture regression that verifies:

- one public owner;
- zero submit hook assignments in historical layers;
- zero `PriorSubmitOfficialPageTurn` aliases;
- runtime assembly after all helpers;
- exact historical outer-to-inner ordering;
- executable nested handoff and reverse unwind in Node.

## Acceptance

- exactly one public `submitOfficialPageTurn` owner;
- zero runtime assignments of that hook;
- zero historical submit prior aliases;
- ordinary text commit hardening unchanged;
- rich schema7 atomic-submit authority unchanged;
- closure/deadline compatibility semantics unchanged;
- Temporary prewrite/readiness authority unchanged;
- engineering quality and JavaScript syntax green;
- full Linux/Windows Python 3.10–3.14 matrix green;
- release build and installed-wheel smoke green.
