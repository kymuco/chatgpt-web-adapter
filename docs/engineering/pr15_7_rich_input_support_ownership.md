# PR15.7 — Rich-input support ownership consolidation

## Goal

Remove historical `executeNativeTurn` ownership that exists only to augment the
`characterizeRichInputSupport` no-write response.

The runtime rule remains:

> one concept → one explicit owner → one call path

## Before

The rich-input support response was assembled implicitly while a no-write support
probe traversed the ordinary native-turn wrapper chain. Schema generations 4,
6, and 7–29 progressively mutated the returned support object. Many of those
schema files therefore sat on every ordinary turn even though their native-turn
wrapper existed only for support metadata.

## After

The existing explicit `rich-input-diagnostics` control-plane owner also matches
`characterizeRichInputSupport`.

A pure support probe:

1. validates that no text or attachment paths were supplied;
2. creates the schema-1 base support result;
3. applies the historical support augmenters in exact order:
   schema 4 → schema 6 → schema 7 … schema 29;
4. returns without entering ordinary `executeNativeTurn`.

Combined diagnostic+support requests retain the PR15.5 diagnostic precedence and
their historical outer support-tail behavior.

## Ownership reduction

The native-turn wrapper is removed from support-only layers:

- deadline repair;
- schema 7–13;
- schema 15–17;
- schema 19–27.

Mixed layers keep native-turn ownership only where they still own runtime
semantics:

- base rich-input lifecycle;
- closure result semantics;
- schema 14 composition guard;
- schema 18 committed-identity normalization;
- schema 28 identity diagnostics;
- schema 29 submit/identity diagnostics.

## Preserved boundaries

This change does not alter attachment staging, protected submit, Browser
Authority, deadline enforcement, durable-fence cleanup, request correlation,
conversation identity authority, or automatic retry policy.
