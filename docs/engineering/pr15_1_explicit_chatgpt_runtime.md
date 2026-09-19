# PR15.1 — Explicit ChatGPT Runtime Ownership

Status: implementation candidate  
Base: `7946f5b570a9020756ac9995a7d7a61def994095`  
Tracking: #107  
Pull request: #109

## Goal

Reduce production behavior that depends on import-order replacement of
`executeNativeTurn`.

This slice does not add product capability and does not rewrite Browser Authority,
finality, retry policy, Temporary Chat semantics, or rich-input behavior.

The change establishes two explicit composition surfaces:

```text
diagnostic request
→ exactly one named diagnostic handler

ordinary runtime request
→ ordered observers
→ exactly one executeNativeTurn call
```

## Diagnostic ownership

The dispatcher rejects duplicate handler names and rejects a request claimed by more
than one handler.

Migrated diagnostic ownership:

- connector observation / required-action support;
- retained route identity;
- retained picker forensics;
- instant failure forensics + popup-subtree augmentation.

The displaced `executeNativeTurn` wrappers are removed from those modules.

Instant failure evidence capture remains separate from diagnostic dispatch. Existing
`locateAndFocusComposer` evidence hooks remain active; only their characterization RPC
ownership moved.

## Ordinary-turn observers

`service_worker.js` now owns a named observer registry around one ordinary
`executeNativeTurn` call.

Registration order models historical wrapper nesting:

```text
last registered observer before
→ ...
→ first registered observer before
→ executeNativeTurn
→ first registered observer afterSuccess
→ ...
→ last registered observer afterSuccess
→ cleanup inner-to-outer
```

Observer cleanup cannot replace the product-turn outcome.

The first migrated ordinary-turn observer is provisioning observability from
`service_worker_observability.js`.

That module still exports the same bounded metadata:

- runtime tab preexisting;
- runtime tab created for turn;
- tab active after;
- tab activated during turn;
- foreground activation observed.

It no longer owns an `executeNativeTurn` override.

## Deliberate non-migrations

Phase timing and post-answer tail timing still wrap `executeNativeTurn` in this PR.

They are not outermost. Moving either directly into the central observer pipeline would
change its nesting relative to Temporary, early-completion, streaming and other active
runtime layers, changing the measured interval.

Those layers require a separate adjacent-cluster migration.

Rich-input schema lineage is also out of scope for this slice.

## Behavioral proof

`tests/test_native_turn_dispatch_behavior.py` executes the extracted dispatcher in
Node and proves:

- outer-before / inner-before / core / inner-after / outer-after order;
- inner-to-outer cleanup;
- diagnostic requests bypass ordinary observers and the product core;
- observer cleanup failure cannot replace the original product-turn failure.

Source contracts additionally prove that migrated modules no longer redefine
`executeNativeTurn`.

## Acceptance boundary

PR15.1 is accepted only if:

```text
migrated diagnostic owners no longer wrap executeNativeTurn
+
provisioning observability no longer wraps executeNativeTurn
+
ordinary runtime reaches one explicit observer pipeline
+
deterministic behavior tests pass
+
full supported Python / OS / installed-wheel CI passes
```

No live product write is required for this structural slice because no authority,
submission, canonical-finality, retry, or product-mutation rule is intentionally
changed.
