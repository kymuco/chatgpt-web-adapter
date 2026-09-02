## Summary

Describe the user-visible or contract-level change.

## Scope

- What is included?
- What is intentionally not included?

## Capability / authority impact

State whether this PR changes any of the following:

- public API/support tier;
- capability state;
- product-write behavior;
- canonical finality/reconciliation;
- retry/fallback behavior;
- structured observation surface;
- connector/required-action authority boundary;
- filesystem/Git/workspace authority.

If none, say **none**.

## Validation

List focused tests and the final full-suite / CI evidence.

For product-facing changes, include bounded live evidence and its write/read/click/local-write budget. Documentation-only work should normally require **no live product write**.

## Compatibility / security

Describe compatibility, packaging, privacy or credential-handling implications.

## Checklist

- [ ] Tests cover the changed contract.
- [ ] Current docs are updated where needed.
- [ ] Historical evidence was not rewritten as if it proved later claims.
- [ ] No secret/session/connector/private payload material is included.
- [ ] No automatic ambiguous-write retry or silent fallback was introduced unintentionally.
- [ ] Capability/support claims are evidence-backed and provider-aware.
- [ ] Final closure is based on the exact PR head.
- [ ] Merge remains a separate explicit decision after review/validation.
