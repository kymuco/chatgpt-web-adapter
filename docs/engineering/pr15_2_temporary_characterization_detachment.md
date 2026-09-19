# PR15.2 — Detach Temporary Characterization from Ordinary Runtime

Status: implementation candidate  
Base: `82156189b9465f6f2abd3f2864b99f967df0d771`  
Tracking: #107  
Pull request: #110

## Why this slice exists

PR15.1 introduced explicit diagnostic dispatch and ordinary-turn observer composition.
The next inventory pass found a closed PR8.7 Temporary characterization chain still
participating in ordinary `executeNativeTurn` composition:

```text
temporary_chat
→ state_semantics
→ ax_semantics
→ semantic_notice
→ turn_probe
→ history_probe
→ manual_ground_truth
→ route_reopen
```

Seven modules in that chain owned `executeNativeTurn`. Ordinary product turns passed
through those historical research layers even when no Temporary characterization was
requested.

PR15.2 removes that ownership.

## New ownership

The entire cluster has one explicit diagnostic owner:

```text
temporary-characterization
```

It recognizes only the historical characterization flags:

- `probeTemporaryMode`;
- `characterizeTemporaryTurn`;
- `probeTemporaryHistoryPresence`;
- `characterizeManualTemporaryGroundTruth`;
- `probeTemporaryRouteReopen`.

No characterization module redefines `executeNativeTurn`.

## Historical precedence is preserved

The previous wrapper stack implied an outer-to-inner precedence for conflicting flags.
The explicit handler keeps that order deliberately:

```text
route reopen
→ manual ground truth
→ history
→ turn
→ mode
```

This preserves which existing validation surface owns an invalid multi-flag request
rather than relying on import order.

## Mode-probe composition

Mode characterization remains composed from the same implementation layers:

```text
base isolated mode probe
+ aria-action snapshot semantics
+ Accessibility Tree snapshot semantics
+ semantic notice / mode-marker observation
```

The state and semantic layers continue to modify the bounded snapshot implementation;
they no longer own turn dispatch.

AX capture is now explicit around the base mode-probe call and still exports
`axBefore`, `axAfter`, and the final
`temporaryStateSemantics = accessibility_tree_v1` marker.

## Writeful research probes

"Diagnostic" does not mean "no write."

Two historical characterization actions can intentionally perform a product write:

- `characterizeTemporaryTurn` — one disposable, explicitly acknowledged risk probe;
- `characterizeManualTemporaryGroundTruth` — one human-prepared Temporary smoke turn.

Their write authority remains local to those probe implementations. They do not enter
the ordinary product runtime, do not gain retry authority, and do not become production
Temporary semantics.

The other Temporary characterization actions remain bounded zero-write probes.

## Production Temporary is untouched

PR15.2 does not modify the PR8.13 production Temporary lifecycle:

- `service_worker_temporary_chat_production_pr8_13.js`;
- `service_worker_temporary_session_identity_pr8_13.js`;
- `service_worker_temporary_fresh_identity_flush_pr8_13.js`;
- `service_worker_temporary_startup_readiness_pr8_13_2.js`.

The structural rule is:

```text
historical characterization
!= production Temporary lifecycle
```

## Deterministic proof

The PR adds architecture and behavior tests that prove:

- seven displaced characterization modules no longer redefine
  `executeNativeTurn`;
- one named handler owns Temporary characterization dispatch;
- ordinary requests are not claimed by that handler;
- every characterization flag routes to its exact implementation;
- multi-flag routing keeps historical outer-wrapper precedence;
- writeful probes retain explicit acknowledgement / human-confirmation guards;
- PR8.13 production Temporary imports remain present and separate.

Existing probe-specific Python tests continue to validate their public serialization
and result parsing.

## Provider sequencing consequence

PR15.0 already required provider #2 to wait until ChatGPT was consolidated. PR15.1
made additional historical ownership visible, so the previous fixed label
"PR15.2 provider proof" was premature.

The sequence is now evidence-driven:

```text
PR15.0 inventory
→ PR15.1 explicit composition foundation
→ PR15.2 detach Temporary characterization
→ remaining ChatGPT consolidation slices
→ provider architecture proof with minimal DeepSeek support
```

The provider proof remains required, but its PR number is intentionally not frozen
until the ChatGPT consolidation exit criteria are met.

## Acceptance boundary

PR15.2 is accepted when:

```text
Temporary characterization executeNativeTurn owners = 0
+
explicit Temporary characterization owners = 1
+
historical routing precedence preserved
+
probe-specific behavior tests pass
+
PR8.13 production Temporary lifecycle unchanged
+
full supported OS / Python / installed-wheel CI passes
```

No new live product characterization is required for this structural migration. The PR
does not claim new Temporary behavior; it moves already-existing research actions out
of ordinary runtime dispatch.
