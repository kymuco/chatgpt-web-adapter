# Direct HTTP: Sentinel prepare rejection diagnostics v1

A narrowly scoped diagnostic change to `BrowserlessHTTPClient`. This change
does **not** change request ordering, authentication, challenge handling,
conversation-write policy or automatic retry behavior.

When the HTTP transport receives an unusable prepare response,
`_acquire_http_bundle()` distinguishes:

- `http_status`: the HTTP status is not 200.
- `non_object_response`: the decoded value is not a JSON object (including
  HTML/text, empty responses, JSON strings and arrays).
- `missing_prepare_token`: HTTP 200 with an object but no nonempty string token.

The `RequestError` includes the HTTP status, decoded Python response type,
request stage and fixed endpoint, but **never** records response values, the
raw response body, prepared tokens, proof material, Turnstile descriptors or
cookies. The existing `body_preview` remains empty for this error.

HTTP 200 and a structurally present prepare token do not authorize
finalization or a conversation write. The existing handling of
server-required Turnstile, PoW and SO conditions is unchanged.

## Codexia operator boundary

A previous `send_admitted` is not cleared or retried by this change. A
transport failure after admission requires separate, evidence-based durable
reconciliation. Uncertain sends remain blocked.

## Regression

Run:

```shell
python -m pytest -q tests/test_browserless_http_prepare_diagnostics_v1.py tests/test_request_error.py
```

The fake response tests cover unsuccessful HTTP status, non-object HTTP 200,
missing and malformed tokens, no response/body leakage and the unchanged
successful-prepare branch. No live Sentinel or conversation requests occur in
these tests.
