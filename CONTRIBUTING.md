# Contributing

Thanks for contributing to `chatgpt-web-adapter` (CWA).

CWA sits on top of an ordinary, undocumented and changing ChatGPT web-product surface. Contributions therefore need to preserve not only behavior, but also the distinction between **what was observed**, **what is implemented**, and **what authority the public runtime actually grants**.

## Start with the current contract

For new work, read:

- [`README.md`](README.md) — product position and quick start;
- [`STATUS.md`](STATUS.md) — current release/main/capability state;
- [`ROADMAP.md`](ROADMAP.md) — current direction;
- [`docs/architecture.md`](docs/architecture.md) — runtime/transport/observation boundaries;
- [`docs/README.md`](docs/README.md) — current vs historical documentation map;
- [`SECURITY.md`](SECURITY.md) — sensitive-data rules.

Historical PR-specific documents are evidence and lineage. Do not assume an older milestone document is the current public contract when a later status/architecture/contract document supersedes its framing.

## Development setup

```bash
python -m pip install -e ".[test,browser]"
python -m pytest -q
```

The full source matrix supports Python 3.10-3.14 on Ubuntu and Windows. Ordinary deterministic tests must not require a live account or product write.

## Three change classes

### 1. Documentation / repository polish

Examples:

- README/status/roadmap updates;
- documentation navigation;
- contribution/security/community files;
- packaging metadata that does not change runtime behavior.

Expected validation:

- documentation/metadata regressions;
- normal CI/build/installed-wheel gates when the change reaches a PR.

A docs-only change does **not** justify sending a live ChatGPT turn merely to produce more evidence.

### 2. Product-runtime behavior

Examples:

- product writes;
- canonical finality/reconciliation;
- rich input;
- model/Temporary behavior;
- structured observations;
- capability declarations;
- production browser-owned transport behavior.

Expected validation:

```text
implementation
-> deterministic regression / failure semantics
-> bounded live validation for the changed product-facing behavior
-> docs / compatibility update
-> full CI and exact installed-wheel validation
```

Live validation should have an explicit write/read/click/local-write budget appropriate to the experiment. Prefer one decision-relevant gate over repeated open-ended probing.

### 3. Experimental / research / diagnostic work

Examples:

- `browserless-request` investigations;
- Sentinel/protocol characterization;
- direct browser-native diagnostics;
- DOM/CDP/product-surface characterization;
- feasibility probes.

Research code must not self-promote into a production support claim merely because one experiment passed. Keep public support tier and capability state conservative until the required product evidence exists.

When a research path reaches the decision-relevant boundary, stop. Do not continue reverse engineering merely because deeper internal state is accessible.

## Core invariants

Contributions must preserve these unless a separately reviewed evidence-backed milestone explicitly changes one:

```text
product observation
!= product approval
!= connector authorization
!= product write authority
!= retry authority
!= canonical finality
!= downstream filesystem/Git/workspace authority
```

```text
streaming != canonical finality
```

```text
ambiguous write -> reconciliation -> no automatic retry
```

Additional rules:

- no silent browser-owned ↔ browserless ↔ compatibility fallback;
- capability state is evidence-backed and provider-aware;
- transport support tier is separate from capability state;
- browser/extension/CDP internals stay below the public runtime contract;
- generic labels, DOM position, adjacency or filenames do not become stable product identity by inference;
- challenge protections are not bypass targets.

## Public API and compatibility

`ChatGPTProductRuntime` is the forward-looking production boundary.

`ChatGPTWebClient` / `WebChatClient` remain compatibility surfaces for existing callers. Do not silently route one API through the other or remove compatibility/research imports merely for tree cleanliness.

If a change affects root exports, support tiers, capability state, runtime signatures, CLI behavior or installed-package contents, update the corresponding tests and documentation in the same PR.

## Tests and gates

Before finalizing a PR-sized change:

- run `python -m pytest -q`;
- preserve README/documentation regression tests;
- run relevant focused tests while developing;
- use [`docs/live_smoke_checklist.md`](docs/live_smoke_checklist.md) when product-facing behavior changed;
- use [`docs/release_checklist.md`](docs/release_checklist.md) for release-impacting work;
- verify the exact PR head in CI rather than relying on an earlier green commit.

Do not weaken a safety, packaging, artifact or documentation gate merely to turn CI green. If the gate exposes a real mismatch, repair the implementation or the stale contract explicitly.

Transient timing failures should be diagnosed separately from code regressions; do not hide a deterministic failure behind reruns.

## Documentation lineage

CWA intentionally retains many historical PR-specific evidence documents.

When later work changes the current contract:

- update current landing/status/architecture docs;
- add or update the new milestone contract/evidence document;
- preserve older evidence as historical evidence;
- do not rewrite history to imply that an older experiment proved a later claim.

Use [`docs/README.md`](docs/README.md) to keep current and historical material discoverable.

## Security and privacy hygiene

Never commit or paste into issues/PRs:

- `auth_data.json`;
- cookies, access/refresh/session tokens;
- signed-in browser profiles;
- Native Messaging runtime tokens/descriptors;
- Sentinel/Turnstile/proof/conduit credentials;
- raw network captures or unsanitized traces;
- raw connector arguments/results or retrieved private content;
- capability-bearing artifact locator values such as signed download URLs.

See [`SECURITY.md`](SECURITY.md).

## Pull requests

Prefer one coherent vertical milestone over a chain of verification-only micro-PRs.

A PR description should state:

- goal and scope;
- explicit non-goals;
- public capability/support/authority impact;
- deterministic validation;
- bounded live evidence when applicable;
- compatibility/security implications;
- exact final head used for closure.

Keep commits logically grouped and the branch clean. Merge remains a separate explicit decision after review and exact-head validation.
