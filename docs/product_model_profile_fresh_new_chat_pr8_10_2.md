# PR8.10.2 — Fresh New-Chat Initial-Mode Acquisition, Bounded Readiness Wait and Strict Profile-Selection Repair

Status: IMPLEMENTED — fresh-new-chat live repair gate pending.

## Trigger

The new standalone CLI exposed a production boundary that the original PR8.10 live gate did not cover.

Fresh new-chat invocation with the standalone default `DEEP -> HIGH` failed closed:

```text
cwa send "Reply with exactly: CWA_STANDALONE_HIGH_OK"
error: PR8_10_MODEL_PROFILE_INITIAL_MODE_NOT_PROVEN
```

The same HIGH requirement on an existing conversation succeeded:

```text
cwa send "Reply with exactly: CWA_EXISTING_HIGH_OK" --conversation <existing-conversation-id>
CWA_EXISTING_HIGH_OK
```

This isolates the observed failure to fresh/new-chat initial-mode acquisition rather than the proven HIGH slider selection or canonical response path.

## Why PR8.10 missed it

PR8.10's original production gate proved the bounded transition sequence:

```text
FAST -> DEEP -> BALANCED
INSTANT -> INSTANT -> HIGH -> MEDIUM
```

The selector therefore had live evidence for transitions after a current mode was already observable, but no independent fresh-new-chat initial-state gate.

The production selector used one immediate `_pr88InstantSelectedModeSnapshot()` before selection. A fresh runtime tab can exist before the composer-local model control is ready to provide a unique selected-mode proof, causing `PR8_10_MODEL_PROFILE_INITIAL_MODE_NOT_PROVEN` before prompt insertion.

## Repair

PR8.10.2 changes only initial-mode acquisition.

The selector now performs a bounded read-only acquisition through the already-existing PR8.8 primitive:

```text
_pr88InstantWaitForSelectedMode(debuggee, 8000)
```

The helper polls the same bounded selected-mode snapshot and returns immediately once a selected mode is proven. Warm/existing conversations therefore retain the fast path while fresh tabs receive a bounded readiness window.

No model target, slider actuation, prompt insertion, submit path, write authority, retry behavior, or canonical readback contract is changed.

## Strict boundaries

A profile-required turn proceeds only when the acquired initial mode is both:

1. uniquely proven by the existing composer-local observation contract; and
2. one of the three PR8.10 supported states: `INSTANT`, `MEDIUM`, or `HIGH`.

If no mode becomes proven before the bounded timeout, the turn still fails before the selection/write boundary. The error now carries bounded diagnostic classification:

```text
PR8_10_MODEL_PROFILE_INITIAL_MODE_NOT_PROVEN:<proofKind>:composer_ready=<bool>:candidate_count=<n>
```

Possible existing PR8.8 proof kinds include `composer_missing`, `no_mode_control`, `ambiguous_mode_controls`, and `probe_failed`.

If the UI proves a mode outside the three-state PR8.10 contract, the selector fails separately:

```text
PR8_10_MODEL_PROFILE_INITIAL_MODE_UNSUPPORTED:<mode>
```

PR8.10.2 does not attempt to reinterpret `EXTRA_HIGH`, Pro variants, Auto-like unclassified states, or any other product mode as part of the proven three-position slider.

## Added success evidence

Successful selection records now include bounded initial-acquisition evidence:

- `initialModeAcquisitionTimeoutMs`;
- `initialModeAcquisitionElapsedMs`;
- `initialModeComposerReady`;
- `selectedModeBeforeProofKind`;
- `selectedModeBeforeCandidateCount`;
- `selectedModeBeforeNearestDistancePx`.

The model-profile support characterization also reports `boundedInitialModeAcquisition = true` and the configured acquisition timeout.

## Required live repair gate

Implementation is not sufficient to close PR8.10.2. The missing production case must be exercised directly.

### Gate A — fresh new chat

```text
cwa send "Reply with exactly: CWA_PR8_10_2_FRESH_HIGH_OK"
```

Required result:

```text
CWA_PR8_10_2_FRESH_HIGH_OK
```

and selection evidence must establish:

- requested mode `HIGH`;
- initial mode proven after bounded acquisition;
- selected mode after = `HIGH`;
- selected mode after proven = true;
- conversation write before selection = false;
- exactly one product write;
- no automatic retry.

### Gate B — existing-conversation regression

```text
cwa send "Reply with exactly: CWA_PR8_10_2_EXISTING_HIGH_OK" --conversation <existing-conversation-id>
```

Required result:

```text
CWA_PR8_10_2_EXISTING_HIGH_OK
```

The existing-conversation path must remain successful and preserve the same strict prewrite proof.

## Claim boundary

Until Gate A passes, do not claim that PR8.10.2 fixes fresh-new-chat profile selection in production.

Current claim is narrower:

> PR8.10.2 implements bounded fresh-chat initial-mode acquisition while preserving PR8.10's fail-closed three-state selection contract; production repair remains pending the explicit fresh-new-chat live gate.
