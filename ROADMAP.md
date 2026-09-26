# chatgpt-web-adapter Roadmap

_Last updated: 2026-09-26_

This roadmap describes the current direction after CWA 0.3 and the completed PR15
architecture reset.

Historical PR planning documents remain in `docs/` as evidence and lineage.

## Product role

CWA is a standalone local product-runtime bridge for authenticated consumer AI web
products.

```text
local application / HDE / Codexia / terminal
                  |
                  v
        provider-specific runtime
          /          |          \
         /           |           \
   ChatGPT      DeepSeek Web    Gemini Web
 production     experimental    experimental
```

Each runtime can be inspected/validated through the frozen provider-neutral
`ProductProviderBoundary schema 2`.

CWA owns reusable product/session/write/finality mechanics, capabilities, provenance,
structured product observations, diagnostics and the local browser bridge.

CWA does **not** own project cognition, task planning, Git/workspace authority,
external-action approval policy, or autonomous continuation policy.

## Completed release generations

### CWA 0.2 — production text baseline

Released `v0.2.0` on 2026-08-22.

Established the forward-looking ChatGPT product runtime, browser-owned production
writes, canonical finality, model profiles, Temporary Chat, stable CLI and release-grade
CI.

### CWA 0.3 — rich input and product observation

Released `v0.3.0` on 2026-09-01.

```text
PR9.0  browser-owned v1 + standalone runtime contract
PR9.1  experimental browserless-request transport
PR9.2  images / files / multimodal continuation
PR9.3  search / tool / source / citation observations
PR9.4  stabilization and release
```

## Completed post-0.3 milestones

### PR10 — conservative product boundaries

Added stronger connector/required-action observation while keeping:

```text
tools_connectors = UNKNOWN
```

and froze generated-artifact download as:

```text
ARTIFACT_DOWNLOAD_HANDOFF_UNSUPPORTED_WITHOUT_STABLE_PRODUCT_IDENTITY
```

### PR11 — browser bridge product surface

Established the local extension's bounded read-only product chrome, diagnostics and
packaging surface without changing product write/finality authority.

### PR12-14 — runtime hardening

Hardened browser authority, recovery/delegation behavior, ambiguity semantics and
failure handling before the architecture reset.

### PR15 — architecture reset and provider proof

PR15 is complete.

The sequence:

```text
historical layered ChatGPT runtime
→ explicit ownership consolidation
→ zero reachable production rebinding
→ provider-neutral boundary v1
→ DeepSeek falsifies mandatory canonical readback
→ ProductProviderBoundary schema 2
→ neutrality audit removes silent ChatGPT provenance default
→ Gemini passes schema 2
→ cross-provider ambiguity parity
→ architecture freeze
```

The result is a stable shared provider contract without a public generic provider
factory or fake capability uniformity.

ChatGPT remains production/default.

DeepSeek/Gemini remain module-only experimental providers with live-proven text
new-chat and continuation.

See
[`docs/engineering/pr15_56_provider_architecture_closure.md`](docs/engineering/pr15_56_provider_architecture_closure.md).

## PR16 — public positioning and documentation

### PR16.0 — positioning direction

Completed.

Decision:

- describe CWA according to the provider-aware architecture that now exists;
- keep ChatGPT as production/default;
- keep DeepSeek/Gemini experimental;
- preserve all current repository/distribution/import/CLI names;
- deliberately defer any future naming decision.

### PR16.1 — current documentation refresh

Completed.

Refresh:

- README;
- architecture;
- provider support/finality matrix;
- browser-owned strategy;
- usage/downstream-integration guidance;
- security framing;
- status/roadmap/docs map;
- deterministic documentation contract tests.

No runtime/provider behavior changes were intended.

### PR16.2 — non-chat hosted-capability falsification

Current experimental spike.

Question:

```text
is CWA's reusable core broader than conversational providers?
```

First test:

```text
Google Translate Web
→ translate_text(text, source_language, target_language)
→ bounded page result
```

The experiment deliberately does not force translation into
`ProductProviderBoundary schema 2`, because the existing runtime surface is still
conversation-shaped (`send_text`, `ConversationInput`, `ChatResponse`,
conversation/message identity).

The spike reuses only the lower-level browser bridge, authority lane and ambiguity
discipline. No generic hosted-capability framework should be created unless this and
later non-chat evidence actually require one.

HDE is explicitly not used as a test bed for this experiment.

## Current direction after PR16

After the documentation catches up, stop architecture-driven expansion.

The next runtime work should be **consumer-driven** or **drift-driven**.

### Consumer-driven triggers

Examples:

- HDE/Codexia needs a reusable capability that clearly belongs below application
  policy;
- an external consumer needs stable provider construction/selection;
- a non-ChatGPT provider needs promotion because it is now a real production
  dependency;
- a bounded product capability provides clear utility across consumers.

### Drift-driven triggers

Reopen implementation work when:

- a previously proven provider path fails;
- DOM/request/session behavior changes;
- finality or conversation identity assumptions stop holding;
- browser/extension behavior changes materially;
- a reproducible compatibility regression appears.

Preferred response:

```text
observe failure
→ characterize narrowly
→ repair the smallest owned contract
→ deterministic regression
→ bounded live validation
→ document the new boundary
```

Avoid open-ended reverse engineering after the decision-relevant boundary is known.

## Reopen conditions for provider architecture

Do not add provider #4 or another abstraction layer just to increase coverage.

Reopen the frozen provider architecture only if:

1. a real provider cannot fit schema 2 without lying about semantics;
2. a real consumer needs stable public provider construction/selection;
3. a new canonical interface shape cannot be represented;
4. an experimental provider is being promoted to production and needs a stronger
   support contract;
5. a concrete safety failure disproves current write/reconciliation invariants.

## Browser-owned vs browserless

Browser-owned remains the reference/default web-product mutation strategy.

`browserless-request` remains `EXPERIMENTAL` until long-term evidence supports a
stronger claim.

CWA will not add challenge-bypass machinery merely to remove the browser.

See [`docs/browser_owned.md`](docs/browser_owned.md).

## Conservative boundaries

### Connector execution

Revisit only if authenticated product evidence exposes stable connector execution
identity/correlation without exporting credentials or private connector content.

Until then:

```text
tools_connectors = UNKNOWN
```

### Generated-artifact download

Reopen only after both are proven:

1. stable product-owned artifact identity;
2. a safe browser-owned resolution path.

### Chrome Web Store distribution

Reconsider only when external adoption justifies the privacy/update/support contract.

Do not publish merely to remove the unpacked/developer label.

## Release direction

Do not cut a new minor release for documentation polish alone.

Likely rule:

- `0.3.x` — compatible fixes, drift repairs, docs, packaging, narrow ergonomics;
- `0.4.0` — coherent new public runtime capability generation.

## Architectural invariants

1. CWA remains standalone.
2. Provider semantics remain explicit.
3. Canonical observation and mutation authority stay separate.
4. Transport/provider fallback is never silent.
5. Ambiguous writes are never automatically retried.
6. Incremental/page observation is not promoted to canonical finality.
7. Provenance is observed rather than fabricated.
8. Capability state is evidence-backed and provider-aware.
9. Observation never becomes downstream authority by implication.
10. Browser internals remain below the runtime boundary.
11. Research surfaces do not become production APIs merely by existing.
12. No challenge-bypass expansion.
13. Product drift fails clearly rather than pretending permanence.
14. Future naming is a separate product decision, not an architecture requirement.

## Non-goals

CWA is not becoming:

- a full chat application;
- a general agent/orchestrator;
- HDE/Codexia memory or policy;
- a Git/filesystem authority layer;
- a provider failover router;
- a caller-controlled abstraction over every internal product tool;
- a browser-protection bypass toolkit;
- a generic model/API aggregator;
- a public provider registry without a real consumer need.
