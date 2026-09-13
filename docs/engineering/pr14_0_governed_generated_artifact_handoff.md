# PR14.0 — Governed Generated Artifact Handoff

## Purpose

PR13.1–PR13.4 established the read-side chain for a ChatGPT-generated artifact:

```text
saved conversation
  -> explicit product-owned file_id
  -> identity-bound resolver
  -> approved locator
  -> exact artifact bytes
  -> byte-count / SHA-256 integrity evidence
  -> longitudinal identity stability
```

Those experiments deliberately stopped before filesystem authority. PR14.0 promotes
that evidence into one bounded production capability: materialize one caller-named
generated artifact to one caller-authorized local destination without turning an
observed product locator into filesystem or retry authority.

This is the graduation path frozen in PR10.1: stable product identity and a safe
identity-bound resolver are now proven, so CWA may add a handoff only under explicit
destination, overwrite, integrity, credential, and retry boundaries.

## Public operation

The production operation is intentionally narrow and is exposed through the client
and product runtime rather than as a root-level free function:

```python
result = client.handoff_generated_artifact(
    conversation,
    filename="report.pdf",
    destination="./exports/report.pdf",
    overwrite=False,
)

result = runtime.handoff_generated_artifact(
    conversation,
    filename="report.pdf",
    destination="./exports/report.pdf",
    overwrite=False,
)
```

`chatgpt_web_adapter.generated_artifact_handoff.handoff_generated_artifact` remains an
internal composition helper. The stable root value surface is:

```text
GeneratedArtifactHandoffResult
GeneratedArtifactHandoffError
GENERATED_ARTIFACT_HANDOFF_SCHEMA
DEFAULT_GENERATED_ARTIFACT_MAX_BYTES
```

These values are classified as shared support; the operation itself is reached
through `ChatGPTWebClient` or `ChatGPTProductRuntime`, matching the existing
first-class runtime method pattern.

The success value contains only stable, non-locator evidence:

```text
conversation_id
source_filename
destination
size_bytes
sha256
overwritten
integrity_verified = true
```

It does **not** expose the product `file_id`, resolver payload, locator, signed query,
credentials, or artifact bytes.

## Authority model

### Product identity

The human-readable filename is a selector, not identity.

PR14.0 accepts only an explicit `file_id` from the conversation-scoped files
collection as production artifact identity. Research fallback candidates such as
`artifact_id`, `asset_id`, or generic `id` are not silently promoted.

```text
filename selector != product identity
file_id = product identity
```

Zero filename matches fail closed. Multiple filename matches fail closed. A unique
filename match without a valid `file_id` fails closed.

### Destination authority

The caller must provide the exact destination path. PR14.0 does not infer a download
folder, reuse the source filename as local authority, create parent directories, or
pick a replacement path.

Before any network read:

- the destination parent must already exist and be a directory;
- a symlink destination is rejected;
- an existing non-regular destination is rejected;
- an existing regular file is rejected unless `overwrite=True` was supplied.

The default is therefore:

```text
existing destination -> fail before download
```

### Overwrite authority

`overwrite=False` is protected both before retrieval and at publish time. The final
no-overwrite publication uses an atomic same-directory hard-link from the staged
artifact, so a file that appears after the initial authority check causes a
fail-closed `DESTINATION_EXISTS` rather than a hidden overwrite.

`overwrite=True` authorizes replacement at that exact path and publishes with
`os.replace`. It does not authorize directory replacement or symlink traversal.

## Read chain

A successful handoff uses the already-characterized PR13 chain:

1. one authenticated read of
   `/backend-api/conversations/{conversation_id}/files`;
2. one authenticated read of
   `/backend-api/files/download/{file_id}?conversation_id=...&inline=false`;
3. one non-redirecting GET of the approved resolver locator.

There is no endpoint fallback and no automatic request retry in this capability.

If discovery metadata already proves `source_size > max_bytes`, the handoff stops
immediately after discovery. Resolver and locator retrieval are not attempted.

## Locator and credential policy

The PR13.3 locator policy becomes a production invariant.

Allowed locator classes:

- `https://chatgpt.com/...`;
- `https://oaiusercontent.com/...`;
- `https://*.oaiusercontent.com/...`.

Rejected:

- non-HTTPS URLs;
- URL userinfo;
- fragments;
- non-default ports;
- any other origin;
- redirects.

Credential forwarding is origin-bound:

```text
chatgpt.com locator
    -> authenticated ChatGPT headers allowed

oaiusercontent.com locator
    -> no ChatGPT Authorization header
    -> no ChatGPT Cookie header
```

The dedicated handoff read path does not route resolver or artifact response bodies
through the normal debug HTTP body trace writer. This prevents an enabled debug
trace from silently persisting signed locators or generated artifact bytes.

## Bounded retrieval

The default artifact size ceiling is 1 GiB:

```text
DEFAULT_GENERATED_ARTIFACT_MAX_BYTES = 1073741824
```

The caller may supply a different positive `max_bytes` value explicitly. Retrieval
is written directly into a sibling staging file rather than accumulated in Python
memory.

Known product size metadata is checked before resolution. During transfer, curl's
bounded filesize path is mapped to the explicit
`ARTIFACT_SIZE_LIMIT_EXCEEDED` failure. The staged byte count is checked again before
publish so unknown or inaccurate response metadata cannot bypass the bound.

## Materialization transaction

The artifact is never downloaded directly into the caller-visible destination.

```text
approved locator
    -> unique sibling .part staging file
    -> retrieval complete
    -> fsync staging file
    -> compute staged byte count + SHA-256
    -> compare product size metadata when present
    -> atomic publish
    -> re-read destination
    -> verify exact byte count + SHA-256
    -> success result
```

For `overwrite=False`, publication is atomic no-replace. For `overwrite=True`,
publication uses `os.replace`.

The staging sync path uses a writable file handle so the contract works on both the
supported Linux and Windows CI platforms. Staging files are cleaned on pre-publish
failures; cleanup never grants a second publish attempt.

## Ambiguous filesystem failure

A publish attempt is a write boundary. If the operating system reports a publish
failure for which final destination state cannot be proven, PR14.0 reports:

```text
destination_state = unknown_after_publish_attempt
```

and stops. It does not retry the write automatically.

If publication succeeded but CWA cannot complete the post-write readback, or the
materialized bytes no longer match the staged size/SHA-256, PR14.0 reports:

```text
destination_state = published_unverified
```

and likewise does not retry, delete, roll back, or overwrite again automatically.

This preserves the broader CWA rule used for product writes:

```text
ambiguous write != retry authority
```

## Runtime governance

`ChatGPTProductRuntime.governance()` reports this capability independently of the
existing rich-input `FILES` transport capability:

```text
generated_artifact_handoff_supported
generated_artifact_handoff_identity_authority
generated_artifact_handoff_destination_authority
generated_artifact_handoff_implicit_overwrite
generated_artifact_handoff_automatic_retry
generated_artifact_handoff_cross_origin_chatgpt_credentials
```

A runtime backed by a legacy/custom canonical client that does not expose the handoff
method reports `generated_artifact_handoff_supported=false`. The presence of a method
on `ChatGPTProductRuntime` itself never fabricates support in an injected client.

The governance extension preserves historical runtime construction used by existing
regression tests: it tolerates older objects that expose `client` but predate the
`canonical` alias.

## Stable failure surface

`GeneratedArtifactHandoffError` reports bounded fields only:

```text
reason
stage
status_code
destination_state
```

The failure surface never includes `file_id`, resolver locator, signed query,
credentials, resolver body, or artifact bytes.

Stages are:

```text
authority
discovery
resolution
retrieval
publish
verification
```

The historical `chatgpt_web_adapter.errors` compatibility namespace is intentionally
not widened by PR14.0. The new error remains available as an explicit root/shared
support symbol without changing the exact legacy `errors.__all__` contract.

## Scope boundaries

PR14.0 does not add:

- bulk artifact download;
- destination inference;
- implicit parent-directory creation;
- arbitrary URL download;
- redirect following;
- resumable download;
- automatic network retry;
- automatic filesystem retry;
- automatic rollback after an ambiguous publish;
- product-side writes or mutations.

The capability is a governed handoff from already-proven product-owned identity to
one explicit local filesystem destination.

## Deterministic regression coverage

The candidate covers at minimum:

- successful verified materialization;
- explicit overwrite replacement;
- pre-read rejection of unauthorized overwrite;
- no-overwrite destination race;
- duplicate filename ambiguity;
- explicit `file_id` requirement;
- unknown locator origin rejection;
- cross-origin credential stripping;
- source-size mismatch;
- known-size fail-fast before resolution;
- curl filesize-limit mapping;
- symlink destination rejection;
- Windows-compatible staging fsync;
- staging verification failure with `destination_state=unchanged`;
- post-publish readback failure with `destination_state=published_unverified`;
- client/runtime public surface and runtime governance;
- legacy runtime/client compatibility boundaries.

## Final live acceptance target

Before merge, PR14.0 requires a green supported CI matrix and one authenticated
exact-head live gate against the existing PR13 generated text fixture:

```text
filename = cwa_pr13_1_identity_probe.txt
size = 45
sha256 = d0bb354d72fad3715f5348740d75dd644435165f68034f54f7974c834cbe9f1d
```

The live gate must prove on the exact candidate SHA:

```text
identity-bound discovery = PASS
resolver = PASS
locator policy = PASS
local materialization = PASS
materialized size = 45
materialized SHA-256 = expected
post-write integrity = PASS
implicit overwrite = REJECTED
automatic retry = NOT ATTEMPTED
```

The fixture destination is local only; the live gate performs no ChatGPT/product
write. The PR must remain draft until deterministic CI is green; only after the
exact-head authenticated gate passes may it be promoted for merge.
