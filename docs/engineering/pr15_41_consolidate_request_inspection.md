# PR15.41 — Consolidate request-inspection ownership

## Purpose

Continue #107 by removing source-order replacement from the shared request
correlation inspector:

```text
_pr92Schema29InspectRequestPostData(...)
```

The historical production chain was:

```text
schema29 request-correlation inspector
→ request-text-shape compatibility
→ browser-indent compatibility
```

Both compatibility layers captured the previous public binding and reassigned
the same global name.

## Explicit stages

Schema29 remains the sole request-correlation authority:

```text
_pr92Schema29BaseInspectRequestPostData(...)
```

Request-text-shape compatibility becomes:

```text
_cwaRequestTextShapeInspect(...)
→ normalize bounded textual representations
→ _pr92Schema29BaseInspectRequestPostData(...)
→ persist safe request-shape fingerprint
```

Browser-indent compatibility becomes:

```text
_cwaBrowserIndentInspect(...)
→ _cwaRequestTextShapeInspect(original evidence)
→ if already matched or rich turn: return
→ otherwise test the narrow line-leading indentation equivalence
→ _cwaRequestTextShapeInspect(canonicalized local copy)
→ persist safe indent fingerprint
```

The sole public production owner is:

```text
service_worker_request_inspection.js
```

with final call graph:

```text
_pr92Schema29InspectRequestPostData(...)
→ _cwaBrowserIndentInspect(...)
→ _cwaRequestTextShapeInspect(...)
→ _pr92Schema29BaseInspectRequestPostData(...)
```

## Preserved authority boundary

Schema29 still decides all request-correlation authority:

- request JSON validity;
- `action === "next"`;
- exact conversation identity semantics;
- user-message identity classification;
- exact text equality after bounded compatibility normalization;
- attachment evidence/count agreement;
- logical message identity.

Neither compatibility layer gains authority to classify a request independently.

## Preserved request-text-shape compatibility

Only already-textual representations are normalized:

- object parts carrying a string `text` field become string parts;
- `content.text` is used only when no textual parts exist;
- attachment-pointer objects remain attachment evidence;
- unknown objects remain untouched.

The original network request is never mutated.

The safe fingerprint still receives the original evidence plus the result of the
schema29 base inspection and cannot expose raw prompt/request data.

## Preserved browser-indent compatibility

The indentation layer still performs its historical two-pass behavior.

First pass:

```text
_cwaRequestTextShapeInspect(original postData)
```

Only when that fails, attachments are zero, and exactly one ordinary user text
candidate is eligible, the narrow equivalence is considered:

- expected ASCII space;
- observed U+00A0 NBSP or U+202F NNBSP;
- mismatch occurs only while still inside line-leading indentation;
- total string length is identical;
- every other code unit matches exactly.

If eligible, a local correlation copy is canonicalized and the exact same
request-text-shape helper is called again.

This preserves both request-shape normalization and its safe fingerprint on the
retry path.

## Assembly

The write domain now loads:

```text
service_worker_request_text_shape_compat.js
→ service_worker_browser_indent_compat.js
→ service_worker_request_inspection.js
→ service_worker_ui_compat_pr11_7.js
→ ...
→ service_worker_ordinary_text_identity_authority.js
```

Ordinary-text identity therefore continues consuming the final public inspector.

## Static target

```text
_pr92Schema29InspectRequestPostData public definitions = 1
_pr92Schema29InspectRequestPostData runtime assignments = 0
_cwaRequestTextShapePriorSchema29Inspect aliases = 0
_cwaBrowserIndentPriorSchema29Inspect aliases = 0
```

## Authority

PR15.41 changes ownership/composition only.

It does not add:

- fuzzy request matching;
- attachment request authority;
- route identity authority;
- retry/write authority;
- navigation authority;
- canonical finality.

## Remaining confirmed ownership inventory

After this slice the request-inspection cluster is removed from the confirmed
PR15.40 inventory.

Still confirmed:

```text
runtime lifecycle / tab state:
  executeNativeTurn
  executeOfficialPageTurn
  storedRuntimeTabId

recovery / deadline:
  waitForTabComplete
  _pr811ReloadRuntimeTabAndWait
  _pr811MaybeRecoverStaleRuntimeUi

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

The final architecture-reset ownership closure still requires a static
no-reassignment gate over the shipping worker surface after these remaining
clusters are consolidated.

Tracking: #107
