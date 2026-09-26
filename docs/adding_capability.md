# Adding a Hosted Capability to CWA

New hosted capabilities should be evidence-driven vertical slices, not generic
abstractions looking for a product.

Before opening code, use the
[capability proposal issue template](../.github/ISSUE_TEMPLATE/capability_proposal.yml).

## 1. State the product semantics

Describe the smallest useful operation in product terms.

Good:

```text
text + source language + target language
-> translated text
```

Too broad:

```text
automate Google
```

Explain why this belongs in CWA rather than in downstream application policy.

## 2. Define input and output identity

Specify:

- exact input values;
- product/session identity assumptions;
- output identity;
- whether the operation is conversational, persistent, stateless, or long-running;
- whether the result is text, observation, or durable artifact.

Do not infer stable identity from DOM order, display text, filename, or URL similarity.

## 3. Identify the commitment boundary

Write down the point at which the hosted product may already have accepted the
operation.

```text
before commitment
-> ordinary failure may be safe

commitment may have executed
-> outcome may be ambiguous
-> reconciliation required
-> automatic retry forbidden
```

## 4. Define finality before implementation

Examples of distinct finality classes:

```text
CANONICAL_READBACK
PAGE_DOM_STABLE_COMPLETION
PAGE_DOM_STABLE_TRANSLATION
```

Do not relabel page observation as canonical product completion.

## 5. Keep product mechanics local

Provider/product-specific selectors, routes, page structure, and browser mechanics
should stay in the product module.

A new capability should not modify shared core merely because a local implementation
detail is inconvenient.

Promote a shared primitive only when multiple independent products demonstrate the
same requirement.

## 6. Preserve authority separation

A capability must not collapse:

```text
observation
approval
write authority
retry authority
canonical finality
downstream filesystem/Git/workspace authority
```

into one boolean such as "success".

## 7. Add deterministic regressions

At minimum cover:

- input validation before product mutation;
- exact request/operation identity;
- known pre-commit failure;
- ambiguous post-commit failure;
- no automatic retry;
- result identity/finality;
- route/session mismatch where relevant;
- packaging/runtime composition when new browser assets are added.

Deterministic tests must not depend on a live account.

## 8. Use one bounded live acceptance gate

For product-facing behavior, add the smallest temporary live gate that answers the
decision-relevant question.

The gate should have a bounded write/read/click budget and privacy-safe diagnostics.

When the question is answered:

1. preserve the evidence in an engineering record;
2. delete temporary live/characterization tooling unless it is genuinely a supported
   diagnostic;
3. run exact-head CI again.

## 9. Keep the support claim conservative

A successful live probe can justify an experimental capability.

It does not automatically justify:

- root-package export;
- production support;
- provider-neutral abstraction;
- generic registry/factory;
- automatic retry;
- official-API equivalence.

## 10. PR closure checklist

```text
[ ] issue states product semantics and non-goals
[ ] commitment boundary documented
[ ] ambiguity/no-replay behavior explicit
[ ] finality class explicit
[ ] deterministic regressions green
[ ] bounded live evidence captured where required
[ ] temporary acceptance tooling removed
[ ] support tier remains evidence-backed
[ ] current docs updated
[ ] exact final PR head passes full CI
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the general repository contract.
