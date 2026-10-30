# Troubleshooting

Start with:

```bash
chatgpt-web-adapter auth status --auth-file auth_data.json
```

## Primary ChatGPT Direct HTTP troubleshooting

Start with `BrowserlessHTTPClient` on the same installed package/source
revision; confirm Node.js 24+, curl and a valid `auth_data.json` without
printing its contents. A rejected auth/session request must be reconciled
before any new send. Direct HTTP has **no automatic browser fallback**.

If a response is lost after a potentially committed Send, do not send the
same prompt again automatically: attempt canonical readback using the known
conversation identity, or report the outcome as uncertain.

Browser-owned rich-input is a secondary experimental UI path. On 2026-10-29,
its three-file live attempt stalled after one visible attachment; do not
clear the attachment fence or repeat that turn without confirmed state.

## Missing or Expired Access Token

Try `chatgpt-web-adapter auth refresh --auth-file auth_data.json`. If refresh is
rejected, run `chatgpt-web-adapter auth login --force --auth-file auth_data.json`.

## Secondary browser-owned / legacy diagnostics

The following browser and Sentinel steps apply to explicit browser-owned
or historical compatibility workflows, **not** the primary Direct HTTP Send.

## Browser Profile Is Busy

Another SDK process is using the same Chromium profile. Let it finish or stop it
cleanly. Do not delete Chromium lock files while a browser process is active.
Use separate profile directories for intentionally concurrent sessions.

## Sentinel Capture Timeout

The provider retries transient capture failures by default. If all attempts
time out:

1. Confirm `browser_profile_exists` is true in `auth status`.
2. Run `auth login --force` and confirm the correct account appears.
3. Retry once with `sentinel_headless=False` to inspect the visible page.
4. Inspect `provider.last_diagnostics`; it contains stage booleans, not tokens.

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(
    auth_file="auth_data.json",
    auto_sentinel=True,
    sentinel_timeout=90,
    sentinel_max_attempts=2,
    sentinel_headless=False,
)

try:
    client.send("Reply with exactly: smoke-ok")
finally:
    provider = getattr(client, "_sentinel_bundle_provider", None)
    if provider is not None:
        print(provider.last_diagnostics)
```

## Text Works but Images Fail

Check file creation (`/backend-api/files`), blob upload, upload finalization, and
the final protected conversation write separately. Supported formats are PNG,
JPEG/JPG, GIF, and WebP. Start with a tiny PNG to distinguish upload-contract
problems from size or format problems.

## Conflicting Session Cookies

Current sessions may use `.0`/`.1` chunked session cookies. The loader prefers
explicit chunks and removes the conflicting non-chunked fallback in memory. A
fresh `auth login --force` rewrites the file with the current structured jar.

## Safe Diagnostics

```python
client = ChatGPTWebClient(
    auth_file="auth_data.json",
    auto_sentinel=True,
    debug_trace_dir="traffic-scan/client-traces",
)
```

Auth, cookies, conduit credentials, and Sentinel headers are redacted. Raw HAR
files can still contain secrets and must be sanitized before sharing.

## Legacy browser-only live smoke (not required for HTTP)

The following example is retained for compatibility diagnostics; a successful
single-turn browser smoke does not establish guarded multi-file reliability.

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(
    auth_file="auth_data.json",
    auto_sentinel=True,
    sentinel_headless=True,
)
response = client.send("Reply with exactly: smoke-ok")
assert response.text.strip() == "smoke-ok"
assert response.conversation.conversation_id
```

For the full release matrix, see [live_smoke_checklist.md](live_smoke_checklist.md).
