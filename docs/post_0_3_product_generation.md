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

Expose structured, privacy-bounded evidence when ChatGPT uses a connected app or
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
ProductRequiredActionSurfaceObservation
```

Connector observations carry a stable `connector_activity_id`, phase, optional
connector identity, optional operation, optional correlated action id, sequence,
and timing evidence. Correlated required-action lifecycle observations carry an
explicit `action_id`, `action_type`, optional connector correlation, phase, sequence,
and timing evidence.

`ProductRequiredActionSurfaceObservation` is deliberately weaker. It materializes a
visible product authorization affordance as `REQUIRED_ACTION / OBSERVED` when CWA
can prove the connector name plus both connect and dismiss controls, but the product
surface does not expose a proven stable `action_id`. The type intentionally has no
`action_id` field and cannot acquire lifecycle or approval authority by implication.

Supported phases for correlated lifecycle evidence are:

- `OBSERVED`
- `STARTED`
- `UPDATED`
- `COMPLETED`
- `FAILED`

`OBSERVED` is intentionally weaker than a lifecycle. It is used when the product
provides explicit point evidence but does not provide a stable cross-message
correlation id. CWA must not invent a lifecycle from message order, labels, tool
names, DOM position, or generated identifiers.

The PR9.3 legacy `product_required_action_observed` point event remains compatible.
When that event also carries an explicit product `action_id`, PR10.0 may materialize
the stronger correlated required-action value without changing approval authority.

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

A DOM attribute name is not itself an action id. The required-action surface probe
may report only the *presence* of names from a fixed identity-attribute whitelist.
Even an action-shaped field such as `data-action-id` is only a candidate field until
its value and stability are separately proven. The field presence alone leaves
`stable_action_id_present=false` and cannot promote point evidence into lifecycle.

### Browser-owned observation overlay

The PR10.0 service-worker overlay inspects only explicit app/connector and
required-action identifiers already present in product message metadata.

It does **not** classify a message as connector activity merely because:

- the message has a tool role;
- `web.run`, `api_tool.call_tool`, or another generic router/tool appears;
- a status/label resembles connector activity;
- an event appears near another tool event.

Without explicit connector/app/plugin identity, the message overlay emits no
connector observation. Without an explicit stable activity id, it may emit only
point `OBSERVED` evidence keyed to the current product message, never a fabricated
request/result lifecycle.

A separate bounded router-envelope characterization path may inspect only whitelisted
routing structure. It never exports raw tool arguments/results or treats router use
alone as connector identity.

### Required-action product surface

PR10.0 also has a separate browser-owned, read-only surface probe for authorization
affordances already visible in the existing runtime tab. It uses CDP `Runtime.evaluate`
only. It never dispatches input, clicks controls, creates/navigates tabs, sends a
product turn, or grants approval authority.

The surface is accepted only when all of the following are visible together:

```text
recognized app/connector name
connect control
explicit dismiss/not-now control
action type = connector_authorization_required
```

The worker re-materializes only a fixed safe result. Raw DOM text is not returned.
Identity characterization additionally returns only whitelisted attribute *names*;
attribute values remain unexported in this milestone unless a later, separately
reviewed proof establishes that one field is safe and semantically stable.

### Privacy rule

Structured app/connector observations must never contain raw tool arguments/results,
OAuth tokens, cookies, authorization headers, refresh/access tokens, signed URLs,
provider credentials, private reasoning, raw SSE, arbitrary connector payloads, raw
DOM text, raw identity-attribute values, or retrieved private connector content.

Only bounded identifiers, safe product display names, operation names, lifecycle
phase, sequence, timing metadata, and fixed-whitelist structural field names are
eligible for observation/characterization. Live-gate reporting additionally strips
labels and emits only an explicit safe-key allowlist.

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

`tools/pr10_0_connector_live_gate.py` is the bounded turn characterization entrypoint.
It requires:

- exact Git head supplied through `--expected-head`;
- tracked-only clean working state;
- explicit `--acknowledge-live-write`;
- successful no-write overlay support proof;
- exactly one browser-owned product write;
- no automatic retry and no fallback transport;
- canonical readback finality and exact conversation/message identity;
- no exported private-thought text;
- zero dropped structured-observation events for a passing safety/finality run.

The default prompt allows only a harmless read-only use of an already-connected
ChatGPT app/plugin and asks the product not to reveal retrieved private content.
The report redacts arbitrary assistant text.

A safe/finality pass with no explicit connector identity is still valuable product
characterization, but it does **not** graduate `TOOLS_CONNECTORS`.

`tools/pr10_0_required_action_surface_probe.py` is separate and has an unconditional
product-write budget of zero. It observes an already-visible authorization surface,
materializes safe point evidence through the same PR10 collector contract, and
continues to claim no lifecycle correlation until a stable product id is proven.

### Authenticated live evidence so far

The loaded Chrome worker proved the PR10.0 no-write support contract after the
outermost-wrapper composition repair.

A bounded authenticated product turn then proved the existing write/finality safety
boundary: exactly one write, one canonical readback, canonical finality, matching
conversation/message identity, no automatic retry, no fallback, and no private-thought
text export. Product activity included the generic `api_tool` router, but no explicit
connector/app/plugin identity was present in the normalized message metadata. That
router activity therefore remains tool evidence rather than connector evidence.

After that turn, the real ChatGPT UI presented a Gmail authorization affordance with
both **Connect** and **Not now** choices. A zero-write/zero-click authenticated surface
probe observed:

```text
connector_name                 gmail
action_type                    connector_authorization_required
connect_control_present        true
dismiss_control_present        true
stable_action_id_present       false
raw_dom_exported               false
click_performed                false
write_performed                false
approval_authority_granted     false
debugger_attached_after        false
```

The V2 surface gate then materialized this live product evidence as a
`ProductRequiredActionSurfaceObservation` with `kind=REQUIRED_ACTION`,
`phase=OBSERVED`, `surface_origin=product_surface`, zero collector drops, no
`action_id`, and `lifecycle_correlation_claimed=false`.

This proves **required-action point evidence end-to-end**. It does not prove connector
execution lifecycle or stable required-action lifecycle correlation.

### Capability rule

`TOOLS_CONNECTORS` stays `UNKNOWN` until authenticated live product evidence proves
that the browser-owned observation channel exposes qualifying connector execution
evidence with the required privacy, correlation, finality, and no-retry boundaries.
A calculator, generic tool/router proof, authorization prompt, or required-action
point observation is insufficient because those do not prove connector execution
lifecycle.

Deterministic tests are necessary but not sufficient for capability graduation.
PR10.0 may close with `TOOLS_CONNECTORS=UNKNOWN` if the authenticated product does
not expose qualifying explicit connector identity/correlation evidence; that boundary
must be recorded rather than guessed around.

### Acceptance

PR10.0 is complete only when:

1. deterministic collector/runtime tests pass across the supported Python matrix;
2. legacy PR9.3 observation semantics remain compatible;
3. collector defects remain non-authoritative and cannot invalidate/retry a write;
4. privacy regressions are fail-closed;
5. the loaded worker proves the PR10.0 observation schema with a no-write support gate;
6. browser-owned app/connector and required-action surfaces are characterized without
   exporting credentials, arguments, results, retrieved private content, private
   reasoning, raw DOM text, or raw identity-attribute values;
7. one bounded authenticated turn confirms the existing write/finality contract;
8. visible required-action evidence materializes as point `REQUIRED_ACTION/OBSERVED`
   without fabricated lifecycle identity;
9. any lifecycle correlation claim requires a separately proven stable product id;
10. `TOOLS_CONNECTORS` remains `UNKNOWN` unless qualifying connector execution evidence
    is actually observed;
11. exact installed-wheel smoke remains green before merge.

## Later PR10 milestones

Do not freeze later milestone contents before PR10.0 live evidence. Candidate areas
include generated/downloadable product artifacts, compatibility-drift hardening, and
real downstream adoption feedback. Each should remain a vertical product milestone,
not a sequence of verification-only micro-PRs.
