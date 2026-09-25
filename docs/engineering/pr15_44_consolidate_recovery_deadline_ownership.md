# PR15.44 — Consolidate recovery/deadline ownership

## Purpose

Continue #107 by removing source-order replacement from the remaining
recovery/deadline hook trio:

```text
waitForTabComplete(...)
_pr811ReloadRuntimeTabAndWait(...)
_pr811MaybeRecoverStaleRuntimeUi(...)
```

Historically PR9.2 captured the already-loaded base/recovery bindings and
reassigned all three names so rich-input turns could share one outer deadline
and stage attachments only after stale-UI recovery.

PR15.44 keeps that behavior but makes the composition explicit.

## Explicit base helpers

The base worker tab-completion primitive is now:

```text
_cwaBaseWaitForTabComplete(...)
```

PR8.11 recovery exposes immutable helpers:

```text
_pr811BaseReloadRuntimeTabAndWait(...)
_pr811BaseMaybeRecoverStaleRuntimeUi(...)
```

The base stale-UI recovery helper deliberately continues resolving the public
reload hook dynamically:

```text
_pr811BaseMaybeRecoverStaleRuntimeUi(...)
→ _pr811ReloadRuntimeTabAndWait(...)
```

That edge is required so an active PR9.2 turn still receives deadline-bounded
reload behavior.

## Explicit PR9.2 helpers

PR9.2 now defines pure named helpers rather than replacing globals.

Tab load:

```text
_pr92WaitForTabCompleteWithinTurn(...)
→ no active turn: _cwaBaseWaitForTabComplete(...)
→ active turn: _cwaBaseWaitForTabComplete(... capped timeout ...)
```

Stale-UI reload:

```text
_pr92ReloadRuntimeTabWithinTurn(...)
→ no active turn: _pr811BaseReloadRuntimeTabAndWait(...)
→ active turn: existing bounded reload/verify implementation
```

Recovery then attachment staging:

```text
_pr92RecoverThenStage(message)
→ _pr811BaseMaybeRecoverStaleRuntimeUi(message)
→ if rich turn: stage attachments
→ rewrite message.timeoutMs to remaining outer budget
```

## Sole public owner

The final public names are owned by:

```text
service_worker_recovery_deadline.js
```

Call graph:

```text
waitForTabComplete(...)
→ _pr92WaitForTabCompleteWithinTurn(...)
→ _cwaBaseWaitForTabComplete(...)
```

```text
_pr811ReloadRuntimeTabAndWait(...)
→ _pr92ReloadRuntimeTabWithinTurn(...)
→ _pr811BaseReloadRuntimeTabAndWait(...)
```

```text
_pr811MaybeRecoverStaleRuntimeUi(...)
→ _pr92RecoverThenStage(...)
→ _pr811BaseMaybeRecoverStaleRuntimeUi(...)
→ _pr811ReloadRuntimeTabAndWait(...)
```

The last public reload edge intentionally re-enters the final owner so recovery
inside an active rich-input turn cannot bypass the shared outer deadline.

## Preserved deadline semantics

PR9.2 still owns one total rich-turn deadline.

The following behavior is unchanged:

- tab-load waits are capped to remaining turn time;
- stale-UI reload uses the smaller of the historical 45s cap and remaining turn
  time;
- reload completion is verified against the expected conversation route;
- timeout is checked again after reload and before attachment staging;
- attachment staging happens only after stale-UI recovery;
- the downstream page turn receives only the remaining outer budget.

Text-only / non-PR9.2 calls keep the original base timeout behavior.

## Preserved recovery authority

No retry is introduced.

Stale-UI recovery remains conditional on fresh canonical completion evidence and
visible generation-control state. The recovery layer may reload the already-owned
runtime tab, but it does not gain a second product submit/write attempt.

The current official page-turn terminal remains unchanged.

## Support contract

`PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE` now checks the immutable base helpers
directly instead of checking captured-prior aliases.

This preserves the support gate while removing import-order ownership.

## Assembly

The write domain now begins:

```text
service_worker_retained_conversation_tabs.js
→ service_worker_rich_input_pr9_2.js
→ service_worker_recovery_deadline.js
→ service_worker_rich_input_deadline_repair_pr9_2.js
→ ...
```

The owner is installed after PR9.2 defines its helpers and before later rich
deadline/closure/schema layers load.

## Static target

```text
waitForTabComplete public definitions = 1
waitForTabComplete runtime assignments = 0
_pr92PriorWaitForTabComplete aliases = 0

_pr811ReloadRuntimeTabAndWait public definitions = 1
_pr811ReloadRuntimeTabAndWait runtime assignments = 0
_pr92PriorReloadRuntimeTabAndWait aliases = 0

_pr811MaybeRecoverStaleRuntimeUi public definitions = 1
_pr811MaybeRecoverStaleRuntimeUi runtime assignments = 0
_pr92PriorMaybeRecoverStaleRuntimeUi aliases = 0
```

## Authority

PR15.44 changes ownership/composition only.

It does not add or widen:

- runtime-tab creation authority;
- Browser Authority;
- attachment-selection authority;
- submit/write authority;
- automatic retry authority;
- navigation authority;
- canonical finality.

## Remaining confirmed ownership inventory

After PR15.44 the recovery/deadline cluster is removed from the confirmed PR15.40
inventory.

Still confirmed:

```text
rich-input schema hooks:
  _pr92ClosureReadPageOwnedAttachmentEvidence
  waitForSendButtonPoint
  _pr92Schema10RequireOfficialCleanComposerBeforeStaging
  _pr92Schema12ObservePostStageAttachmentEvidence
  _pr92ReadDirtyAttachmentFence
  _pr92Schema17OptionalPostWrite

Temporary state:
  _pr87TemporaryControlSnapshotExpression
```

Final closure still requires consolidation of those names plus a static
no-reassignment gate over the shipping worker surface.

Tracking: #107


## Follow-up ownership note

PR15.45 classifies the six remaining rich-input schema hooks into independent
semantic clusters and consolidates the attachment/composer-readiness cluster:
`_pr92ClosureReadPageOwnedAttachmentEvidence`,
`_pr92Schema10RequireOfficialCleanComposerBeforeStaging`, and
`_pr92Schema12ObservePostStageAttachmentEvidence`.
