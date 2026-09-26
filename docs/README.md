# Documentation Map

This directory contains two different kinds of documentation:

1. **current product/runtime guidance** — what a user or downstream integrator should
   read now;
2. **historical engineering evidence** — PR-specific records preserved because CWA's
   capability and safety boundaries are evidence-driven.

Do not treat every PR-numbered document as current getting-started guidance.

## Start here

- [`../README.md`](../README.md) — project overview, provider status and production
  quick start;
- [`../STATUS.md`](../STATUS.md) — current release vs `main` checkpoint;
- [`../USAGE.md`](../USAGE.md) — usage guide;
- [`../ROADMAP.md`](../ROADMAP.md) — current development direction;
- [`architecture.md`](architecture.md) — current provider-aware architecture;
- [`providers.md`](providers.md) — provider capability/support matrix;
- [`browser_owned.md`](browser_owned.md) — why browser-owned execution is the
  reference/default web-product strategy;
- [`../SECURITY.md`](../SECURITY.md) — security and sensitive-data boundary;
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution/evidence expectations.

## Current architecture and public surface

- [`architecture.md`](architecture.md) — provider-specific runtimes, schema-2
  provider boundary, canonical/finality differences and authority separation;
- [`providers.md`](providers.md) — ChatGPT production/default vs DeepSeek/Gemini
  experimental support;
- [`browser_owned.md`](browser_owned.md) — browser-owned vs browserless execution;
- [`browser_owned_v1_contract.md`](browser_owned_v1_contract.md) — ChatGPT
  production browser-owned contract;
- [`product_capabilities_provenance_pr8_5.md`](product_capabilities_provenance_pr8_5.md)
  — capability/provenance foundations;
- [`public_surface_pr8_6.md`](public_surface_pr8_6.md) — support-tier lineage;
- [`building_on_top.md`](building_on_top.md) — downstream integration guidance.

The PR8-named capability/public-surface records remain relevant lineage, but current
architecture should be read from `architecture.md`, `providers.md` and
`STATUS.md`.

## Authentication and browser bridge

- [`authentication.md`](authentication.md) — reusable ChatGPT web-session lifecycle;
- [`browser_bridge_product_surface_pr11_0.md`](browser_bridge_product_surface_pr11_0.md)
  — local extension product chrome and no-write UI boundary;
- [`browser_native_runtime.md`](browser_native_runtime.md) — lower-level
  browser-native implementation history;
- [`troubleshooting.md`](troubleshooting.md) — operational failures;
- [`live_smoke_checklist.md`](live_smoke_checklist.md) — bounded live validation.

DeepSeek/Gemini currently reuse the local browser bridge but retain provider-specific
page/runtime semantics. See `providers.md`.

## ChatGPT production capabilities

### Rich input

- [`product_rich_input_pr9_2.md`](product_rich_input_pr9_2.md) — image/file/
  multimodal production boundary.

### Structured product observations

- [`product_runtime_observation_integration_pr9_3.md`](product_runtime_observation_integration_pr9_3.md)
  — observation integration;
- [`generated_artifact_handoff_pr10_1.md`](generated_artifact_handoff_pr10_1.md)
  — generated-artifact boundary and current unsupported handoff decision.

### Browserless / backend research

- [`browserless_request_transport_pr9_1.md`](browserless_request_transport_pr9_1.md)
  — experimental ChatGPT browserless transport;
- [`raw_payload.md`](raw_payload.md) — lower-level experimental payload surface.

## Provider architecture evidence

The current provider-neutral boundary was established and tested through the PR15
generation.

Key records:

- [`engineering/pr15_52_provider_neutral_boundary.md`](engineering/pr15_52_provider_neutral_boundary.md)
  — initial provider-neutral boundary;
- [`engineering/pr15_53_minimal_deepseek_web_proof.md`](engineering/pr15_53_minimal_deepseek_web_proof.md)
  — DeepSeek proof;
- [`engineering/pr15_54_post_deepseek_provider_boundary_audit.md`](engineering/pr15_54_post_deepseek_provider_boundary_audit.md)
  — neutrality audit;
- [`engineering/pr15_55_minimal_gemini_web_proof.md`](engineering/pr15_55_minimal_gemini_web_proof.md)
  — Gemini proof;
- [`engineering/pr15_56_provider_architecture_closure.md`](engineering/pr15_56_provider_architecture_closure.md)
  — closure/freeze decision.

File names of historical records may retain PR-specific wording. Their role is evidence,
not public API definition.

## Current project positioning

- [`engineering/pr16_0_cwa_identity_direction.md`](engineering/pr16_0_cwa_identity_direction.md)
  — post-PR15 positioning direction; naming is deliberately deferred.

## Release and maintenance

- [`release_checklist.md`](release_checklist.md) — release gates;
- [`rename_compatibility.md`](rename_compatibility.md) — historical package naming
  compatibility record.

## Historical records

Other PR-specific files under `docs/` and `docs/engineering/` preserve:

- live product evidence;
- failed hypotheses;
- ownership migrations;
- compatibility decisions;
- safety/finality boundaries;
- retired research surfaces.

Keep them when they explain why a current boundary exists, but do not make users walk
through the historical sequence to understand today's product.
