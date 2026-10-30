# Direct HTTP: streaming POST lifetime

## Observed failure (Codexia DW6.1, 2026-10-30)

Controller continuation was explicitly authorized once and reached the ChatGPT streaming
POST. curl terminated after approximately 60 seconds with 21,009 bytes received.
The server had actually accepted the request and generated a completed assistant reply,
verified separately through canonical GET. Codexia correctly kept its durable
send_admitted fence until human-approved observed-send reconciliation recorded
the completed reply without replaying the POST.

Cause in CWA: BrowserlessHTTPClient has timeout=60 by default, and the inherited
curl builder applied --max-time=60 even to an active, streaming conversation POST.
An absolute 60-second deadline is unsuitable for slower reasoning streams.

## Targeted fix

The Direct HTTP client alone now gives no-buffer POST streams:

- Connection limit: the existing --connect-timeout 10.
- Transfer inactivity: --speed-limit 1 --speed-time max(client.timeout, 180).
- Bounded total stream lifetime: --max-time max(client.timeout, 1800).

curl low-speed protection detects low transfer rate over its configured window,
including initial lack of response data and a stalled ongoing stream. This is
not a semantic SSE heartbeat timer, and healthy streams reaching the total
cap still fail closed. Short JSON calls, canonical GET, Sentinel prepare/finalize
and buffered writes retain their original overall timeout.

A nonzero exit from streaming POST is still an ambiguous write outcome.
Nothing retries it or silently treats a partial response as complete; Codexia
must inspect the canonical conversation and reconcile an observed completed send
under its independent human-gated workflow.

## Test and limitation

Run:

    python -m pytest -q tests/test_direct_http_stream_post_lifetime.py

The tests examine curl arguments using fake client objects. There is no live POST,
no Sentinel negotiation, no auth-file access and no model generation.
This validates option selection, not server behavior or proof of completion
for long GPT-6 streams. A later approved E2E test is necessary for that.
