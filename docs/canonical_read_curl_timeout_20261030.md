# Canonical read: bounded recovery from curl transport timeout

On 2026-10-30, a Codexia DW6 `status` (which reads the newest Worker and
Controller messages) stopped with `RequestError: curl failed:
exit_code=28; http_status=200`. The request had received HTTP response
headers but failed to complete the transfer before the HTTP client's 60-second
`--max-time` limit. CWA correctly rejected the incomplete response after
PR #246; no Controller send occurred.

CWA's canonical conversation GET reader already steps the server's
`num_turns` hint through 20, 10 and 5 when it receives explicit HTTP
408/504 or selected 500 timeout responses. The curl 28 failure previously
escaped before this load-shedding mechanism could run.

This narrow fix classifies curl exit 28 as `request_stage=transport_timeout`
while preserving the existing numeric HTTP status and a non-sensitive error
message. Only `_read_current_page` catches that exact structured exception.
It advances to the next smaller `num_turns` hint; there is no same-size
retry, unbounded loop, or silent success. If the final hint also times out,
the actual final `RequestError` propagates. Exit 18/56, other transport
errors, and ordinary GET failures still fail closed.

This is a **safe-read recovery only**. It does not alter protected write
requests, Sentinel prepare/finalize, model invocation, auth refresh, approval,
or DW5's admitted-send fencing. It does not guarantee a slow server will
return successfully: each attempt retains the client's configured timeout.
The fix also does not prove why the server failed to finish this specific
response; the established evidence is curl exit 28 after HTTP 200 headers.

Regression tests use deterministic fake GET responses and verify bounded
20 -> 10 -> 5 behavior, a successful smaller response, exhaustion,
unchanged behavior for other curl failures and existing HTTP 504 load
shedding. No network or model calls are part of the test.
