# PR15.6 — Picker Trigger Diagnostic Ownership

Status: implementation candidate  
Base: `6f595f516f0c90b7f3342abfbbdbe9483dfd14ad`

## Goal

Remove a residual `executeNativeTurn` owner left behind after instant-failure
forensics moved to explicit diagnostic dispatch.

The picker-trigger timeline layer still wrapped every ordinary turn only to augment:

- `characterizeInstantFailureForensicsSupport`;
- `characterizeInstantFailureForensicsRecord`.

Those requests are now claimed by the explicit `instant-failure-forensics`
diagnostic owner before ordinary `executeNativeTurn` dispatch. The historical
wrapper therefore no longer owned reachable diagnostic behavior, but it remained
in the ordinary runtime chain.

## Ownership change

The existing `instant-failure-forensics` owner now also returns the picker-trigger
support and persisted timeline fields.

`service_worker_picker_trigger_persistence_pr8_8.js` retains only the failure-path
persistence hook and stored-record helper. It no longer redefines
`executeNativeTurn`.

The stale `_pr88TriggerPriorExecuteNativeTurn` capture is removed from
`service_worker_picker_trigger_identity_pr8_8.js`.

## Preserved boundaries

This slice does not change:

- picker selection or click behavior;
- failure-path timeline capture;
- Browser Authority;
- prompt insertion or submit;
- retry/finality semantics;
- Instant selection semantics;
- persisted timeline redaction.

The record path still requires exact lease matching and never exports the private
lease id.

## Acceptance

```text
picker-trigger executeNativeTurn owners = 0
+
picker-trigger PriorExecuteNativeTurn aliases = 0
+
instant-failure-forensics explicit owners = 1
+
support augmentation preserved
+
record augmentation + lease redaction preserved
+
full CI / installed-wheel gates green
```
