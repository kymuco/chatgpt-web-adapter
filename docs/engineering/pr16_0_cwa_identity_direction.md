# PR16.0 — CWA post-PR15 identity and positioning direction

## Status

Design / positioning pass only.

This slice changes no runtime behavior, provider support tier, package name, Python
import path, CLI entry point, repository name or release version.

Its purpose is to align the public story with the architecture that PR15 actually
produced before changing names or widening the public provider surface.

## 1. Why this pass exists

The current public identity still says, in effect:

```text
chatgpt-web-adapter
→ Python SDK / CLI for one ordinary ChatGPT web session
→ ChatGPTProductRuntime
```

That was accurate for the released 0.3 generation.

PR15 changed the architecture materially:

```text
consumer
→ provider-neutral product boundary
→ provider semantics
   ├─ ChatGPT
   ├─ DeepSeek Web
   └─ Gemini Web
```

The repository therefore now contains two truths at once:

1. ChatGPT is still the mature/default production provider and owns most of the rich
   capability surface.
2. The reusable architecture is no longer ChatGPT-specific.

Documentation should make both truths visible instead of choosing one and hiding the
other.

## 2. Proposed product identity

The project should be understood as:

> A local product-runtime bridge for authenticated consumer AI web products.

A slightly fuller statement:

> CWA lets local software use ordinary consumer AI products through an explicit,
> typed runtime boundary while keeping product observation, write authority, finality,
> retry authority and downstream action authority separate.

The key value is not merely “send text to multiple chat websites”.

The durable value is:

```text
local application / HDE / Codexia / terminal
                  ↓
         product-runtime boundary
                  ↓
       ordinary hosted AI products
```

with explicit semantics for:

- provider identity;
- capabilities;
- provenance;
- write transport;
- completion/finality evidence;
- ambiguous-write reconciliation;
- support tier;
- downstream authority separation.

## 3. What CWA is not

CWA should not be positioned as:

- an official API client;
- an API-key model aggregator;
- a generic browser automation framework;
- a full chat application;
- an agent/orchestrator;
- a memory system;
- a provider failover router;
- an anti-bot/challenge bypass toolkit;
- a generic abstraction over every AI website;
- a promise that all providers expose identical capabilities.

The architecture intentionally preserves provider differences instead of hiding them.

## 4. Provider model after PR15

The public story should distinguish shared architecture from provider maturity.

### ChatGPT

```text
support: production/default provider
canonical readback: yes
browser-owned protected write: production
rich input: production on proven paths
model/temporary/search observation: evidence-backed
historical compatibility client: retained
```

### DeepSeek Web

```text
support: experimental
text new chat: live-proven
text continuation: live-proven
canonical readback: no claim
completion evidence: page DOM stable completion, noncanonical
provider runtime: module-only
```

### Gemini Web

```text
support: experimental
text new chat: live-proven
text continuation: live-proven
canonical readback: no claim
completion evidence: page DOM stable completion, noncanonical
provider runtime: module-only
```

README capability reporting should therefore move from one flat ChatGPT-centric table
toward a provider × capability matrix.

## 5. Browser-owned vs browserless positioning

The current architecture should explicitly treat browser-owned execution as the
reference/default web-product mutation strategy.

Why:

```text
real signed-in browser
→ owns cookies/session
→ owns frontend execution
→ owns normal navigation
→ owns product challenge/protection behavior
→ owns the actual consumer-product submit
```

CWA then has a bounded responsibility:

```text
resolve product surface
→ perform one governed write
→ observe/reconcile outcome
```

Browserless reproduction of private web protocols remains technically possible and is
already represented by the experimental ChatGPT `browserless-request` transport.

It is not the architectural target merely because it avoids Chrome.

A browserless path should be promoted only when product evidence shows that it is
materially useful and sufficiently stable without challenge bypass, synthetic
protection credentials, hidden fallback or weaker write/finality guarantees.

Official provider APIs are a third category:

```text
OpenAI API / Gemini API / DeepSeek API
!= ordinary ChatGPT / Gemini / DeepSeek consumer web product
```

They may be useful integrations in another context, but should not be described as a
drop-in replacement for CWA's ordinary-product semantics.

## 6. CWA name direction

The short name `CWA` has accumulated useful continuity:

- CLI: `cwa`;
- documentation shorthand;
- repository history;
- user familiarity;
- extension/product identity.

The strongest candidate expansion after PR15 is:

> **CWA — Conversational Web Adapter**

Why it fits:

- keeps the existing short identity;
- no longer names one provider;
- still describes the web-product boundary rather than pretending to be a model/API
  abstraction;
- remains compatible with ChatGPT being the mature/default provider;
- leaves room for DeepSeek, Gemini and future evidence-backed products;
- does not imply agent orchestration or downstream authority.

This is a positioning candidate, not yet a package rename.

Alternative directions considered:

- **AI Product Runtime** — accurately names an architectural layer, but is too generic
  and sounds more like a framework category than this project.
- **AI Product Bridge** — understandable but less specific about the web-product
  boundary and loses CWA continuity.
- **Multi-AI Web Adapter** — over-emphasizes provider count and ages poorly.
- **Web Product Runtime** — technically reasonable but weak as a recognizable project
  identity.

## 7. No hard rename in PR16.0

PR16.0 deliberately keeps:

```text
repository   = chatgpt-web-adapter
distribution = chatgpt-web-adapter
import       = chatgpt_web_adapter
CLI          = cwa / chatgpt-web-adapter
```

Reasons:

1. the current PyPI release is ChatGPT-centered and already consumed under this name;
2. ChatGPT remains the only provider with a mature production capability surface;
3. DeepSeek/Gemini are real but still EXPERIMENTAL/module-only;
4. a rename would mix package migration with a positioning decision;
5. PyPI distribution migration is not a free alias operation and creates long-term
   compatibility/support obligations.

The project can change its narrative before changing its package identity.

## 8. Rename trigger

A hard repository/distribution rename should be reconsidered only when at least one of
the following is true:

1. a non-ChatGPT provider is promoted beyond experimental support;
2. a stable public provider selection/construction API exists because a real consumer
   needs it;
3. a new release is intentionally positioned as a multi-provider product-runtime
   generation rather than a ChatGPT-first runtime with experimental providers;
4. the old package name materially misleads external users more than migration would
   cost.

Before a hard rename, separately verify:

- GitHub repository-name collisions;
- PyPI distribution availability;
- CLI collision risk;
- documentation/search discoverability;
- migration plan for existing `chatgpt_web_adapter` imports;
- whether the old PyPI project becomes a compatibility shim, deprecation package or
  frozen historical distribution.

## 9. Recommended public narrative

The README should eventually open with something structurally similar to:

```text
CWA
Local runtime bridge for consumer AI web products.

ChatGPT       production/default
DeepSeek Web  experimental
Gemini Web    experimental
```

Then explain:

```text
application / HDE / Codexia / terminal
                 ↓
       ProductProviderBoundary
                 ↓
       provider-specific runtime
       ├─ ChatGPT
       ├─ DeepSeek
       └─ Gemini
```

Only after that should the README enter the mature ChatGPT quick start.

This avoids two bad narratives:

```text
bad A: "CWA is still only ChatGPT"
bad B: "all three providers are equally production-ready"
```

Neither is true.

## 10. Documentation restructuring

The current docs are valuable but mix current guidance with architectural lineage.

Recommended current-document set:

```text
README.md
  project identity + provider matrix + quick start

docs/architecture.md
  provider-neutral architecture first
  ChatGPT production plane second
  experimental provider implementations third

USAGE.md
  stable ChatGPT/default workflow
  explicit experimental provider section

docs/providers.md
  provider support/capability matrix
  canonical-read/finality differences
  support-tier rules

docs/browser_owned.md
  browser-owned strategy and why it is the default

docs/README.md
  current docs first
  historical/evidence records clearly separated
```

PR-numbered engineering records should remain as evidence/history rather than being
rewritten into polished current guides.

## 11. README changes that are already justified

Without renaming the package, the README can already safely change:

- opening description from ChatGPT-only to consumer-AI-product runtime bridge;
- first architecture diagram to `ProductProviderBoundary` + providers;
- provider × capability matrix;
- explicit statement that ChatGPT is production/default;
- explicit statement that DeepSeek/Gemini are experimental;
- browser-owned explanation as the preferred web-product execution strategy;
- browserless explanation as experimental, not the end goal;
- clearer distinction between official APIs and ordinary web-product semantics;
- project non-goals after provider-architecture freeze.

The existing ChatGPT installation and quick-start commands remain valid and should
stay prominent.

## 12. Package metadata changes should wait

`pyproject.toml` currently says:

> Local Python SDK and CLI bridge for an existing ordinary ChatGPT web session.

That is now narrower than the source architecture.

However, changing package metadata should be grouped with the first intentional
post-PR15 public documentation/release pass, not slipped into the identity decision
itself.

Likewise, package keywords and project description can become provider-neutral before
a hard rename while preserving the existing distribution name.

## 13. Security documentation implications

The current security document is also ChatGPT-centric.

Future public-doc refresh should generalize high-level rules:

```text
authenticated provider session/profile
browser-native bridge material
provider-specific route/session identity
product observations
capability-bearing locators
```

Then keep ChatGPT-specific Sentinel/Turnstile material in a provider-specific section.

The no-challenge-bypass and no-credential-export boundaries remain unchanged.

## 14. Release direction

A docs/identity refresh alone does not justify a release.

A natural release decision remains:

```text
0.3.x
→ compatible fixes / drift repairs / docs / packaging

0.4.0
→ coherent new public product-runtime capability generation
```

A future rename does not need to be coupled to 0.4.0 unless the public multi-provider
surface itself is part of that release.

## 15. Decision after PR16.0

The recommended direction is:

```text
now
→ freeze technical architecture
→ adopt provider-neutral public narrative
→ keep current repository/package/import names
→ use CWA as the primary short identity
→ treat "Conversational Web Adapter" as the leading future expansion

next
→ rewrite current README/docs around the frozen architecture

later, only with evidence
→ decide whether a hard repository/distribution rename is worth migration cost
```

This lets project identity catch up with the architecture without turning branding into
another compatibility migration.
