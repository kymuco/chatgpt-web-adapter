# CWA post-0.3 product generation

_Status: PR10.0 working contract_

CWA 0.3.0 is the released baseline for the next product generation.

```text
release  v0.3.0
main     112a47e3c586d0720e4be85e43e7e793edb9cfc6
```

The PR10 line should extend the released product-runtime contract without reopening
already-proven browser-owned write/finality foundations or silently promoting
experimental browserless behavior.

## Product terminology

The ChatGPT product increasingly presents external integrations as Apps and Plugins,
while CWA 0.3 retains the compatibility capability name `TOOLS_CONNECTORS`.
PR10 documentation therefore uses **app/connector** for the user-visible product
surface without renaming the released capability identifier inside this milestone.

## PR10.0 — app/connector and required-action lifecycle

### Goal

Expose a structured, privacy-bounded lifecycle when ChatGPT uses a connected app or
connector and when the product requires user action before continuation.

The core invariant is:

```text
product observation
    != product approval
    != connector authorization
    != local/external action authority
    != canonical finality
    != write retry authority
```

CWA reports what the ChatGPT product visibly did or requested. It does not decide
whether an external action should be allowed, and it does not acquire workspace,
filesystem, Git, account, or provider authority from an observation.

### Implemented typed surface

PR10.0 extends the PR9.3 observation union with:

```text
ProductConnectorObservation
ProductRequiredActionLifecycleObservation
```

Connector observations carry a stable `connector_activity_id`, phase, optional
connector identity, optional operation, optional correlated action id, sequence,
and timing evidence. Required-action lifecycle observations carry an explicit
`action_id`, `action_type`, optional connector correlation, phase, sequence, and
timing evidence.

Supported phases are:

- `OBSERVED`
- `STARTED`
- `UPDATED`
- `COMPLETED`
- `FAILED`

`OBSERVED` is intentionally weaker than a lifecycle. It is used when the product
provides explicit connector identity on one product message but does not provide a
stable cross-message activity id. CWA must not invent a lifecycle from message order.

The PR9.3 legacy `product_required_action_observed` point event remains compatible.
When the event also carries an explicit `action_id`, PR10.0 may materialize the
stronger typed required-action value without changing approval authority.

### Correlation rule

CWA must not pair request/result/action events merely because they are adjacent,
share a label, have similar tool names, or appear in one turn. Lifecycle correlation
requires an explicit stable identifier supplied by the observed product surface.
Conflicting reuse of one stable identifier fails closed.

Connector display names are descriptive, not identity-bearing. They may change due
to localization or product presentation without rebinding a stable connector
activity. Connector identity binding uses stable ids/operation evidence rather than
display text.

Once a correlated activity reaches `COMPLETED` or `FAILED`, later evidence cannot
flip the terminal outcome or resume the activity. Conflicting terminal or identity
evidence is dropped and counted rather than repaired heuristically.

### Browser-owned observation overlay

The PR10.0 service-worker overlay inspects only explicit app/connector and
required-action identifiers already present in product message metadata.

It does **not** classify a message as connector activity merely because:

- the message has a tool role;
- `web.run` or another generic tool appears;
- a status/label resembles connector activity;
- an event appears near another tool event.

Without explicit connector/app/plugin identity, the overlay emits no connector
observation. Without an explicit stable activity id, it may emit only point
`OBSERVED` evidence keyed to the current product message, never a fabricated
request/result lifecycle.

### Privacy rule

Structured app/connector observations must never contain raw tool arguments/results,
OAuth tokens, cookies, authorization headers, refresh/access tokens, signed URLs,
provider credentials, private reasoning, raw SSE, arbitrary connector payloads, or
retrieved private connector content.

Only bounded identifiers, safe product display names, operation names, lifecycle
phase, sequence, and timing metadata are eligible for typed observation. Live-gate
reporting additionally strips labels and emits only an explicit safe-key allowlist.

### No-write overlay support proof

Authenticated live characterization must first prove that the currently running
Chrome extension actually contains the PR10.0 observation overlay. The worker
supports a no-write request:

```text
characterizeConnectorObservationSupport = true
```

A valid support response must prove all of the following before a product write is
permitted by the reusable live gate:

```text
connector observation supported             true
schema                                      1
explicit connector identity required        true
explicit lifecycle correlation required     true
generic tool activity implies connector     false
raw connector payload exported              false
observation grants approval authority       false
observation changes canonical finality      false
observation changes retry authority         false
automatic write retry                       false
fallback transport                          null
write performed                             false
```

Any mismatch, stale extension, malformed response, or support-probe failure returns
before runtime assembly and before the product-write path.

### Reusable authenticated live gate

`tools/pr10_0_connector_live_gate.py` is the bounded live characterization entrypoint.
It requires:

- exact Git head supplied through `--expected-head`;
- tracked-only clean working state;
- explicit `--acknowledge-live-write`;
- successful no-write overlay support proof;
- exactly one browser-owned product write;
- no automatic retry and no fallback transport;
- canonical readback finality and exact conversation/message identity;
- no exported private-thought text;
- zero dropped structured-observation events for a passing run.

The default prompt allows only a harmless read-only use of an already-connected
ChatGPT app/plugin and asks the product not to reveal retrieved private content.
The report redacts arbitrary assistant text and exports only two expected marker
responses or `OTHER_RESPONSE_REDACTED`.

A safe/finality pass with no explicit connector evidence is still valuable product
characterization, but it does **not** graduate `TOOLS_CONNECTORS`.

### Capability rule

`TOOLS_CONNECTORS` stays `UNKNOWN` until authenticated live product evidence proves
that the browser-owned observation channel exposes connector evidence with the
required privacy, correlation, finality, and no-retry boundaries. A calculator or
generic tool proof is insufficient because connector/app semantics are a broader
capability class.

Deterministic tests are necessary but not sufficient for capability graduation.
PR10.0 may close with `TOOLS_CONNECTORS=UNKNOWN` if the authenticated product does
not expose qualifying explicit connector evidence; that unsupported boundary must
be recorded rather than guessed around.

### Acceptance

PR10.0 is complete only when:

1. deterministic collector/runtime tests pass across the supported Python matrix;
2. legacy PR9.3 observation semantics remain compatible;
3. collector defects remain non-authoritative and cannot invalidate/retry a write;
4. privacy regressions are fail-closed;
5. the loaded worker proves the PR10.0 observation schema with a no-write support gate;
6. browser-owned app/connector event shape is characterized without exporting raw
   credentials, arguments, results, retrieved private content, or private reasoning;
7. one bounded authenticated live gate confirms the implemented event contract, or
   the capability remains explicitly `UNKNOWN` with the unsupported evidence recorded;
8. canonical readback/finality remains independent of connector/action observations;
9. exact installed-wheel smoke remains green before merge.

## Later PR10 milestones

Do not freeze later milestone contents before PR10.0 live evidence. Candidate areas
include generated/downloadable product artifacts, compatibility-drift hardening, and
real downstream adoption feedback. Each should remain a vertical product milestone,
not a sequence of verification-only micro-PRs.
