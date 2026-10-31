# Standalone `cwa send` — primary ChatGPT CLI

Since published `v0.4.1`, `cwa send` uses the **Direct HTTP**
`BrowserlessHTTPClient` by default. No ChatGPT browser tab is needed to send.
This differs from the older `cwa runtime send` command and the
`assemble_product_runtime()` compatibility default (browser-owned, experimental).

## Setup and first turn

Requirements: Python 3.10–3.14, Node.js 24+, `curl` and valid
`auth_data.json`. First-time authentication is interactive and needs
the optional `[browser]` package extra:

```powershell
python -m pip install "chatgpt-web-adapter[browser]"
chatgpt-web-adapter auth login --auth-file auth_data.json
cwa send "Explain this result in two sentences." --profile HIGH
```

See [authentication](authentication.md) for session handling. Direct HTTP
uses private, changeable ChatGPT web behavior; it is not an official API.

## Profiles, continuation and files

The default requested profile is `HIGH`. Supported aliases are
`FAST=INSTANT`, `BALANCED=MEDIUM`, `DEEP=HIGH`. Model/profile requests
do not attest what the server actually selected.

```powershell
cwa send "Brief answer." --profile INSTANT
cwa send "Compare the tradeoffs." --profile MEDIUM
cwa send "Continue the previous chat." --conversation <conversation-id> --profile HIGH
cwa send "Summarize these notes." --file notes-a.md --file notes-b.md --profile HIGH
cwa send "Answer without saving a durable chat." --temporary
```

`--conversation` accepts an ID or standard ChatGPT URL. On current `main` it
also accepts `https://chatgpt.com/g/<project-or-gpt-id>/c/<conversation-id>`,
a parser update **not included in the published `v0.4.1` wheel**. Parsing
does not guarantee access; the signed-in account must be authorized to read
or continue that conversation. Project-specific authenticated continuation
is not yet established by an independent live E2E.

## Output and failures

```powershell
cwa send "Explain the architecture." --stream
cwa send "Inspect this." --json
```

Plain mode shows the completed answer; streaming may include provisional
output, so final/canonical readback remains authoritative. JSON output exposes
structured send results or a bounded failure. Do not interpret a lost response
after potential submission as permission to resend. **No automatic retry or
transport fallback** is performed.

`cwa doctor`, `cwa status`, `cwa capabilities` and `cwa messages` still
inspect the **legacy product runtime** by default; they are not Direct HTTP
send-readiness checks.

## Explicit secondary runtime

The older browser-owned UI mode is **EXPERIMENTAL**, even though its
historical Python assembly default is retained for compatibility:

```powershell
cwa send "Use the page-owned UI path." --transport browser-owned --profile HIGH
cwa runtime send "Use the historical product-runtime command."
```

These are separate, explicitly selected paths; CWA does not silently migrate
between them. See [primary HTTP SDK](browserless_http_sdk.md) and
[capabilities](capabilities.md) for per-operation evidence.
