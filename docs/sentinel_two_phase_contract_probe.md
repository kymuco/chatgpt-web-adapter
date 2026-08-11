# Two-Phase Sentinel Chat-Requirements Contract Probe

PR7.11b freezes live-observed structure for the current ChatGPT web Sentinel
requirements flow without solving, replaying, or finalizing browser challenges.

## Live-observed sequence

A successful browser turn observed on 2026-08-09 used this ordering:

```text
POST /backend-api/f/conversation/prepare
POST /backend-api/sentinel/chat-requirements/prepare
POST /backend-api/sentinel/chat-requirements/finalize
POST /backend-api/f/conversation
```

UI/autocomplete/list/telemetry requests may interleave with this sequence and are
not treated as write-contract requirements.

The current production adapter still uses the legacy single-step
`/backend-api/sentinel/chat-requirements` path. PR7.11b does not change that
production path; it records the current two-phase evidence so a later integration
PR can replace it deliberately.

## Observed request/response shapes

Sentinel prepare request:

```json
{
  "p": "<opaque-or-null>"
}
```

Sentinel prepare response top-level keys:

```text
persona
prepare_token
turnstile
proofofwork
so
```

Observed nested shape:

```text
turnstile:
  required
  dx

proofofwork:
  required
  seed
  difficulty

so:
  required
  collector_dx
  snapshot_dx
```

Sentinel finalize request top-level keys:

```text
prepare_token
proofofwork
turnstile
```

Sentinel finalize response top-level keys:

```text
persona
token
expire_after
expire_at
```

The observed `prepare_token`, challenge descriptors, challenge responses, and final
requirements token are turn-scoped evidence. PR7.11b deliberately does not claim
which values are cryptographically bound to one another beyond the observed
request/response flow.

## Probe boundary

`examples/probe_sentinel_requirements_contract.py` performs only the Sentinel
`/prepare` request. It stops before:

- Sentinel `/finalize`;
- any Turnstile replay or challenge solving;
- any final `/f/conversation` write.

The report records only status, key names, presence booleans, and required flags.
It never records:

- `prepare_token`;
- `turnstile.dx`;
- PoW seed/difficulty values;
- `so.collector_dx` or `so.snapshot_dx`;
- raw request/response bodies;
- final requirements tokens.

When generic HTTP debug tracing is enabled, the prepare request is executed under
the existing execution-context-local trace suppression boundary and replaced with
one structural `sentinel-prepare` trace.

## Verdicts

`TWO_PHASE_SENTINEL_PREPARE_OBSERVED`

: HTTP success plus a non-empty observed `persona` and `prepare_token`, with
  every live-observed top-level and nested structural key still present in the
  `turnstile`, `proofofwork`, and `so` blocks. Additional server keys are allowed.
  Challenge `required` booleans are recorded but are not frozen into the pass
  criterion because server policy may vary by session or risk context.

`SENTINEL_PREPARE_PARTIAL_SHAPE`

: HTTP success but one or more observed structural fields are absent.

`SENTINEL_PREPARE_REJECTED`

: non-successful Sentinel prepare request.

## Governance

The following remain explicit non-goals for PR7.11b:

- Turnstile solving or bypass;
- browser challenge replay;
- production send-path integration;
- treating any challenge value as independently reusable;
- claiming the legacy single-step endpoint is universally removed.

The current evidence does establish that a successful current browser write uses
the two-phase `prepare -> finalize` Sentinel flow, while the adapter's legacy
single-step flow is not live-validated for that prepared-write contract.
