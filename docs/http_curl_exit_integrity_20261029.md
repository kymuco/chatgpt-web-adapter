# HTTP transport: do not trust HTTP status without curl completion

The shared CWA HTTP transport previously raised a transport error only when
curl exited nonzero *and* it could not extract an HTTP status. This could
mistakenly return a partial or truncated response body to JSON parsing if
curl had already received HTTP 200 headers before a transfer failure.

The revised contract is fail-closed: **any nonzero curl exit code is a
RequestError**, including curl 18 (partial file transfer), 28 (timeout) and
56 (receive failure), regardless of any already-observed HTTP status. The
exception provides only bounded numeric curl exit and HTTP status fields,
with request_stage=transport; it never adds response body, cookie, auth,
request payload or arbitrary stderr to its message. Response cookies are
applied only after a completed curl process.

For an actual curl exit code of zero, the previous JSON decoding and response
return semantics are unchanged. An HTTP 200 containing HTML/text, a JSON string
scalar or other non-object body may still occur and is classified separately
by the Direct HTTP Sentinel prepare diagnostics.

## Evidence and limitation

A prior Codexia Direct HTTP Sentinel probe recorded HTTP 200 decoded to
Python str; subsequent probes decoded HTTP 200 to valid dict and observed
required Turnstile, PoW and SO. The original failing curl process's exit code,
content type and raw bytes were **not recorded**, so a truncated transfer
is a plausible **unconfirmed** contributor, not an established root cause.
This change prevents partial transfers from being mistaken for a successful
HTTP response without bypassing any server challenge.

The fix does **not** perform automatic retries, alter Sentinel/challenge
processing, or authorize a Codexia Controller send. Recovery of an existing
DW5 send_admitted fence still requires independent durable reconciliation.

Run:

    python -m pytest -q tests/test_curl_exit_after_http_headers.py

The regression uses a fake subprocess only, with partial HTTP 200 and other
failure variants, cookie immutability on failed transfers and an unchanged
successful JSON path. No live network requests are included.
