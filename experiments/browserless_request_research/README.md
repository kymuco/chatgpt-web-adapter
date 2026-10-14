# Browserless HTTP — verified results, 2026-10-14

The new `chatgpt_web_adapter.browserless_http.BrowserlessHTTPClient` sends through
HTTP and Node without starting a browser or opening a tab. Node 24+ and curl are
required. The first use downloads a public integrity module pinned by SHA-256.

```python
from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient

client = BrowserlessHTTPClient(auth_file="auth_data.json")
reply = client.send("Hello", model="gpt-6-instant", temporary=True,
                    on_token=lambda text: print(text, end="", flush=True))
print(client.last_timing)

saved = client.send("Remember the word orchid", model="gpt-6-instant")
continued = client.send("What word did I give you?",
                        conversation=saved.conversation.conversation_id)
```

Verified live: Instant replies, text callbacks, canonical text equality,
`is_temporary_chat=true` for temporary chats, persistent creation and continuation.
The missing HTTP bootstrap/device cookie was a critical finding: the original
saved auth contained session cookies but no `oai-did`. HTTP bootstrap establishes
that context without a browser. The updated JS proof/VM also differs from the
legacy implementation. The new snapshot-aware parser delivers text that the old
parser only recovered after completion.

Measured Instant TTFT: cold invocation 9.810 s (including 5.714 s bootstrap),
warm invocation 4.893 s; from final request launch 2.374 and 3.157 s respectively.
These are two samples, not a latency distribution or a physical minimum.
Canonical readback matched both replies and confirmed temporary mode.

**Model limitation:** requesting `gpt-6-sol-wm` on the ordinary route produced
`gpt-6` metadata, although continuation and its text were correct. An explicit
`conversation_origin="flora"` experiment failed at the transport stage. Exact Sol
routing is still unverified; do not treat the requested slug as observed identity.

The public client is experimental and separate from the historical strict
`browserless-request` transport. No automatic write retries or browser fallback
are added. Keep the client instance alive to avoid repeating HTTP bootstrap.
The Node shim is minimal, not a complete browser environment. Protocol updates
require reviewing and updating the pinned module; hash mismatches fail closed.

The earlier lab `probe.py` remains useful for protocol structure investigation;
it uses the older parser and its status labels are conservative. Prefer the new
client above for actual streaming. Local measurement files are in the ignored
`artifacts/browserless-research-2026-10-13/` directory.

## Network measurements and physical bound

Six HTTP/1.1 catalogue requests returned 200. Five reused connections had first-byte
latency min/median/max 647.5/737.9/900.7 ms. Cold cumulative TLS setup was 30.7 ms.
Catalogue TTFB is neither pure RTT nor generation TTFT. Five samples do not justify
p95 estimates. The diagnostic can be repeated without sending messages:

```powershell
.\.venv\Scripts\python.exe -m chatgpt_web_adapter.browserless_diagnostics --samples 6
```

For ready credentials and an established connection:
`TTFT = client work + propagation + routing/queue + prefill + first decode + delivery`.
Current sequential Sentinel prepare/finalize and conversation prepare add about
1.7 s before final request launch on a warm session. Prefetching and connection
reuse are candidates for further measurement, not proven speedups here.

A propagation bound for one-way distance d is `2*d/c` in vacuum; approximate
fiber propagation is `2*d/(200,000 km/s)`, or 10 ms per 1,000 km one-way. Backend
location, actual path, queue and compute costs are unknown, so no absolute
physical minimum in milliseconds can be established from these observations.

## Attachments (live-verified 2026-10-14)

`client.send(prompt, temporary=True, media=[Path("image.png")])` supports images.
For files use `media=[Path("document.txt")]`; bytes require `(data, "document.txt")`.
Images use multimodal content; ordinary files use attachment metadata and the
`my_files` upload route. Storage PUT requests carry no ChatGPT authorization.

Live Instant checks: a generated red/blue PNG was correctly described left/right;
a TXT attachment yielded its exact hidden verification code and copper-bolt count.
Other formats (PDF, DOCX, etc.), mixed attachments and large files are not yet
live-verified. Temporary conversation mode does not establish immediate deletion
of uploaded files from account storage. Upload time remains inside send TTFT.
