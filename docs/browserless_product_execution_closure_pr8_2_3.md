# PR8.2.3 — Supported Non-Browser Product Execution Surface Exhaustion, Native Client Boundary Characterization and Browserless Write-Path Closure Governance

PR8.2.3 closes the supported-interface branch of the browserless ordinary ChatGPT write investigation as of 2026-08-14.

## Question

Does OpenAI currently document a supported non-browser surface that an external process can invoke to create an ordinary ChatGPT **Chat** turn while preserving the consumer ChatGPT product's existing conversations, memory/personalization continuity, and product usage semantics?

## Acceptance contract

A candidate must satisfy every property:

1. OpenAI-supported and documented.
2. No browser runtime is required as the execution substrate.
3. An external program can invoke it directly.
4. It executes ordinary ChatGPT Chat semantics rather than a different model/agent product.
5. It can continue existing ChatGPT conversations.
6. It preserves ChatGPT memory/personalization continuity.
7. It uses the consumer ChatGPT product entitlement/usage semantics rather than separate API billing or a different agentic pool.
8. Direction is external client → ChatGPT Chat.

## Current closure verdict

`SUPPORTED_NON_BROWSER_PRODUCT_WRITE_SURFACE_EXHAUSTED`

This is a supported-surface exhaustion result, not a claim of physical impossibility. It is deliberately reopenable if OpenAI later documents a surface satisfying the whole acceptance contract.

## Surface classification

- **ChatGPT desktop app (Chat):** native OpenAI product surface with Chat conversation continuity, but no documented external Chat turn IPC/SDK/CLI contract was identified.
- **OpenAI API:** supported and browserless, but API service is a separately billed/managed product and does not expose consumer ChatGPT conversation/memory state.
- **Sign in with ChatGPT:** identity provider only; sign-in does not independently grant external access to conversations, memory, files, tokens, billing, or other ChatGPT account data.
- **Apps SDK / MCP:** supported integration direction is ChatGPT invoking external tools/data, not an external application invoking ordinary ChatGPT Chat as a client turn API.
- **Codex CLI / SDK:** supported programmatic non-browser surface and can be available through ChatGPT plans, but Codex is an agentic/coding experience whose history/workflows remain separate from ordinary ChatGPT history.
- **Compliance Platform:** programmatic audit/compliance access to workspace logs/state, not ordinary Chat turn execution.

Official evidence was reviewed from OpenAI Help Center and developer documentation on 2026-08-14. Product documentation can change; this PR therefore records an evidence date and a reopen condition instead of hard-coding permanent impossibility.

## Native client inventory

`examples/browserless_product_execution_closure.py --native-inventory` performs a bounded read-only inventory:

- on Windows, `Get-AppxPackage *ChatGPT*` returns package name metadata;
- PATH is checked for the `codex` executable.

The probe does **not** launch ChatGPT, automate UI, inspect private application storage, extract credentials, or probe undocumented IPC. Installed native-client presence is not evidence of an external execution contract.

## Governance

PR8.2.3 does not implement or extend:

- private ChatGPT protected-write reconstruction;
- challenge/Sentinel/Turnstile emulation;
- browser fingerprint or protective credential extraction;
- native UI automation;
- undocumented native IPC probing.

Until the closure is reopened, PR8.1/PR8.1.1 browser-native page-owned submission remains the minimum proven supported ordinary ChatGPT product write substrate.
