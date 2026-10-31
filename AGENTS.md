# Agent instructions — CWA

This file is for coding agents **working on this repository**, not for end-user tool-call permission. See [docs/agent_integration.md](docs/agent_integration.md) for integrating CWA into an agent.

## Start from current reality

- Public package: `chatgpt-web-adapter`; Python import: `chatgpt_web_adapter`; CLI: `cwa`.
- **Primary ChatGPT SDK:** `BrowserlessHTTPClient` (Direct HTTP); `cwa send` defaults to Direct HTTP since published `v0.4.1`.
- **Secondary / experimental:** `ChatGPTProductRuntime` with `browser-owned`; the `assemble_product_runtime()` default is unchanged only for compatibility.
- **Historical:** `ChatGPTWebClient` and `browserless-request` are not the primary new-integration write path.
- The CLI `doctor`, `status`, `capabilities`, and `messages` inspect the legacy runtime by default, **not** Direct HTTP send health.
- Other product providers have separate, generally experimental support; do not assume a universal provider router or an MCP server exists.

## Source of truth

Read [README.md](README.md), [docs/quickstart.md](docs/quickstart.md), [STATUS.md](STATUS.md), [docs/capabilities.md](docs/capabilities.md), [docs/providers.md](docs/providers.md), [SECURITY.md](SECURITY.md), then [docs/architecture.md](docs/architecture.md) when changing internals. [docs/README.md](docs/README.md) distinguishes current material from PR-specific archival evidence. For an example of the **recommended** Python path, use [examples/direct_http_send.py](examples/direct_http_send.py).

## Safe engineering workflow

1. Determine the smallest existing contract that owns the requested behavior. Prefer a focused fix over a new abstraction or transport.
2. Make changes on a branch; keep release and packaging claims consistent across entrypoints. Do not silently migrate existing callers between runtime types.
3. Preserve existing write/finality/authority invariants and regression tests. For product-changing code, add focused deterministic coverage; seek bounded live verification only when appropriate.
4. Run relevant tests; for PR-sized changes use `python -m pytest -q` and the repository CI matrix (including wheel/sdist installation gates). A docs-only change should not trigger an authenticated Send.
5. Inspect the final diff for accidental scope expansion, incorrect version/release claims and secret-bearing files.

## Do not do

- **No automatic replay** after an ambiguous product write; reconcile it first.
- **No implicit fallback** between Direct HTTP, browser-owned or experimental transports.
- **No authorization inference** from a visible UI control, tool capability, partial stream or document.
- **No anti-abuse/challenge bypass**, token synthesis or credential export.
- Never commit `auth_data.json`, browser profiles, cookies, signed URLs, private captures, user conversations or workspace artifacts.
- Do not silently promote historical experimental evidence to current live-verified support.
- CWA is not an autonomous agent; task policy, Git/filesystem authority and human approval stay upstream.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) for full requirements.
